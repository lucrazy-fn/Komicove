
from __future__ import annotations

from komicove_backend.moderation.analyzers.base import BaseAnalyzer
from komicove_backend.moderation.config import ModerationConfig
from komicove_backend.moderation.models import (
    AnalyzerFinding,
    PublicationSubmission,
    RiskLevel,
)


class AIAnalyzer(BaseAnalyzer):
    name = "ai_analyzer_v0"

    def __init__(self, config: ModerationConfig | None = None):
        self._config = config or ModerationConfig.from_env()

    def is_available(self) -> bool:


        return bool(self._config.ai_api_key)

    def analyze(self, submission: PublicationSubmission) -> AnalyzerFinding:
        if not self.is_available():
            return AnalyzerFinding(
                analyzer_name=self.name,
                risk_level=RiskLevel.LOW,
                confidence=0.0,
                reasons=["Analisador de IA não configurado (sem chave de API); ignorado."],
            )






        raise NotImplementedError(
            "AIAnalyzer ainda não está implementado: isto é só a estrutura "
            "para o service.py conseguir plugar um analisador de IA no "
            "futuro sem exigir mudanças em outros arquivos."
        )
