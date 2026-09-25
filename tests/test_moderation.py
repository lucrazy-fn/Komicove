from komicove_backend.moderation.analyzers.metadata_rules import MetadataRulesAnalyzer
from komicove_backend.moderation.known_works import KnownWorksRepository
from komicove_backend.moderation.models import PublicationSubmission, RiskLevel


def _submission(**overrides):
    values = {
        "user_id": "user-1",
        "title": "Minha obra independente",
        "author": "Autora",
        "description": "",
        "authorship_declared": True,
    }
    values.update(overrides)
    return PublicationSubmission(**values)


def test_original_declared_work_is_low_risk():
    analyzer = MetadataRulesAnalyzer(KnownWorksRepository([]))
    assert analyzer.analyze(_submission()).risk_level == RiskLevel.LOW


def test_license_text_does_not_override_missing_authorization():
    analyzer = MetadataRulesAnalyzer(KnownWorksRepository([]))
    finding = analyzer.analyze(
        _submission(authorship_declared=False, license="qualquer texto")
    )
    assert finding.risk_level == RiskLevel.MEDIUM


def test_known_commercial_title_is_high_risk():
    analyzer = MetadataRulesAnalyzer()
    finding = analyzer.analyze(_submission(title="Batman"))
    assert finding.risk_level == RiskLevel.HIGH
