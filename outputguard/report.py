from dataclasses import dataclass, field

from outputguard._diff import unified_diff
from outputguard.formats import format_label


@dataclass
class StrategyApplication:
    """Record of a single strategy being applied."""

    name: str
    changed: bool
    input_text: str
    output_text: str
    error: str | None = None

    @property
    def diff(self) -> str:
        """Unified diff of this strategy's changes."""
        if not self.changed:
            return ""
        return unified_diff(
            self.input_text,
            self.output_text,
            fromfile=f"before_{self.name}",
            tofile=f"after_{self.name}",
        )


@dataclass
class RepairReport:
    """Detailed report of a repair operation."""

    original_text: str
    final_text: str
    success: bool
    steps: list[StrategyApplication] = field(default_factory=list)
    parse_error: str | None = None
    format: str = "json"

    @property
    def candidate_text(self) -> str:
        """Last attempted text, including changes discarded after a failed repair."""
        return self.steps[-1].output_text if self.steps else self.final_text

    @property
    def strategies_applied(self) -> list[str]:
        """Names of strategies that actually changed the text."""
        return [s.name for s in self.steps if s.changed]

    @property
    def strategies_tried(self) -> list[str]:
        """Names of all strategies that were tried."""
        return [s.name for s in self.steps]

    @property
    def diff(self) -> str:
        """Unified diff from original to final text."""
        return unified_diff(
            self.original_text,
            self.final_text,
            fromfile="original",
            tofile="repaired",
        )

    @property
    def confidence(self) -> float:
        """Heuristic confidence score (0.0 to 1.0) for the repair.

        Higher when fewer strategies were needed and the change was minimal.
        """
        if not self.success:
            return 0.0

        applied_count = len(self.strategies_applied)

        if applied_count == 0:
            return 1.0  # No repair needed, already valid

        # Work in hundredths and round the exact ratio half up. Binary float
        # ties otherwise differ from JavaScript's rounding (e.g. 0.865).
        base = 100 - min(applied_count, 5) * 10
        orig_len = max(len(self.original_text), 1)
        final_len = max(len(self.final_text), 1)
        length = max(orig_len, final_len)
        change = min(abs(orig_len - final_len) * 50, length * 30)
        hundredths = (2 * (base * length - change) + length) // (2 * length)
        return max(hundredths, 10) / 100

    @property
    def summary(self) -> str:
        """One-line summary of the repair."""
        if not self.success:
            return f"Repair failed after trying {len(self.steps)} strategies"
        applied = self.strategies_applied
        if not applied:
            return f"No repair needed — {format_label(self.format)} was already valid"
        return f"Repaired using {len(applied)} strategy(ies): {', '.join(applied)}"

    def step_diffs(self) -> str:
        """Show changes and strategy errors, useful for --verbose."""
        parts = []
        for step in self.steps:
            if step.error is not None:
                parts.append(f"=== {step.name} ===\nError: {step.error}\n")
            elif step.changed:
                parts.append(f"=== {step.name} ===\n{step.diff}")
        return "\n".join(parts)
