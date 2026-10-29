"""Immutable, predeclared one-dimension research scenarios; no parameter search."""

from dataclasses import dataclass
from types import MappingProxyType

from mft109.config import BASELINE


WEIGHTS = {
    "equal": (.25, .25, .25, .25),
    "momentum_tilt": (.40, .20, .20, .20),
    "low_volatility_tilt": (.20, .40, .20, .20),
    "liquidity_tilt": (.20, .20, .40, .20),
    "reversal_tilt": (.20, .20, .20, .40),
}
VALUES = {
    "top_n": (10, 20, 30, 50),
    "transaction_cost_bps": (0, 5, 10, 20),
    "rebalance_frequency": ("monthly", "quarterly"),
    "volatility_window": (20, 60, 120),
    "reversal_window": (5, 10, 20),
    "factor_weights": tuple(WEIGHTS),
}
BASE_VALUES = {"top_n": 20, "transaction_cost_bps": 10, "rebalance_frequency": "monthly",
               "volatility_window": 60, "reversal_window": 20, "factor_weights": "equal"}
WEIGHTS = MappingProxyType(WEIGHTS)
VALUES = MappingProxyType(VALUES)
BASE_VALUES = MappingProxyType(BASE_VALUES)


@dataclass(frozen=True)
class Scenario:
    """Exactly one named dimension and one approved value, never a combined grid."""

    experiment: str
    value: int | str

    def __post_init__(self) -> None:
        if (self.experiment not in VALUES or type(self.value) not in (int, str)
                or self.value not in VALUES[self.experiment]):
            raise ValueError("Expected one predeclared Phase 7 experiment/value")

    @property
    def name(self) -> str:
        return f"{self.experiment}:{self.value}"

    @property
    def is_baseline(self) -> bool:
        return self.value == BASE_VALUES[self.experiment]

    def parameter(self, name: str) -> int | str:
        """Return a full scenario setting without changing BASELINE or globals."""
        return self.value if name == self.experiment else BASE_VALUES[name]

    @property
    def top_n(self) -> int:
        return int(self.parameter("top_n"))

    @property
    def cost_rate(self) -> float:
        return int(self.parameter("transaction_cost_bps")) / 10000

    @property
    def quarterly(self) -> bool:
        return self.parameter("rebalance_frequency") == "quarterly"

    @property
    def weights(self) -> tuple[float, ...]:
        return WEIGHTS[str(self.parameter("factor_weights"))]


def approved_scenarios() -> tuple[Scenario, ...]:
    """21 ordered rows, including a baseline row inside each of the six groups."""
    return tuple(Scenario(group, value) for group, values in VALUES.items() for value in values)


def check_scenario(scenario: Scenario | None) -> None:
    """Reject implicit mappings/custom objects and baseline configuration drift."""
    if scenario is not None:
        if type(scenario) is not Scenario:
            raise TypeError("scenario must be an immutable approved Scenario")
        scenario.__post_init__()
        if (BASELINE.top_n, BASELINE.transaction_cost_rate, BASELINE.rebalance_frequency,
                BASELINE.volatility_lookback_days, BASELINE.reversal_lookback_days,
                BASELINE.momentum_weight, BASELINE.low_volatility_weight,
                BASELINE.liquidity_weight, BASELINE.reversal_weight) != (
                    20, .001, "monthly", 60, 20, .25, .25, .25, .25):
            raise ValueError("Approved baseline settings must remain unchanged")
