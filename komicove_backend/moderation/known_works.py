
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from difflib import SequenceMatcher


@dataclass(frozen=True)
class KnownWork:
    title: str
    publisher: str = ""
    aliases: tuple[str, ...] = ()




_SEED_KNOWN_WORKS: list[KnownWork] = [
    KnownWork("Batman", "DC Comics"),
    KnownWork("Spider-Man", "Marvel", aliases=("Homem-Aranha",)),
    KnownWork("One Piece", "Shueisha"),
    KnownWork("Naruto", "Shueisha"),
    KnownWork("Dragon Ball", "Shueisha"),
    KnownWork("Turma da Mônica", "Mauricio de Sousa Produções"),
]


class KnownWorksRepository:
    pass

    def __init__(self, works: list[KnownWork] | None = None):
        self._works = works if works is not None else list(_SEED_KNOWN_WORKS)

    @classmethod
    def from_env_or_seed(cls) -> "KnownWorksRepository":
        pass
        path = os.environ.get("KNOWN_WORKS_FILE")
        if path and os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            works = [
                KnownWork(
                    title=item["title"],
                    publisher=item.get("publisher", ""),
                    aliases=tuple(item.get("aliases", [])),
                )
                for item in raw
            ]
            return cls(works)
        return cls()

    def best_match(self, text: str) -> tuple[KnownWork, float] | None:
        pass
        if not text or not self._works:
            return None

        text_norm = text.strip().lower()
        best: tuple[KnownWork, float] | None = None

        for work in self._works:
            candidates = (work.title, *work.aliases)
            for candidate in candidates:
                score = SequenceMatcher(None, text_norm, candidate.lower()).ratio()
                if best is None or score > best[1]:
                    best = (work, score)

        return best
