
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ModerationConfig:

    auto_reject_threshold: float = 0.6
    auto_pending_threshold: float = 0.3


    ai_provider: str = ""
    ai_api_key: str = ""

    @classmethod
    def from_env(cls) -> "ModerationConfig":
        return cls(
            auto_reject_threshold=float(
                os.environ.get("MODERATION_AUTO_REJECT_THRESHOLD", 0.6)
            ),
            auto_pending_threshold=float(
                os.environ.get("MODERATION_AUTO_PENDING_THRESHOLD", 0.3)
            ),
            ai_provider=os.environ.get("MODERATION_AI_PROVIDER", ""),
            ai_api_key=os.environ.get("MODERATION_AI_API_KEY", ""),
        )
