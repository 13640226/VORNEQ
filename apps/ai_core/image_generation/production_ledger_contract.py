"""Production image ledger contract: validation only, no charges or reservations.

Actual transactional reservations must be implemented in a separate audited PR.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ProductionImageBudget:
    project_micro_usd: int
    daily_micro_usd: int
    request_micro_usd: int

    def valid(self) -> bool:
        return (
            type(self.project_micro_usd) is int
            and type(self.daily_micro_usd) is int
            and type(self.request_micro_usd) is int
            and self.project_micro_usd == 5_000_000
            and self.daily_micro_usd == 200_000
            and 1 <= self.request_micro_usd <= 100_000
        )

    def permits_reservation(self, *, project_used: int, daily_used: int, amount: int) -> bool:
        """Conservative integer micro-dollar check; NOT an atomic ledger reservation."""
        return (
            self.valid()
            and all(type(v) is int and v >= 0 for v in (project_used, daily_used, amount))
            and 0 < amount <= self.request_micro_usd
            and project_used <= self.project_micro_usd
            and daily_used <= self.daily_micro_usd
            and amount <= self.project_micro_usd - project_used
            and amount <= self.daily_micro_usd - daily_used
        )


def production_image_ledger_ready() -> bool:
    """Must remain false until a separate transactional ledger is implemented."""
    return False
