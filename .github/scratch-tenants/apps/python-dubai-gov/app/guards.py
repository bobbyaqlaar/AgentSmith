"""The moderation hook this tenant declares."""

from agentsmith.moderation import ModerationResult


def classify_output(text: str) -> ModerationResult:
    return ModerationResult(allowed=True)
