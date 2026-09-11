from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from statistics import median
from typing import Sequence


@dataclass(frozen=True)
class VerificationDecision:
    caught: bool
    release_ratio: float
    median_assessment: float
    instantaneous_deviation: float
    adaptive_threshold: float
    cumulative_drift: float
    reason: str


class VerificationNetworkV2:
    """Research-only adaptive evidence verifier.

    Distilled from the legacy fixed-threshold verifier. V1 caught gross fraud but
    systematically passed smaller repeated overclaims. V2 combines a robust
    median/MAD instantaneous check with claimant-specific cumulative EWMA drift.

    This class provides evidence scoring only. It grants no network, financial,
    validator, accounting or treasury authority.
    """

    def __init__(
        self,
        bond_ratio: float = 0.35,
        min_instant_threshold: float = 0.12,
        max_instant_threshold: float = 0.30,
        cumulative_threshold: float = 0.045,
        drift_alpha: float = 0.35,
    ):
        self.bond_ratio = bond_ratio
        self.min_instant_threshold = min_instant_threshold
        self.max_instant_threshold = max_instant_threshold
        self.cumulative_threshold = cumulative_threshold
        self.drift_alpha = drift_alpha
        self._drift = defaultdict(float)

    @staticmethod
    def _robust_noise_ratio(values: Sequence[float], med: float) -> float:
        if med <= 0:
            return 0.0
        mad = median([abs(v - med) for v in values])
        return mad / med

    def verify(
        self,
        claimant_id: str,
        claimed_delta: float,
        assessments: Sequence[float],
        posted_bond: float,
    ) -> VerificationDecision:
        if claimed_delta < 0 or not assessments:
            raise ValueError("invalid claim")

        values = [max(0.0, float(v)) for v in assessments]
        med = median(values)
        required_bond = claimed_delta * self.bond_ratio
        coverage = 1.0 if required_bond <= 0 else min(1.0, posted_bond / required_bond)
        effective_claim = claimed_delta * coverage
        deviation = 0.0 if med <= 1e-12 else (effective_claim - med) / med

        noise = self._robust_noise_ratio(values, med)
        adaptive_threshold = min(
            self.max_instant_threshold,
            max(self.min_instant_threshold, 4.0 * noise + 0.03),
        )

        prior = self._drift[claimant_id]
        drift = self.drift_alpha * max(0.0, deviation) + (1.0 - self.drift_alpha) * prior
        self._drift[claimant_id] = drift

        insufficient_bond = coverage < 0.999999
        instant = deviation > adaptive_threshold
        cumulative = drift > self.cumulative_threshold
        caught = insufficient_bond or instant or cumulative

        if caught:
            release_ratio = min(coverage, 1.0 if claimed_delta <= 1e-12 else med / claimed_delta)
            reason = (
                "insufficient_bond"
                if insufficient_bond
                else "instant_deviation"
                if instant
                else "cumulative_drift"
            )
        else:
            release_ratio = coverage
            reason = "accepted"

        return VerificationDecision(
            caught=caught,
            release_ratio=max(0.0, min(1.0, release_ratio)),
            median_assessment=med,
            instantaneous_deviation=deviation,
            adaptive_threshold=adaptive_threshold,
            cumulative_drift=drift,
            reason=reason,
        )
