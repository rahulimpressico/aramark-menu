"""
LLM runner for stub implementations (first draft).
Uses LangChain ChatGoogleGenerativeAI (Gemini) with structured output. Replace with programmable logic later.
Set GOOGLE_API_KEY in the environment.
Token usage is accumulated per request; use get_usage_summary() / clear_usage().
"""
from __future__ import annotations

import json
from contextvars import ContextVar
from typing import Any, TypeVar

from pydantic import BaseModel

from experiments.log_config import log

T = TypeVar("T", bound=BaseModel)

_usage_records: ContextVar[list[dict[str, int]]] = ContextVar("llm_usage_records", default=[])


def _get_usage_from_message(msg: Any) -> tuple[int, int]:
    meta = getattr(msg, "response_metadata", None) or {}
    usage = meta.get("usage_metadata") or meta.get("usage") or getattr(msg, "usage_metadata", None) or {}
    if not isinstance(usage, dict):
        usage = {}
    inp = (
        usage.get("promptTokenCount")
        or usage.get("input_token_count")
        or usage.get("prompt_tokens")
        or usage.get("input_tokens")
        or 0
    )
    out = (
        usage.get("candidatesTokenCount")
        or usage.get("output_token_count")
        or usage.get("completion_tokens")
        or usage.get("output_tokens")
        or 0
    )
    if not out and usage.get("totalTokenCount"):
        out = max(0, int(usage.get("totalTokenCount", 0)) - int(inp))
    if not out and usage.get("total_tokens"):
        out = max(0, int(usage.get("total_tokens", 0)) - int(inp))
    return (int(inp), int(out))


def _append_usage(input_tokens: int, output_tokens: int) -> None:
    try:
        records = _usage_records.get()
    except LookupError:
        records = []
    records.append({"input_tokens": input_tokens, "output_tokens": output_tokens})
    _usage_records.set(records)


def get_usage_summary() -> dict[str, Any]:
    """Total input/output tokens and cost for current request. Does not clear; call clear_usage() to reset."""
    try:
        records = _usage_records.get()
    except LookupError:
        records = []
    total_in = sum(r.get("input_tokens", 0) for r in records)
    total_out = sum(r.get("output_tokens", 0) for r in records)
    from experiments.report_format import estimate_cost_usd
    return {
        "total_input_tokens": total_in,
        "total_output_tokens": total_out,
        "cost_usd": round(estimate_cost_usd(total_in, total_out), 4),
        "call_count": len(records),
    }


def clear_usage() -> None:
    _usage_records.set([])


def run_structured(
    task_description: str,
    context: str,
    output_model: type[T],
    model_name: str = "gemini-2.5-flash",
) -> T:
    """
    Invoke an LLM with the given task and context; parse response into output_model.
    Accumulates token usage; use get_usage_summary() after the run.
    """
    log.debug("run_structured model={} output_model={}", model_name, output_model.__name__)
    from langchain_google_genai import ChatGoogleGenerativeAI
    llm = ChatGoogleGenerativeAI(model=model_name, temperature=0)
    message = f"""## Task
{task_description}

## Context / Input
{context}

Respond with a single JSON object that conforms to the output schema. Be concise and factual."""
    try:
        raw_msg = llm.invoke(message)
        inp, out = _get_usage_from_message(raw_msg)
        _append_usage(inp, out)
        log.debug("run_structured usage input={} output={}", inp, out)
        content = raw_msg.content
        if isinstance(content, list):
            parts = []
            for p in content:
                if isinstance(p, str):
                    parts.append(p)
                elif isinstance(p, dict):
                    inner = p.get("parts")
                    if isinstance(inner, list):
                        for part in inner:
                            if isinstance(part, str):
                                parts.append(part)
                            elif isinstance(part, dict):
                                parts.append(part.get("text") or part.get("content") or "")
                            else:
                                parts.append(getattr(part, "text", None) or getattr(part, "content", None) or str(part))
                    else:
                        parts.append(p.get("text") or p.get("content") or "")
                else:
                    parts.append(getattr(p, "text", None) or getattr(p, "content", None) or str(p))
            text = "".join(parts)
        else:
            text = content or ""
        text = (text or "").strip()
        for start in ("```json", "```"):
            if start in text:
                i = text.find(start) + len(start)
                if start == "```":
                    idx = text.find("```")
                    i = text.find("\n", idx) + 1 if idx != -1 else i
                j = text.find("```", i)
                if j != -1:
                    text = text[i:j].strip()
                break
        try:
            data = json.loads(text) if text else {}
        except json.JSONDecodeError:
            # LLM sometimes returns plain markdown instead of JSON (e.g. report formatting)
            fields = getattr(output_model, "model_fields", None) or getattr(output_model, "__fields__", {})
            if "full_markdown" in fields:
                data = {f: "" for f in fields}
                data["full_markdown"] = text
                log.debug("run_structured: response was markdown, using as full_markdown")
            else:
                raise
        result = output_model.model_validate(data)
        log.debug("run_structured completed output_model={}", output_model.__name__)
        return result
    except Exception as e:
        log.exception("run_structured failed model={} output_model={}", model_name, output_model.__name__)
        raise
