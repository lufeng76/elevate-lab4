"""HR Policy Agent — entry point.

The runner/session/CLI plumbing below is GIVEN. Your job is the one marked block:
build the `root_agent`. You will also implement the tools it uses
(agent/tools/*.py) and its instructions (agent/prompt.py).

Run it:
    uv run python -m agent.agent "How many days of paid outpatient sick leave do I get?"
    uv run python -m agent.agent --interactive
    uv run adk web .            # then pick "agent" in the web UI
"""
import asyncio
import logging
import sys

from google.adk.agents import LlmAgent  # noqa: F401  (used in the TODO block)

from . import config
from .prompt import POLICY_AGENT_PROMPT

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# GIVEN: tool selection. Picks the retrieval "brain" based on RETRIEVAL_MODE.
# ---------------------------------------------------------------------------
def select_tools(mode: str):
    """Return the list of tool callables for the given retrieval mode."""
    tools = []
    if mode in ("okf", "hybrid"):
        from .tools.okf_tool import list_concepts, read_concept
        tools += [list_concepts, read_concept]
    if mode in ("rag", "hybrid"):
        from .tools.rag_tool import search_policy_docs
        tools += [search_policy_docs]
    if not tools:
        raise ValueError(f"Unknown RETRIEVAL_MODE: {mode!r} (use okf | rag | hybrid)")

    # Enterprise Systems Integration via Google ADK McpToolset (WorkWeek + ServiceImmediately)
    from .tools.mcp_tool import get_mcp_toolsets
    tools.extend(get_mcp_toolsets())

    return tools



# ===========================================================================
# TODO(you): Build the HR Policy Agent.
#
# Construct an ADK LlmAgent and assign it to `root_agent`. It should use:
#   - model:       config.GEMINI_MODEL
#   - name:        a short identifier, e.g. "hr_policy_agent"
#   - description: one line describing what it does
#   - instruction: POLICY_AGENT_PROMPT  (you write this in agent/prompt.py)
#   - tools:       select_tools(config.RETRIEVAL_MODE)
#
# HINT: from google.adk.agents import LlmAgent  (already imported above)
#       root_agent = LlmAgent(model=..., name=..., description=..., instruction=..., tools=...)
#
# Suggested coding-agent prompt:
#   "In agent/agent.py, build an ADK LlmAgent named hr_policy_agent using
#    config.GEMINI_MODEL, POLICY_AGENT_PROMPT as the instruction, and
#    select_tools(config.RETRIEVAL_MODE) as its tools. Assign it to root_agent."
# ===========================================================================
root_agent = LlmAgent(
    model=config.GEMINI_MODEL,
    name="hr_policy_agent",
    description="Altostrat Singapore HR Policy Assistant that answers employee questions grounded in the handbook.",
    instruction=POLICY_AGENT_PROMPT,
    tools=select_tools(config.RETRIEVAL_MODE),
)


# ---------------------------------------------------------------------------
# GIVEN: a tiny CLI runner so you can talk to the agent from the terminal.
# ---------------------------------------------------------------------------
_session_service = None


def _ensure_runner():
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    global _session_service
    if root_agent is None:
        raise SystemExit(
            "root_agent is None — implement the TODO block in agent/agent.py first."
        )
    if _session_service is None:
        _session_service = InMemorySessionService()
    return Runner(app_name=config.APP_NAME, agent=root_agent, session_service=_session_service)


async def _ensure_session_async(user_id, session_id):
    """Ensure the session exists via the async API, avoiding silent failures and preserving traces."""
    from google.adk.errors.already_exists_error import AlreadyExistsError

    # First verify if session already exists
    session = await _session_service.get_session(
        app_name=config.APP_NAME, user_id=user_id, session_id=session_id
    )
    if session is not None:
        return session

    try:
        return await _session_service.create_session(
            app_name=config.APP_NAME, user_id=user_id, session_id=session_id
        )
    except AlreadyExistsError:
        logger.debug(
            "Session %s for user %s already exists in %s.",
            session_id,
            user_id,
            config.APP_NAME,
        )
        return await _session_service.get_session(
            app_name=config.APP_NAME, user_id=user_id, session_id=session_id
        )
    except Exception as e:
        logger.error(
            "Failed to initialize session %s for user %s in %s: %s",
            session_id,
            user_id,
            config.APP_NAME,
            e,
            exc_info=True,
        )
        raise


async def _run_query_traced_async(query, user_id, session_id):
    import time
    from google.genai import types

    from .security import (
        AuditLogger,
        GroundingEvaluator,
        IdentityContextInjector,
        InputSafetyFilter,
        OutputSafetyFilter,
    )

    start_time = time.perf_counter()

    # 1. Identity context extraction & revocation check (SDD 6.1.1 & 9.1.1)
    if IdentityContextInjector.is_revoked(user_id):
        refusal = "Authentication session expired or revoked. Please re-authenticate."
        AuditLogger.emit(
            session_id=session_id,
            user_id=user_id,
            action_type="SECURITY_REVOCATION_BLOCK",
            payload={"query": query},
            status="BLOCKED",
            latency_ms=(time.perf_counter() - start_time) * 1000,
        )
        return refusal, []

    IdentityContextInjector.create_context(user_id=user_id, session_id=session_id)

    # 2. Input Safety Guardrail (SDD 4.2.1 - prompt injection / boundary scan)
    input_filter = InputSafetyFilter()
    input_check = input_filter.validate(query, user_id=user_id)
    if not input_check.is_safe:
        refusal = input_check.sanitized_output or "Request blocked by safety policy."
        AuditLogger.emit(
            session_id=session_id,
            user_id=user_id,
            action_type="SECURITY_INPUT_BLOCK",
            payload={"query": query, "reason": input_check.reason},
            safety_evaluation={"input_guard_passed": False, "violation": input_check.violation_category},
            status="BLOCKED",
            latency_ms=(time.perf_counter() - start_time) * 1000,
        )
        return refusal, []

    # 3. Agent Reasoning & Tool Loop
    runner = _ensure_runner()
    await _ensure_session_async(user_id, session_id)
    message = types.Content(role="user", parts=[types.Part(text=query)])
    final = ""
    evidence = []
    async for event in runner.run_async(
        user_id=user_id, session_id=session_id, new_message=message
    ):
        if not (event.content and event.content.parts):
            continue
        for part in event.content.parts:
            fr = getattr(part, "function_response", None)
            if fr is not None:
                evidence.append({"tool": getattr(fr, "name", "?"), "payload": fr.response})
        if event.is_final_response() and event.content.parts:
            texts = [p.text for p in event.content.parts if getattr(p, "text", None)]
            if texts:
                final = "\n".join(texts)

    # 4. Grounding Verification Layer (SDD 4.2.2 & NFR-3.1)
    grounding_eval = GroundingEvaluator()
    grounding_res = grounding_eval.evaluate(final, evidence)

    # 5. Output Safety Guardrail & SPII Redaction (SDD 4.2.2 & 4.3.2)
    output_filter = OutputSafetyFilter()
    output_check = output_filter.validate(final)
    sanitized_final = (
        output_check.sanitized_output if output_check.sanitized_output is not None else final
    )

    # 6. Structured Immutable Audit Telemetry (SDD 9.2)
    latency = (time.perf_counter() - start_time) * 1000
    AuditLogger.emit(
        session_id=session_id,
        user_id=user_id,
        action_type="USER_TURN_COMPLETED",
        payload={"query": query, "response": sanitized_final},
        safety_evaluation={
            "input_guard_passed": True,
            "output_guard_passed": output_check.is_safe,
            "grounding_score": grounding_res.score,
            "is_grounded": grounding_res.is_grounded,
        },
        status="SUCCESS" if output_check.is_safe else "BLOCKED",
        latency_ms=latency,
    )

    return sanitized_final, evidence


def run_query(query: str, user_id: str = "learner", session_id: str = "session-1") -> str:
    answer, _evidence = run_query_traced(query, user_id=user_id, session_id=session_id)
    return answer


def run_query_traced(query: str, user_id: str = "learner", session_id: str = "session-1"):
    """Like run_query, but also returns the evidence the agent retrieved.

    Returns (answer, evidence) where evidence is a list of
    {"tool": <tool name>, "payload": <the tool's return value>} — i.e. exactly
    what each retrieval tool handed back to the model. The eval harness uses this
    to check *grounding* (did the answer stick to what was retrieved?).

    Drives the async ADK APIs (run_async + async create_session) under
    asyncio.run, so callers stay synchronous without hitting the deprecated
    sync Runner.run / *_sync session methods.
    """
    return asyncio.run(_run_query_traced_async(query, user_id, session_id))


def _interactive():
    print(f"HR Policy Agent [{config.RETRIEVAL_MODE}] — type 'exit' to quit.")
    while True:
        try:
            q = input("\nyou > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if q.lower() in {"exit", "quit"}:
            break
        if q:
            print(f"\nagent > {run_query(q)}")


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if argv and argv[0] == "--interactive":
        _interactive()
    elif argv:
        print(run_query(" ".join(argv)))
    else:
        print('Usage: uv run python -m agent.agent "<question>"  |  --interactive')


if __name__ == "__main__":
    main()
