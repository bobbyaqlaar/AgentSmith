"""The moderation hook this tenant declares.

The result is declared here because this app does not install `agentsmith`; a
tenant whose code imports it pins `agentsmith-runtime` in its requirements.
"""

from dataclasses import dataclass, field


@dataclass
class ModerationResult:
    allowed: bool
    reasons: list[str] = field(default_factory=list)


def classify_output(text: str) -> ModerationResult:
    return ModerationResult(allowed=True)
