from dataclasses import dataclass, field
from difflib import unified_diff


@dataclass
class StrategyApplication:
    """Record of a single strategy being applied."""

    name: str
    changed: bool
    input_text: str
    output_text: str

    @property
    def diff(self) -> str:
        """Unified diff of this strategy's changes."""
        if not self.changed:
            return ""
        return "\n".join(
            unified_diff(
                self.input_text.splitlines(keepends=True),
                self.output_text.splitlines(keepends=True),
                fromfile=f"before_{self.name}",
                tofile=f"after_{self.name}",
                lineterm="",
            )
        )


@dataclass
class RepairReport:
    """Detailed report of a repair operation."""

    original_text: str
    final_text: str
    success: bool
    steps: list[StrategyApplication] = field(default_factory=list)
    parse_error: str | None = None

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
        if self.original_text == self.final_text:
            return ""
        return "\n".join(
            unified_diff(
                self.original_text.splitlines(keepends=True),
                self.final_text.splitlines(keepends=True),
                fromfile="original",
                tofile="repaired",
                lineterm="",
            )
        )

    @property
    def confidence(self) -> float:
        """Heuristic confidence score (0.0 to 1.0) for the repair.

        Higher when fewer strategies were needed and the change was minimal.
        """
        if not self.success:
            return 0.0

        len(self.steps)
        applied_count = len(self.strategies_applied)

        if applied_count == 0:
            return 1.0  # No repair needed, already valid

        # Start at 1.0, reduce by:
        # - Number of strategies needed (more = less confident)
        # - Ratio of text changed (more change = less confident)
        strategy_penalty = min(applied_count * 0.1, 0.5)

        orig_len = max(len(self.original_text), 1)
        final_len = max(len(self.final_text), 1)
        change_ratio = abs(orig_len - final_len) / max(orig_len, final_len)
        change_penalty = min(change_ratio * 0.5, 0.3)

        return max(round(1.0 - strategy_penalty - change_penalty, 2), 0.1)

    @property
    def summary(self) -> str:
        """One-line summary of the repair."""
        if not self.success:
            return f"Repair failed after trying {len(self.steps)} strategies"
        applied = self.strategies_applied
        if not applied:
            return "No repair needed — JSON was already valid"
        return f"Repaired using {len(applied)} strategy(ies): {', '.join(applied)}"

    def step_diffs(self) -> str:
        """Show diff for each strategy that made changes, useful for --verbose."""
        parts = []
        for step in self.steps:
            if step.changed:
                parts.append(f"=== {step.name} ===")
                parts.append(step.diff)
                parts.append("")
        return "\n".join(parts)
