"""
LLM runner for stub implementations (first draft).
Uses LangChain ChatGoogleGenerativeAI (Gemini) with structured output. Replace with programmable logic later.
Set GOOGLE_API_KEY in the environment.
"""
from typing import TypeVar

from pydantic import BaseModel

from experiments.log_config import log

T = TypeVar("T", bound=BaseModel)


def run_structured(
    task_description: str,
    context: str,
    output_model: type[T],
    model_name: str = "gemini-2.5-flash",
) -> T:
    """
    Invoke an LLM with the given task and context; parse response into output_model.
    Used by stubs for PoC; replace with deterministic logic when moving to production.
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
    try:
        result = structured_llm.invoke(message)
        log.debug("run_structured completed output_model={}", output_model.__name__)
        return result
    except Exception as e:
        log.exception("run_structured failed model={} output_model={}", model_name, output_model.__name__)
        raise
