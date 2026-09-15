"""Question answering over an already-ingested evidence pack.

No new model: this reuses the same resident brain the artefact agents use, through the
same `LlamaClient`. No retrieval: the whole dossier text goes in the prompt verbatim,
exactly as `ArtefactAgent` does for generation. No persistence as a transform: nothing
here touches `Store` or writes a manifest -- see `api/routes/ask.py` for the two ways a
caller supplies a dossier (an existing transform, or an in-memory session).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

MAX_TOKENS = 700
TEMPERATURE = 0.2

_SYSTEM_TEMPLATE = (
    "You are Rupantar, an offline analyst engine. Answer the operator's question about "
    "material already ingested into an evidence pack. Every unit of evidence below is "
    "tagged [En]. Answer using only facts stated in the evidence pack below, and cite "
    "every claim with the [En] tag(s) it comes from. If the evidence pack does not cover "
    "the question, say so plainly instead of guessing or drawing on outside knowledge.\n\n"
    "# EVIDENCE PACK\n{dossier_text}"
)


class StreamClient(Protocol):
    """The subset of `LlamaClient` this module depends on."""

    def stream(
        self, messages: list[dict[str, str]], *, max_tokens: int, temperature: float
    ) -> AsyncIterator[str]:
        """Yield content deltas for `messages`."""


def build_messages(dossier_text: str, question: str) -> list[dict[str, str]]:
    """System turn carries the evidence pack; the user turn is only the question."""
    system = _SYSTEM_TEMPLATE.format(dossier_text=dossier_text or "(no evidence was ingested)")
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": question},
    ]


async def answer_stream(
    dossier_text: str, question: str, client: StreamClient
) -> AsyncIterator[str]:
    """Yield answer text deltas grounded only in `dossier_text`."""
    messages = build_messages(dossier_text, question)
    async for delta in client.stream(messages, max_tokens=MAX_TOKENS, temperature=TEMPERATURE):
        yield delta
