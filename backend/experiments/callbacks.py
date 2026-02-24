"""
Callbacks for agent runs (e.g. logging LLM output to console).
"""
from __future__ import annotations

from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from experiments.log_config import log

# Number of words to show in the console for each agent's output
OUTPUT_LOG_WORD_LIMIT = 50


def _first_n_words(text: str, n: int) -> tuple[str, int]:
    """Return (first n words, total word count)."""
    if not text or not isinstance(text, str):
        return "", 0
    words = text.split()
    total = len(words)
    first = " ".join(words[:n]) if words else ""
    return first, total


class AgentOutputLoggingCallback(BaseCallbackHandler):
    """Logs the first N words of each LLM response to the console for debugging."""

    def __init__(self, word_limit: int = OUTPUT_LOG_WORD_LIMIT) -> None:
        self.word_limit = word_limit

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        **kwargs: object,
    ) -> None:
        """Log first N words of the model output. Example: 'model responded with: ... 100 more words'."""
        if not response.generations:
            return
        # Flatten: generations is list[list[Generation]]
        run_name = (tags or [None])[0] if tags else None
        if not run_name and kwargs:
            run = kwargs.get("run")
            if run is not None and hasattr(run, "name"):
                run_name = getattr(run, "name", None)
        label = f"[{run_name}] " if run_name else ""

        for gen_list in response.generations:
            for gen in gen_list:
                text = getattr(gen, "text", None)
                if text is None and hasattr(gen, "message"):
                    msg = getattr(gen, "message", None)
                    text = getattr(msg, "content", None)
                    if isinstance(text, list):
                        text = " ".join(
                            b.get("text", b) if isinstance(b, dict) else str(b)
                            for b in text
                        )
                text = str(text).strip() if text else ""
                if not text:
                    continue
                first, total = _first_n_words(str(text), self.word_limit)
                if total <= self.word_limit:
                    log.info(
                        "{}model responded with ({} words): {}",
                        label,
                        total,
                        first or "(empty)",
                    )
                else:
                    more = total - self.word_limit
                    log.info(
                        "{}model responded with: {} ... {} more words",
                        label,
                        first,
                        more,
                    )
