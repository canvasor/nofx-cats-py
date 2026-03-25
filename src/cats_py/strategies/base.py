from __future__ import annotations

from abc import ABC, abstractmethod

from cats_py.domain.models import FeatureVector, SignalCandidate


class Strategy(ABC):
    name: str = "base"

    @abstractmethod
    def generate(self, feature: FeatureVector) -> SignalCandidate | None:
        raise NotImplementedError

    def skip_reason(self, feature: FeatureVector) -> str:
        return f"{self.name}: no candidate conditions met"
