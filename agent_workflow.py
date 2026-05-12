import json
from typing import Optional, Dict, List, Any, TypedDict
from pydantic import BaseModel, Field

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, START, END

from config import (
    EXTRACTION_SYSTEM_PROMPT,
    TASK_SELECTION_SYSTEM_PROMPT,
    QUERY_REFINEMENT_SYSTEM_PROMPT,
    PERIOD_ANALYSIS_SYSTEM_PROMPT,
    MAX_RETRIES,
    CONFIDENCE_THRESHOLD
)
from retrieval import search_tasks, rerank_with_word_overlap
from document_processor import clean_text
from database import get_task_by_id, check_task_duplicate, add_task_log

class TaskSelectionResult(BaseModel):
    selected_task_id: Optional[str] = Field(description="The ID of the best matching task, or null if no good match")
    task_name: Optional[str] = Field(description="The name of the selected task, or null")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0")
    reasoning: str = Field(description="Explanation of why this task was selected or rejected")
    needs_retry: bool = Field(description="True if confidence is low and query should be refined")

class AgentState(TypedDict):
    api_key: str
    db_collection: Any
    use_reranker: bool
    top_k: int
    raw_text: str
    current_query: str
    candidates: List[Dict]
    retry_count: int
    history: List[Dict]
    final_result: Optional[dict]
    upload_date: Optional[str]
    tracking_status: Optional[dict]
    error: Optional[str]

class PeriodAnalysisResult(BaseModel):
    period_label: str = Field(description="The formatted compliance period label")
    reasoning: str = Field(description="Why this period was chosen")

def fallback_summarize_text(raw_text: str, max_chars: int = 2500) -> str:
    raw_text = clean_text(raw_text)
    if not raw_text: return ""
    lines = [line.strip() for line in raw_text.split(". ") if line.strip()]
    keywords = [
        "employee", "employees", "wage", "salary", "pay", "stipend", "fire",
        "waste", "lift", "escalator", "smoking", "notice", "compensation",
        "workshop", "policy", "deduction", "house", "accommodation", "manpower",
        "working hours", "maintenance", "complaint", "authorized", "return",
        "exchange", "tds", "governance", "shareholding", "xbrl", "compliance"
    ]
    interesting = [line for line in lines if any(k in line.lower() for k in keywords)]
    if not interesting:
        interesting = lines[:20]
    return " ".join(interesting)[:max_chars]

def get_llm(api_key: str, structured_out: bool = False, structured_model=None):
    llm = ChatGoogleGenerativeAI(
        model="gemma-4-31b-it",
        google_api_key=api_key,
        temperature=0.0 if structured_out else 0.7
    )
    if structured_out:
        if structured_model:
            return llm.with_structured_output(structured_model)
        return llm.with_structured_output(TaskSelectionResult)
    return llm

# --- NODES ---

def extract_node(state: AgentState): 
    api_key = state.get("api_key")
    raw_text = clean_text(state.get("raw_text", ""))
    
    if not raw_text:
        return {"error": "No text could be extracted from this document."}
        
    if not api_key:
        return {"current_query": fallback_summarize_text(raw_text)}

    llm = get_llm(api_key, structured_out=False)
    truncated_text = raw_text[:15000]
    try:
        messages = [
            SystemMessage(content=EXTRACTION_SYSTEM_PROMPT),
            HumanMessage(content=f"Input Document:\n{truncated_text}")
        ]
        
        print("\n" + "="*50)
        print("=== [EXTRACT NODE] LLM INPUT ===")
        print(f"System: {messages[0].content}")
        print(f"Human: {messages[1].content[:500]} ... (truncated)")
        print("="*50)
        
        response = llm.invoke(messages)
        summary = response.content
        if isinstance(summary, list):
            summary = " ".join([block.get("text", "") if isinstance(block, dict) else str(block) for block in summary])
        summary = str(summary)
        
        print("=== [EXTRACT NODE] LLM OUTPUT ===")
        print(summary)
        print("="*50 + "\n")
        
        return {"current_query": summary[:2500]}
    except Exception:
        return {"current_query": fallback_summarize_text(raw_text)}


def retrieve_node(state: AgentState):
    query = state["current_query"]
    db_collection = state["db_collection"]
    top_k = state["top_k"]
    use_reranker = state["use_reranker"]
    
    candidates = search_tasks(db_collection, query, top_k=top_k)
    if use_reranker and candidates:
        candidates = rerank_with_word_overlap(query, candidates)
        
    return {"candidates": candidates}


def selection_node(state: AgentState):
    api_key = state["api_key"]
    query = state["current_query"]
    candidates = state["candidates"]
    history = state.get("history", [])
    retry_count = state.get("retry_count", 0)
    
    if not api_key or not candidates:
        if candidates:
            res = TaskSelectionResult(
                selected_task_id=candidates[0]["id"],
                task_name=candidates[0]["metadata"]["task_name"],
                confidence=0.5,
                reasoning="Fallback: Selected top match without LLM evaluation.",
                needs_retry=False
            )
        else:
            res = TaskSelectionResult(
                selected_task_id=None, task_name=None, confidence=0, reasoning="No candidates retrieved", needs_retry=False
            )
        new_history = history + [{
            "attempt": retry_count + 1,
            "query": query,
            "candidates": candidates,
            "selection": res.model_dump()
        }]
        return {"final_result": res.model_dump(), "history": new_history}

    llm = get_llm(api_key, structured_out=True)
    formatted_candidates = "\n\n".join([
        f"Candidate ID: {c['id']}\n{c['document']}" for c in candidates
    ])
    
    try:
        messages = [
            SystemMessage(content=TASK_SELECTION_SYSTEM_PROMPT),
            HumanMessage(content=f"Input Request: {query}\n\nCandidate Tasks:\n{formatted_candidates}")
        ]
        
        print("\n" + "="*50)
        print("=== [SELECTION NODE] LLM INPUT ===")
        print(f"System: {messages[0].content}")
        print(f"Human: {messages[1].content}")
        print("="*50)
        
        parsed_res = llm.invoke(messages)
        
        print("=== [SELECTION NODE] LLM OUTPUT ===")
        print(parsed_res.model_dump_json(indent=2))
        print("="*50 + "\n")
        
        # Enforce threshold hard check
        if parsed_res.confidence < CONFIDENCE_THRESHOLD:
            parsed_res.needs_retry = True
            
        new_history = history + [{
            "attempt": retry_count + 1,
            "query": query,
            "candidates": candidates,
            "selection": parsed_res.model_dump()
        }]
        return {"final_result": parsed_res.model_dump(), "history": new_history}
    except Exception as e:
        res = TaskSelectionResult(
            selected_task_id=None, task_name=None, confidence=0, reasoning=f"Error evaluating candidates: {e}", needs_retry=False
        )
        new_history = history + [{
            "attempt": retry_count + 1,
            "query": query,
            "candidates": candidates,
            "selection": res.model_dump()
        }]
        return {"final_result": res.model_dump(), "history": new_history}

def assess_edge(state: AgentState):
    final_res = state.get("final_result", {})
    retry_count = state.get("retry_count", 0)
    
    if final_res.get("confidence", 0) >= CONFIDENCE_THRESHOLD or not final_res.get("needs_retry", False) or retry_count >= MAX_RETRIES:
        return "end"
    return "refine"

def refinement_node(state: AgentState):
    api_key = state["api_key"]
    original_query = state["current_query"]
    candidates = state["candidates"]
    final_res = state["final_result"]
    retry_count = state.get("retry_count", 0)
    
    if not api_key:
        return {"retry_count": retry_count + 1}
        
    llm = get_llm(api_key, structured_out=False)
    formatted_candidates = "\n\n".join([
        f"Candidate ID: {c['id']}\n{c['document']}" for c in candidates
    ])
    
    try:
        messages = [
            SystemMessage(content=QUERY_REFINEMENT_SYSTEM_PROMPT),
            HumanMessage(content=f"Original Query: {original_query}\nReasoning for Failure: {final_res.get('reasoning', '')}\nPreviously Retrieved Tasks: {formatted_candidates}")
        ]
        
        print("\n" + "="*50)
        print("=== [REFINEMENT NODE] LLM INPUT ===")
        print(f"System: {messages[0].content}")
        print(f"Human: {messages[1].content}")
        print("="*50)
        
        new_query_res = llm.invoke(messages)
        content = new_query_res.content
        if isinstance(content, list):
            content = " ".join([block.get("text", "") if isinstance(block, dict) else str(block) for block in content])
        content = str(content)
        
        print("=== [REFINEMENT NODE] LLM OUTPUT ===")
        print(content)
        print("="*50 + "\n")
        
        return {"current_query": content.strip(), "retry_count": retry_count + 1}
    except Exception:
        return {"retry_count": retry_count + 1}

def period_analysis_node(state: AgentState):
    api_key = state["api_key"]
    raw_text = clean_text(state.get("raw_text", ""))
    upload_date = state.get("upload_date", "")
    final_res = state.get("final_result", {})
    
    if not api_key or not final_res or not final_res.get("selected_task_id"):
        return {"tracking_status": {"status": "Error", "message": "No valid task selected to track."}}

    task_id = int(final_res["selected_task_id"])
    task = get_task_by_id(task_id)
    if not task:
        return {"tracking_status": {"status": "Error", "message": "Task not found in DB."}}

    track_type = task.get("track_type", "yearly")
    llm = get_llm(api_key, structured_out=True, structured_model=PeriodAnalysisResult)
    
    truncated_text = raw_text[:15000]
    
    try:
        messages = [
            SystemMessage(content=PERIOD_ANALYSIS_SYSTEM_PROMPT),
            HumanMessage(content=f"Document Text:\n{truncated_text}\n\nMatched Task Frequency: {track_type}\nUpload Date: {upload_date}")
        ]
        
        parsed_res = llm.invoke(messages)
        
        return {"tracking_status": {
            "period_label": parsed_res.period_label,
            "reasoning": parsed_res.reasoning,
            "task_id": task_id
        }}
    except Exception as e:
        return {"tracking_status": {"status": "Error", "message": f"Date Analysis Failed: {e}"}}

def tracking_node(state: AgentState):
    tracking_status = state.get("tracking_status", {})
    if tracking_status.get("status") == "Error":
        return state

    task_id = tracking_status.get("task_id")
    period_label = tracking_status.get("period_label")
    
    if not task_id or not period_label:
        return {"tracking_status": {"status": "Error", "message": "Missing period or task ID."}}

    duplicate = check_task_duplicate(task_id, period_label)
    
    if duplicate:
        tracking_status["status"] = "Already Marked"
    else:
        add_task_log(task_id, period_label, "Completed")
        tracking_status["status"] = "Newly Logged"

    return {"tracking_status": tracking_status}

# --- BUILD GRAPH ---

workflow = StateGraph(AgentState)
workflow.add_node("extract", extract_node)
workflow.add_node("retrieve", retrieve_node)
workflow.add_node("selection", selection_node)
workflow.add_node("refinement", refinement_node)
workflow.add_node("period_analysis", period_analysis_node)
workflow.add_node("tracking", tracking_node)

workflow.add_edge(START, "extract")
workflow.add_edge("extract", "retrieve")
workflow.add_edge("retrieve", "selection")
workflow.add_conditional_edges("selection", assess_edge, {"end": "period_analysis", "refine": "refinement"})
workflow.add_edge("refinement", "retrieve")
workflow.add_edge("period_analysis", "tracking")
workflow.add_edge("tracking", END)

compiled_workflow = workflow.compile()

def agentic_matching_workflow(api_key: str, db_collection, raw_text: str, upload_date: str, top_k: int = 5, use_reranker: bool = True) -> dict:
    initial_state = {
        "api_key": api_key,
        "db_collection": db_collection,
        "use_reranker": use_reranker,
        "top_k": top_k,
        "raw_text": raw_text,
        "upload_date": upload_date,
        "current_query": "",
        "candidates": [],
        "retry_count": 0,
        "history": [],
        "final_result": None,
        "tracking_status": None,
        "error": None
    }
    
    final_state = compiled_workflow.invoke(initial_state)
    
    if final_state.get("error"):
        return {
            "status": "error",
            "message": final_state["error"]
        }
        
    return {
        "status": "success",
        "final_result": final_state["final_result"],
        "history": final_state["history"],
        "tracking_status": final_state["tracking_status"],
        "total_attempts": final_state["retry_count"] + 1
    }
