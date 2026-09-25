
from __future__ import annotations

from komicove_backend.moderation.analyzers.base import BaseAnalyzer
from komicove_backend.moderation.known_works import KnownWorksRepository
from komicove_backend.moderation.models import (
    AnalyzerFinding,
    PublicationSubmission,
    RiskLevel,
)


TITLE_MATCH_THRESHOLD = 0.82



KNOWN_PUBLISHER_SIGNALS = {
    "marvel", "dc comics", "shueisha", "kodansha", "viz media",
    "mauricio de sousa", "panini", "image comics", "dark horse",
}


class MetadataRulesAnalyzer(BaseAnalyzer):
    name = "metadata_rules_v1"

    def __init__(self, known_works: KnownWorksRepository | None = None):
        self._known_works = known_works or KnownWorksRepository.from_env_or_seed()

    def analyze(self, submission: PublicationSubmission) -> AnalyzerFinding:
        reasons: list[str] = []
        signals: dict = {}
        risk = RiskLevel.LOW
        confidence = 0.4


        match = self._known_works.best_match(submission.title)
        if match:
            work, score = match
            signals["title_match"] = {"work": work.title, "score": round(score, 3)}
            if score >= TITLE_MATCH_THRESHOLD:
                risk = RiskLevel.HIGH
                confidence = 0.6
                reasons.append(
                    f"Título muito semelhante a obra conhecida cadastrada "
                    f"('{work.title}', editora/estúdio: {work.publisher or 'não informado'})."
                )
            elif score >= TITLE_MATCH_THRESHOLD - 0.15:
                risk = RiskLevel.MEDIUM
                confidence = 0.5
                reasons.append(
                    f"Título parcialmente semelhante a obra conhecida cadastrada "
                    f"('{work.title}')."
                )


        if not submission.authorship_declared and not submission.authorization_declared:
            reasons.append(
                "Usuário não declarou autoria nem autorização para publicação."
            )
            risk = _max_risk(risk, RiskLevel.MEDIUM)



        if submission.license:
            signals["license"] = submission.license
            reasons.append(f"Licença informada pelo usuário: '{submission.license}'.")


        embedded_publisher = str(
            submission.embedded_metadata.get("publisher", "")
        ).strip().lower()
        if embedded_publisher:
            signals["embedded_publisher"] = embedded_publisher
            if any(pub in embedded_publisher for pub in KNOWN_PUBLISHER_SIGNALS):
                risk = RiskLevel.HIGH
                confidence = 0.65
                reasons.append(
                    f"Metadado embutido no arquivo indica editora comercial: "
                    f"'{embedded_publisher}'."
                )

        if not reasons:
            reasons.append("Nenhum sinal de risco encontrado pelas regras v1.")

        return AnalyzerFinding(
            analyzer_name=self.name,
            risk_level=risk,
            confidence=confidence,
            reasons=reasons,
            matched_signals=signals,
        )


def _max_risk(a: RiskLevel, b: RiskLevel) -> RiskLevel:
    order = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH]
    return a if order.index(a) >= order.index(b) else b
