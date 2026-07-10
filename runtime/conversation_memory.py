"""
runtime/conversation_memory.py — short-term token-window message buffer.

Keeps a chat-style message list under a configurable token budget.
Eviction: drop oldest messages first until under budget (summarization is v2).

Usage:
    mem = ConversationMemory(token_budget=4000)
    mem.add("user", "Hello")
    messages = mem.as_messages()  # for llm_gateway.complete(messages)
"""

from __future__ import annotations

from typing import Any


def _count_tokens(text: str, encoding_name: str = "cl100k_base") -> int:
    try:
        import tiktoken

        enc = tiktoken.get_encoding(encoding_name)
        return len(enc.encode(text))
    except Exception:
        # Fallback: ~4 chars per token
        return max(1, len(text) // 4)


class ConversationMemory:
    """In-process short-term memory with truncate-oldest eviction."""

    def __init__(
        self,
        token_budget: int = 4000,
        encoding_name: str = "cl100k_base",
    ) -> None:
        if token_budget < 1:
            raise ValueError("token_budget must be >= 1")
        self.token_budget = token_budget
        self.encoding_name = encoding_name
        self._messages: list[dict[str, Any]] = []

    @property
    def messages(self) -> list[dict[str, Any]]:
        return list(self._messages)

    def add(self, role: str, content: str, **extra: Any) -> None:
        msg: dict[str, Any] = {"role": role, "content": content}
        msg.update(extra)
        self._messages.append(msg)
        self._evict()

    def as_messages(self) -> list[dict[str, Any]]:
        return [{"role": m["role"], "content": m["content"]} for m in self._messages]

    def token_count(self) -> int:
        return sum(
            _count_tokens(str(m.get("content", "")), self.encoding_name)
            for m in self._messages
        )

    def clear(self) -> None:
        self._messages.clear()

    def _evict(self) -> None:
        while len(self._messages) > 1 and self.token_count() > self.token_budget:
            self._messages.pop(0)
        # If a single message still exceeds budget, keep it (cannot shrink further
        # without summarization — v2).
