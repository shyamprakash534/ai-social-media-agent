from contextlib import ExitStack
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt, Command
from typing_extensions import TypedDict

from app.services.ai import generate_content, review_post
from app.config import settings


class ContentState(TypedDict, total=False):
    topic: str
    platform: str
    tone: str
    brand_voice: str
    draft: str
    review_notes: str
    decision: str


_graph = None
_checkpointer = None
_exit_stack: ExitStack | None = None


def _generate(state: ContentState) -> dict[str, Any]:
    draft = generate_content(
        state["topic"],
        state["platform"],
        state.get("tone", "professional"),
        state.get("brand_voice", ""),
    )
    return {"draft": draft}


def _review(state: ContentState) -> dict[str, Any]:
    draft, notes = review_post(state.get("draft", ""), state.get("platform", "linkedin"))
    return {"draft": draft, "review_notes": notes}


def _approval(state: ContentState) -> dict[str, Any]:
    result = interrupt(
        {
            "kind": "human_approval",
            "draft": state.get("draft", ""),
            "review_notes": state.get("review_notes", ""),
        }
    )
    if isinstance(result, dict):
        return {
            "decision": result.get("decision", "reject"),
            "draft": result.get("draft", state.get("draft", "")),
        }
    return {"decision": str(result)}


def _route(state: ContentState) -> str:
    return "done"


def initialize_graph() -> None:
    global _graph, _checkpointer, _exit_stack

    if _graph is not None:
        return

    builder = StateGraph(ContentState)
    builder.add_node("generate", _generate)
    builder.add_node("review", _review)
    builder.add_node("approval", _approval)
    builder.add_edge(START, "generate")
    builder.add_edge("generate", "review")
    builder.add_edge("review", "approval")
    builder.add_conditional_edges("approval", _route, {"done": END})

    if settings.use_postgres_checkpointer:
        from langgraph.checkpoint.postgres import PostgresSaver

        # from_conn_string() is a context manager. Keep it open for the
        # lifetime of the application instead of storing the context manager
        # object itself (which has no setup/put/get methods).
        _exit_stack = ExitStack()
        _checkpointer = _exit_stack.enter_context(
            PostgresSaver.from_conn_string(settings.database_url)
        )
        _checkpointer.setup()
        _graph = builder.compile(checkpointer=_checkpointer)
    else:
        _exit_stack = None
        _checkpointer = None
        _graph = builder.compile()


def close_graph() -> None:
    global _graph, _checkpointer, _exit_stack

    if _exit_stack is not None:
        try:
            _exit_stack.close()
        except Exception:
            pass

    _graph = None
    _checkpointer = None
    _exit_stack = None


def create_draft(
    topic: str,
    platform: str,
    tone: str,
    brand_voice: str,
    thread_id: str,
) -> dict[str, Any]:
    if _graph is None:
        initialize_graph()
    return _graph.invoke(
        {
            "topic": topic,
            "platform": platform,
            "tone": tone,
            "brand_voice": brand_voice,
        },
        {"configurable": {"thread_id": thread_id}},
    )


def resume_approval(
    thread_id: str,
    decision: str,
    edited_content: str | None = None,
) -> dict[str, Any]:
    if _graph is None:
        initialize_graph()
    payload = {"decision": decision}
    if edited_content:
        payload["draft"] = edited_content
    return _graph.invoke(
        Command(resume=payload),
        {"configurable": {"thread_id": thread_id}},
    )
