"""LangGraph agentic loop — Topology B (PLAN §6 / §0 R4 / R5).

  rewrite → retrieve → grade → ┌── generate → END
                                ├── re_retrieve → retrieve → grade (one bounded loop)
                                └── refuse → END

Each node is :func:`@traceable` so a Telegram message produces a clean LangSmith
trace tree per turn. The graph itself is stateless; per-chat memory lives in
``bot/session.py`` (last ~N turns) and is passed in via the initial state.

Re-retrieve transform (R4) is *unified* with cross-lingual fallback (R2):
- ``narrow_terminology`` → ``rewrite.broaden_terminology`` (colloquial → official KZ term)
- ``cross_lingual_thin`` → relax the lang filter on the next retrieve
- ``wrong_topic`` → refuse immediately (don't burn a retry)
- ``ok`` with empty kept (shouldn't happen) → refuse

Loop cap = :data:`config.GRADE_LOOP_CAP` (default 1) so a Telegram answer stays
under ~6–8s with the four extra LLM hops.
"""
from __future__ import annotations

from typing import Any, Callable, TypedDict

import config
from rag import answer as answer_mod
from rag import grade as grade_mod
from rag import llm
from rag import prompts
from rag import retriever
from rag import rewrite as rewrite_mod
from schema import Answer, Citation, RetrievedChunk

try:
    from langsmith import traceable  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    def traceable(*args, **kwargs):  # type: ignore[no-redef]
        if args and callable(args[0]):
            return args[0]
        def _deco(fn):
            return fn
        return _deco


# ── State ────────────────────────────────────────────────────────────────────
class AgentState(TypedDict, total=False):
    # Inputs
    question: str
    lang: str
    history: list[tuple[str, str]]
    # Rewrite stage
    rewritten_query: str
    is_follow_up: bool
    # Retrieval / grading
    retrieved: list[RetrievedChunk]
    relax_filter: bool          # set by re_retrieve when overall=cross_lingual_thin
    kept: list[RetrievedChunk]
    grade_failure: str          # last grade overall_failure (for routing + tracing)
    retry_count: int
    # Output
    answer_text: str
    refused: bool
    citations: list[Citation]
    disclaimer: str


# ── Node implementations ────────────────────────────────────────────────────
@traceable(name="agent:rewrite", run_type="chain")
def node_rewrite(state: AgentState) -> AgentState:
    res = rewrite_mod.rewrite_query(state["question"], history=state.get("history") or [])
    return {"rewritten_query": res.query, "is_follow_up": res.is_follow_up,
            "retry_count": 0, "relax_filter": False}


@traceable(name="agent:retrieve", run_type="retriever")
def node_retrieve(state: AgentState) -> AgentState:
    q = state.get("rewritten_query") or state["question"]
    chunks = retriever.retrieve(
        q, state["lang"],
        relax_filter=bool(state.get("relax_filter")),
    )
    return {"retrieved": chunks}


@traceable(name="agent:grade", run_type="chain")
def node_grade(state: AgentState) -> AgentState:
    res = grade_mod.grade_chunks(
        state.get("rewritten_query") or state["question"],
        state.get("retrieved") or [],
    )
    kept = [state["retrieved"][i] for i in res.kept_indices]
    return {"kept": kept, "grade_failure": res.overall_failure}


def route_after_grade(state: AgentState) -> str:
    """Conditional edge — pick the next node based on grade verdict and retry budget."""
    if state.get("kept"):
        return "generate"
    failure = state.get("grade_failure") or grade_mod.FAILURE_OK
    retries = state.get("retry_count") or 0
    if failure == grade_mod.FAILURE_WRONG_TOPIC:
        return "refuse"                  # don't burn a retry on genuinely off-topic
    if retries >= config.GRADE_LOOP_CAP:
        return "refuse"
    if failure in (grade_mod.FAILURE_NARROW_TERMINOLOGY,
                   grade_mod.FAILURE_CROSS_LINGUAL_THIN):
        return "re_retrieve"
    return "refuse"


@traceable(name="agent:re_retrieve", run_type="chain")
def node_re_retrieve(state: AgentState) -> AgentState:
    """Pick the transform from the grade failure and prepare the next retrieve."""
    failure = state.get("grade_failure") or grade_mod.FAILURE_OK
    current_q = state.get("rewritten_query") or state["question"]
    update: AgentState = {"retry_count": (state.get("retry_count") or 0) + 1}
    if failure == grade_mod.FAILURE_NARROW_TERMINOLOGY:
        res = rewrite_mod.broaden_terminology(current_q)
        update["rewritten_query"] = res.query
        update["relax_filter"] = bool(state.get("relax_filter"))  # preserve
    elif failure == grade_mod.FAILURE_CROSS_LINGUAL_THIN:
        # Same query, drop the lang filter so we look in the other language too.
        update["relax_filter"] = True
    return update


@traceable(name="agent:generate", run_type="llm")
def node_generate(state: AgentState) -> AgentState:
    lang = state["lang"]
    keep = (state.get("kept") or [])[: config.KEEP_K]
    text = llm.generate(
        prompts.build_generation_prompt(state["question"], keep, lang),
        system=prompts.system_prompt(lang),
    ).strip()
    if not text:
        return {"refused": True, "answer_text": answer_mod._localized_empty_refusal(
                    state["question"], lang, llm.generate),
                "citations": [], "disclaimer": ""}
    # Reuse the linear path's refusal-template detection + citation builder so
    # the agent path produces *identical* output for refusals and dedup-by-url.
    if answer_mod._is_template_refusal(text, lang):
        return {"refused": True, "answer_text": answer_mod._refusal_text(text, lang),
                "citations": [], "disclaimer": ""}
    body, disc = answer_mod._extract_disclaimer(text, lang)
    return {"refused": False, "answer_text": body,
            "citations": answer_mod._citations(keep),
            "disclaimer": disc}


@traceable(name="agent:refuse", run_type="chain")
def node_refuse(state: AgentState) -> AgentState:
    return {"refused": True, "answer_text": answer_mod._localized_empty_refusal(
                state["question"], state["lang"], llm.generate),
            "citations": [], "disclaimer": ""}


# ── Graph build + run ────────────────────────────────────────────────────────
def build_graph():
    """Compile the agent graph. Imported lazily so tests that mock individual
    nodes don't need langgraph installed."""
    from langgraph.graph import END, StateGraph

    g = StateGraph(AgentState)
    g.add_node("rewrite", node_rewrite)
    g.add_node("retrieve", node_retrieve)
    g.add_node("grade", node_grade)
    g.add_node("re_retrieve", node_re_retrieve)
    g.add_node("generate", node_generate)
    g.add_node("refuse", node_refuse)

    g.set_entry_point("rewrite")
    g.add_edge("rewrite", "retrieve")
    g.add_edge("retrieve", "grade")
    g.add_conditional_edges("grade", route_after_grade, {
        "generate": "generate",
        "re_retrieve": "re_retrieve",
        "refuse": "refuse",
    })
    g.add_edge("re_retrieve", "retrieve")     # loop back through retrieve → grade
    g.add_edge("generate", END)
    g.add_edge("refuse", END)
    return g.compile()


# Module-level compiled graph (lazy — first call only). Tests using the graph
# directly should call build_graph() to get a fresh one.
_GRAPH: Any = None


def _graph() -> Any:
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    return _GRAPH


@traceable(name="agent:run", run_type="chain")
def run_agent(question: str, lang: str,
              history: list[tuple[str, str]] | None = None,
              *, thread_id: str | None = None) -> Answer:
    """Top-level agent entrypoint — drop-in for ``rag.answer.answer`` once the
    user opts in (see ``rag/answer.answer_agent``). ``thread_id`` is attached
    to the LangSmith trace so all child node runs group together."""
    from rag.llm import _set_thread_id
    _set_thread_id(thread_id)
    initial: AgentState = {
        "question": (question or "").strip(),
        "lang": lang,
        "history": list(history or []),
        "retry_count": 0,
    }
    final = _graph().invoke(initial)
    return Answer(
        text=final.get("answer_text", "") or prompts.refusal(lang),
        lang=lang,
        citations=final.get("citations") or [],
        disclaimer=final.get("disclaimer") or "",
        refused=bool(final.get("refused", False)),
    )
