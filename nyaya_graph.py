import os
import json
from typing import TypedDict, Annotated
from dotenv import load_dotenv

# LangGraph Core Imports (From Video)
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.types import interrupt
from langgraph.checkpoint.memory import MemorySaver

# LangChain & RAG Imports (From Video - Lightweight for 512MB Render Deployment)
from langchain_groq import ChatGroq
from langchain_tavily import TavilySearch
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS

load_dotenv()

# ==========================================
# 1. TOOLS & LLMs INITIALIZATION
# ==========================================
MODEL_NAME = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")  # change via .env without editing code

search_tool = TavilySearch(max_results=2)
tools = [search_tool]

# Fast, low-temperature LLM for classification & structured legal analysis
core_llm = ChatGroq(
    model=MODEL_NAME,
    temperature=0.2,
    max_retries=3
)

# Writer LLM bound with Tavily Search Tool for drafting & live legal lookup
writer_llm_with_tools = ChatGroq(
    model=MODEL_NAME,
    temperature=0.5,
    max_retries=3
).bind_tools(tools)

# ==========================================
# 2. RAG RETRIEVERS (FAISS + Google Gemini Embeddings for 512MB RAM)
# ==========================================
# Uses Google AI Studio Gemini API for text-embedding-004 (Zero local RAM, Free Tier compatible)
embeddings = GoogleGenerativeAIEmbeddings(model="embedding-001")

DEFAULT_BNS_DOCS = [
    "Bharatiya Nyaya Sanhita (BNS) Section 318 (formerly IPC 420): Cheating and dishonestly inducing delivery of property is punishable with imprisonment up to 7 years and fine.",
    "BNS Section 316 (formerly IPC 406): Criminal breach of trust punishable up to 5 years imprisonment.",
    "BNS Section 351 (formerly IPC 506): Criminal intimidation punishable with imprisonment up to 2 years, or up to 7 years if threat is to cause death or grievous hurt.",
    "BNS Section 79 & IT Act Section 66C/66D: Identity theft and cheating by personation using computer resource (Cyber Fraud) punishable with 3 years imprisonment and Rs. 1 lakh fine.",
    "Consumer Protection Act 2019 Section 2(47) & Section 35: Unfair trade practices, defective goods, or deficient services allow consumers to file complaints on e-Daakhil for refund, replacement, and mental agony compensation."
]

DEFAULT_PROCEDURE_DOCS = [
    "BNSS Section 173 (Zero FIR & e-FIR): Every police station is legally bound to register an FIR for cognizable offences regardless of jurisdiction (Zero FIR). If police refuse under BNSS 173(4), send complaint via registered post to SP/DCP or approach Judicial Magistrate.",
    "National Cyber Crime Reporting Portal (1930): In financial cyber fraud, report immediately on 1930 or cybercrime.gov.in within the Golden Hour to freeze fraudulent bank accounts.",
    "Legal Notice Procedure: Before filing a civil or consumer suit, send a formal Legal Notice giving 15 days to rectify the grievance or pay damages, sent via Registered Post A.D.",
    "Free Legal Aid (NALSA - Article 39A): Women, SC/ST, industrial workmen, victims of trafficking, and citizens with annual income below Rs. 3 Lakhs are entitled to free legal representation via District Legal Services Authority (DLSA)."
]

def build_retriever(pdf_path: str, fallback_texts: list[str]):
    if os.path.exists(pdf_path):
        loader = PyPDFLoader(pdf_path)
        document = loader.load()
        splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
        chunks = splitter.split_documents(document)
        vector_store = FAISS.from_documents(chunks, embeddings)
    else:
        vector_store = FAISS.from_texts(fallback_texts, embeddings)
    return vector_store.as_retriever(search_kwargs={"k": 4})

# Lazy-loaded retrievers so Uvicorn binds the port immediately on Render startup
statutes_retriever = None
procedures_retriever = None

def get_statutes_retriever():
    global statutes_retriever
    if statutes_retriever is None:
        statutes_retriever = build_retriever("bns_handbook.pdf", DEFAULT_BNS_DOCS)
    return statutes_retriever

def get_procedures_retriever():
    global procedures_retriever
    if procedures_retriever is None:
        procedures_retriever = build_retriever("legal_procedures.pdf", DEFAULT_PROCEDURE_DOCS)
    return procedures_retriever

def reload_retrievers():
    global statutes_retriever, procedures_retriever
    statutes_retriever = build_retriever("bns_handbook.pdf", DEFAULT_BNS_DOCS)
    procedures_retriever = build_retriever("legal_procedures.pdf", DEFAULT_PROCEDURE_DOCS)

# ==========================================
# 3. GRAPH STATE (Clean & Streamlined)
# ==========================================
class NyayaState(TypedDict):
    case_category: str
    raw_query: str
    messages: Annotated[list, add_messages]
    query_type: str
    retrieved_context: str
    legal_audit: dict
    draft: str
    review_feedback: str
    is_approved: bool
    attempt: int
    final_output: str

# ==========================================
# 4. WORKFLOW 1: CONDITIONAL RAG NODES
# ==========================================
def classifier_node(state: NyayaState) -> dict:
    """Classifies the citizen query into statutes, procedures, or general."""
    prompt = f"""Classify the following Indian legal query into EXACTLY ONE category:
- statutes : Questions about criminal sections, BNS/IPC punishments, fraud laws, consumer rights, or offences.
- procedures : Questions about how to file FIR, Zero FIR, police refusal, court steps, legal aid, or cyber portal 1930.
- general : Casual greetings or general questions.

Query: {state['raw_query']}
Return ONLY ONE WORD (statutes, procedures, or general)."""
    
    response = core_llm.invoke(prompt)
    category = response.content.strip().lower()

    if "statute" in category:
        category = "statutes"
    elif "procedure" in category:
        category = "procedures"
    else:
        category = "general"

    return {"query_type": category}

def statutes_rag_node(state: NyayaState) -> dict:
    """Retrieves chunks from BNS / Statutes PDF and generates structured Legal Audit in 1 fast call."""
    docs = get_statutes_retriever().invoke(state["raw_query"])
    context = "\n\n".join([d.page_content for d in docs])
    audit = generate_single_shot_audit(state["case_category"], state["raw_query"], context)
    return {"retrieved_context": context, "legal_audit": audit}

def procedures_rag_node(state: NyayaState) -> dict:
    """Retrieves chunks from Procedures PDF and generates structured Legal Audit in 1 fast call."""
    docs = get_procedures_retriever().invoke(state["raw_query"])
    context = "\n\n".join([d.page_content for d in docs])
    audit = generate_single_shot_audit(state["case_category"], state["raw_query"], context)
    return {"retrieved_context": context, "legal_audit": audit}

def general_context_node(state: NyayaState) -> dict:
    """Fallback general context + structured Legal Audit."""
    docs = get_statutes_retriever().invoke(state["raw_query"])
    context = "\n\n".join([d.page_content for d in docs])
    audit = generate_single_shot_audit(state["case_category"], state["raw_query"], context)
    return {"retrieved_context": context, "legal_audit": audit}

def generate_single_shot_audit(category: str, query: str, context: str) -> dict:
    """Replaces 3 heavy parallel calls with 1 fast structured JSON call to save latency & rate limits."""
    prompt = f"""You are an Indian Legal Auditor analyzing a {category} matter.
Based on the RAG context below, return ONLY a valid JSON object with EXACTLY these 3 keys:
"applicable_sections": "3 bullet points of exact BNS 2023 / BNSS 2023 / IT Act / Consumer Act sections and punishments",
"risk_and_evidence": "Urgency score (0-100) and key evidence to preserve immediately",
"action_roadmap": "3 chronological steps (where to report, portal/helpline, escalation)"

Write all values in clear English, even if the citizen's case is written in Hindi or Hinglish.

Context: {context}
Citizen Case: {query}"""
    res = core_llm.invoke(prompt).content.strip()
    try:
        start_idx = res.find("{")
        end_idx = res.rfind("}") + 1
        return json.loads(res[start_idx:end_idx])
    except Exception:
        return {
            "applicable_sections": res,
            "risk_and_evidence": "Preserve all digital receipts, screenshots, UTR numbers, and written communication.",
            "action_roadmap": "1. File written complaint / Zero FIR under BNSS 173.\n2. Escalate to SP/DCP under BNSS 173(4) if refused.\n3. Send formal Legal Notice."
        }

# ==========================================
# 5. WORKFLOW 2: ITERATIVE WRITER + TOOL NODE
# ==========================================
WRITER_SYSTEM_PROMPT = """You are a Senior Indian Legal Drafting Advocate.
Draft a formal, court-ready Legal Notice / Police FIR Complaint based on the citizen's case and legal audit.
Use the web search tool ONLY if you need specific recent judgments or official details not in the context.
If human feedback is provided on a previous draft, incorporate every single requested change accurately.
Always write in formal English, even if the citizen's query is in Hindi or Hinglish."""

def _trim_tool_msg(m, limit: int = 2500):
    """Caps very long Tavily results so a single request stays under the TPM limit."""
    if getattr(m, "type", "") == "tool" and isinstance(m.content, str) and len(m.content) > limit:
        return m.model_copy(update={"content": m.content[:limit] + " ...[truncated]"})
    return m

def writer_node(state: NyayaState) -> dict:
    """Writes or rewrites the Legal Notice/FIR Draft based on RAG context or Human feedback."""
    is_returning_from_tool = (
        bool(state.get("messages")) and getattr(state["messages"][-1], "type", "") == "tool"
    )

    if is_returning_from_tool:
        msgs = state["messages"]
        # Only send the CURRENT turn (last human prompt onward), not the whole history
        last_human = max((i for i, m in enumerate(msgs) if getattr(m, "type", "") == "human"), default=0)
        messages = [("system", WRITER_SYSTEM_PROMPT)] + [_trim_tool_msg(m) for m in msgs[last_human:]]
        response = writer_llm_with_tools.invoke(messages)
        return {"messages": [response]}

    attempt = state.get("attempt", 0) + 1
    feedback = state.get("review_feedback", "")
    audit = state.get("legal_audit", {})

    if attempt == 1 and not feedback:
        user_msg = (
            f"Draft a formal Legal Complaint / Notice for this {state['case_category']} case:\n"
            f"Case Facts: {state['raw_query']}\n"
            f"Applicable Sections: {audit.get('applicable_sections', '')}\n"
            f"RAG Context: {state.get('retrieved_context', '')[:3000]}"
        )
    else:
        user_msg = (
            f"Your previous Legal Draft on '{state['raw_query']}' needs modifications requested by the user.\n\n"
            f"Previous Draft:\n{state.get('draft', '')}\n\n"
            f"User's Required Changes:\n{feedback}\n\n"
            f"Write an updated, complete formal Legal Draft incorporating all changes."
        )

    messages = [("system", WRITER_SYSTEM_PROMPT), ("human", user_msg)]
    response = writer_llm_with_tools.invoke(messages)
    return {
        "messages": [("human", user_msg), response],
        "attempt": attempt,
        "review_feedback": feedback or "Ready for Citizen / Advocate Review (HITL)"
    }

tool_node = ToolNode(tools)

def extract_draft_node(state: NyayaState) -> dict:
    """Extracts the clean text of the generated draft after tool calls finish."""
    last_message = state["messages"][-1]
    return {"draft": last_message.content.strip()}

# ==========================================
# 6. WORKFLOW 3: HUMAN-IN-THE-LOOP (HITL)
# ==========================================
def human_review_node(state: NyayaState) -> dict:
    """Pauses execution using interrupt() so the human can approve or request a rewrite."""
    human_response = interrupt({
        "draft": state["draft"],
        "attempt": state["attempt"],
        "legal_audit": state["legal_audit"],
        "instructions": "Approve the draft or enter feedback to trigger the iterative rewrite loop."
    })

    clean_resp = str(human_response).strip().lower()
    if clean_resp in ["approve", "approved", "yes", "ok", "good"]:
        return {
            "is_approved": True,
            "review_feedback": "Approved by Citizen / Advocate"
        }
    return {
        "is_approved": False,
        "review_feedback": str(human_response)
    }

def english_summary_node(state: NyayaState) -> dict:
    """Final step after Human Approval: Generates a clear, practical English Citizen Action Guide."""
    prompt = f"""You are 'Nyaya AI Citizen Advisor'. Based on the approved legal draft and audit below, write a clear, practical English action guide for a common citizen:
1. Applicable Legal Sections & Rationale
2. Immediate Step-by-Step Action Plan for the Next 24 Hours
3. Essential Helpline Numbers (e.g., 1930 Cyber Cell, 112 Emergency Police, 15100 NALSA Free Legal Aid, 1915 Consumer Helpline).

Audit: {state['legal_audit']}
Approved Draft: {state['draft']}"""
    res = core_llm.invoke(prompt)
    return {"final_output": res.content.strip()}

# ==========================================
# 7. ROUTER FUNCTIONS & GRAPH COMPILATION
# ==========================================
def route_query(state: NyayaState) -> str:
    if state["query_type"] == "statutes":
        return "statutes_rag"
    elif state["query_type"] == "procedures":
        return "procedures_rag"
    return "general_context"

def should_switch_tool(state: NyayaState) -> str:
    last_message = state["messages"][-1]
    if getattr(last_message, "tool_calls", None):
        return "tools"
    return "extract_draft"

# Note: Keeping original function name if referenced elsewhere
should_use_tool = should_switch_tool

def should_stop_looping(state: NyayaState) -> str:
    if state["is_approved"]:
        return "english_summary"
    return "writer"

# Build Graph
graph = StateGraph(NyayaState)

graph.add_node("classifier", classifier_node)
graph.add_node("statutes_rag", statutes_rag_node)
graph.add_node("procedures_rag", procedures_rag_node)
graph.add_node("general_context", general_context_node)
graph.add_node("writer", writer_node)
graph.add_node("tools", tool_node)
graph.add_node("extract_draft", extract_draft_node)
graph.add_node("human_review", human_review_node)
graph.add_node("english_summary", english_summary_node)

# Connect Edges
graph.add_edge(START, "classifier")
graph.add_conditional_edges("classifier", route_query)

graph.add_edge("statutes_rag", "writer")
graph.add_edge("procedures_rag", "writer")
graph.add_edge("general_context", "writer")

graph.add_conditional_edges("writer", should_use_tool)
graph.add_edge("tools", "writer")
graph.add_edge("extract_draft", "human_review")

graph.add_conditional_edges("human_review", should_stop_looping)
graph.add_edge("english_summary", END)

checkpointer = MemorySaver()
nyaya_app = graph.compile(checkpointer=checkpointer)
