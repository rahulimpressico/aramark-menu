"""
LLM runner for stub implementations (first draft).
Uses LangChain ChatGoogleGenerativeAI (Gemini) with structured output. Replace with programmable logic later.
Set GOOGLE_API_KEY in the environment.

Tracing: When run_structured is called from inside an agent run (e.g. from tools), the current
RunnableConfig (including Langfuse callbacks) is read from LangChain's context and passed to the
LLM invoke so every tool-internal LLM call is traced in Langfuse for debugging.
"""
from typing import TypeVar

from pydantic import BaseModel

from experiments.log_config import log

T = TypeVar("T", bound=BaseModel)


def _get_inherited_config():
    """Get the current run's config from LangChain context so tool-internal LLM calls are traced."""
    try:
        from langchain_core.runnables.config import var_child_runnable_config

        return var_child_runnable_config.get()
    except Exception:
        return None


def _get_langfuse_config_for_standalone():
    """
    When run_structured is called outside an agent run, use a Langfuse callback so the LLM call
    is still traced (e.g. in tests or scripts). Returns a config dict or None if Langfuse unavailable.
    """
    try:
        from langfuse.langchain import CallbackHandler

        return {"callbacks": [CallbackHandler()]}
    except Exception:
        return None


def run_structured(
    task_description: str,
    context: str,
    output_model: type[T],
    model_name: str = "gemini-2.5-flash",
) -> T:
    """
    Invoke an LLM with the given task and context; parse response into output_model.
    Used by stubs for PoC; replace with deterministic logic when moving to production.
    When called from within an agent run, inherits the run's config (e.g. Langfuse callbacks)
    so this LLM call is traced in Langfuse.
    """
    log.debug("run_structured model={} output_model={}", model_name, output_model.__name__)
    from langchain_google_genai import ChatGoogleGenerativeAI

    llm = ChatGoogleGenerativeAI(model=model_name, temperature=0)
    structured_llm = llm.with_structured_output(output_model)
    message = f"""## Task
{task_description}

## Context / Input
{context}

Respond with a single JSON object that conforms to the output schema. Be concise and factual."""
    run_config = _get_inherited_config()
    if not run_config:
        run_config = _get_langfuse_config_for_standalone()
    if run_config:
        log.debug("run_structured using config for tracing (e.g. Langfuse)")
    try:
        if run_config:
            result = structured_llm.invoke(message, config=run_config)
        else:
            result = structured_llm.invoke(message)
        log.debug("run_structured completed output_model={}", output_model.__name__)
        return result
    except Exception as e:
        log.exception("run_structured failed model={} output_model={}", model_name, output_model.__name__)
        raise
