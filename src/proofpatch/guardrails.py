"""Machine-enforced incident limits. Prices are supplied by the operator in USD per million tokens."""

import time
from decimal import Decimal, InvalidOperation


class BudgetExceeded(ValueError):
    pass


class CostBudget:
    def __init__(self, limit="0.50", input_rate=None, output_rate=None):
        try:
            self.limit = Decimal(str(limit))
            self.input_rate = Decimal(str(input_rate))
            self.output_rate = Decimal(str(output_rate))
        except InvalidOperation as error:
            raise ValueError("Budget and both model prices must be decimal numbers") from error
        if not all(x.is_finite() for x in (self.limit, self.input_rate, self.output_rate)):
            raise ValueError("Budget and model prices must be finite")
        if self.limit <= 0 or self.input_rate < 0 or self.output_rate < 0:
            raise ValueError("Budget must be positive and prices cannot be negative")
        if not self.input_rate and not self.output_rate:
            raise ValueError("At least one model price must be positive")
        self.spent = Decimal(0)

    def quote(self, input_bytes: int, max_output_tokens: int) -> Decimal:
        # Every UTF-8 token uses at least one byte. Extra room covers request framing
        # and structured-output schema overhead not present in the supplied JSON.
        maximum_input_tokens = input_bytes + 8192
        return (
            Decimal(maximum_input_tokens) * self.input_rate
            + Decimal(max_output_tokens) * self.output_rate
        ) / Decimal(1_000_000)

    def reserve(self, quote: Decimal) -> None:
        if self.spent + quote > self.limit:
            raise BudgetExceeded(
                f"LLM budget cap would be exceeded: ${self.spent + quote:.4f} > ${self.limit:.4f}"
            )

    def charge(self, reserved: Decimal, usage: dict | None) -> Decimal:
        if (
            usage
            and isinstance(usage.get("input_tokens"), int)
            and isinstance(usage.get("output_tokens"), int)
        ):
            actual = (
                Decimal(usage["input_tokens"]) * self.input_rate
                + Decimal(usage["output_tokens"]) * self.output_rate
            ) / Decimal(1_000_000)
            charge = max(actual, Decimal(0))
        else:
            charge = reserved
        self.spent += charge
        return charge

    def ensure_within_cap(self) -> None:
        if self.spent > self.limit:
            raise BudgetExceeded(f"LLM budget cap exceeded after billing: ${self.spent:.4f}")

    def restore(self, entries: list[dict]) -> None:
        self.spent = sum(
            (Decimal(str(e.get("cost_usd", e.get("reserved_usd", "0")))) for e in entries),
            Decimal(0),
        )

    def report(self) -> dict:
        return {
            "limit_usd": float(self.limit),
            "charged_usd": float(self.spent),
            "input_usd_per_million": float(self.input_rate),
            "output_usd_per_million": float(self.output_rate),
            "basis": "operator-supplied rates; missing usage charged at full reservation",
        }


class Deadline:
    def __init__(self, seconds: float, elapsed: float = 0):
        if seconds <= 0:
            raise ValueError("Incident deadline must be positive")
        self.seconds = seconds
        self.started = time.monotonic() - elapsed

    def remaining(self) -> float:
        left = self.seconds - (time.monotonic() - self.started)
        if left <= 0:
            raise TimeoutError("Incident deadline reached")
        return left

    def elapsed(self) -> float:
        return time.monotonic() - self.started
