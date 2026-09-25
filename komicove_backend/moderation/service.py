
from __future__ import annotations

from komicove_backend.moderation.analyzers.ai_analyzer import AIAnalyzer
from komicove_backend.moderation.analyzers.base import BaseAnalyzer
from komicove_backend.moderation.analyzers.metadata_rules import MetadataRulesAnalyzer
from komicove_backend.moderation.config import ModerationConfig
from komicove_backend.moderation.models import (
    AnalyzerFinding,
    ModerationResult,
    ModerationStatus,
    PublicationSubmission,
    RiskLevel,
)
from komicove_backend.moderation.storage import ModerationRecord, ModerationStore

_RISK_ORDER = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH]


class ModerationService:
    def __init__(
        self,
        store: ModerationStore,
        analyzers: list[BaseAnalyzer] | None = None,
        config: ModerationConfig | None = None,
    ):
        self._store = store
        self._config = config or ModerationConfig.from_env()


        self._analyzers = analyzers or [
            MetadataRulesAnalyzer(),
            AIAnalyzer(self._config),
        ]

    def review(self, submission: PublicationSubmission) -> tuple[ModerationResult, ModerationRecord]:
        findings: list[AnalyzerFinding] = []

        for analyzer in self._analyzers:
            if not analyzer.is_available():
                continue
            try:
                findings.append(analyzer.analyze(submission))
            except NotImplementedError:


                continue
            except Exception as exc:  # noqa: BLE001



                findings.append(
                    AnalyzerFinding(
                        analyzer_name=getattr(analyzer, "name", "unknown"),
                        risk_level=RiskLevel.LOW,
                        confidence=0.0,
                        reasons=[f"Analisador falhou durante a execução: {exc}"],
                    )
                )

        result = self._decide(submission, findings)
        record = self._store.save(result, publication_title=submission.title)
        return result, record

    def _decide(
        self, submission: PublicationSubmission, findings: list[AnalyzerFinding]
    ) -> ModerationResult:
        if not findings:


            return ModerationResult(
                submission_user_id=submission.user_id,
                status=ModerationStatus.PENDING_REVIEW,
                risk_level=RiskLevel.MEDIUM,
                confidence=0.0,
                internal_justification=(
                    "Nenhum analisador retornou resultado; enviado para "
                    "revisão manual por precaução."
                ),
                findings=[],
            )

        worst = max(findings, key=lambda f: _RISK_ORDER.index(f.risk_level))


        relevant = [f for f in findings if f.risk_level == worst.risk_level]
        confidence = max(f.confidence for f in relevant)

        status = self._status_from_risk(worst.risk_level, confidence)

        justification = " | ".join(
            f"[{f.analyzer_name}] {'; '.join(f.reasons)}" for f in findings
        )

        return ModerationResult(
            submission_user_id=submission.user_id,
            status=status,
            risk_level=worst.risk_level,
            confidence=confidence,
            internal_justification=justification,
            findings=findings,
        )

    def _status_from_risk(self, risk: RiskLevel, confidence: float) -> ModerationStatus:
        if risk == RiskLevel.HIGH and confidence >= self._config.auto_reject_threshold:
            return ModerationStatus.REJECTED
        if risk in (RiskLevel.MEDIUM, RiskLevel.HIGH):
            return ModerationStatus.PENDING_REVIEW
        if risk == RiskLevel.LOW and confidence < self._config.auto_pending_threshold:


            return ModerationStatus.PENDING_REVIEW
        return ModerationStatus.APPROVED
