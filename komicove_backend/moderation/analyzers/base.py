
from __future__ import annotations

from abc import ABC, abstractmethod

from komicove_backend.moderation.models import AnalyzerFinding, PublicationSubmission


class BaseAnalyzer(ABC):
    pass


    name: str = "base"

    @abstractmethod
    def analyze(self, submission: PublicationSubmission) -> AnalyzerFinding:
        pass
        raise NotImplementedError

    def is_available(self) -> bool:
        pass
        return True
