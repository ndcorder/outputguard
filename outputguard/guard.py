from outputguard.models import ValidationResult, RepairResult, ValidationError
from outputguard import validator as _validator
from outputguard import repairer as _repairer
from outputguard import retry as _retry


class OutputGuard:
    def __init__(
        self,
        strategies: list[str] | None = None,
        max_repair_attempts: int = 3,
    ):
        self.strategies = strategies
        self.max_repair_attempts = max_repair_attempts

    def validate(self, text: str, schema: dict) -> ValidationResult:
        return _validator.validate(text, schema)

    def repair(self, text: str) -> RepairResult:
        return _repairer.repair(text, self.strategies)

    def validate_and_repair(self, text: str, schema: dict) -> ValidationResult:
        """Validate, and if invalid, attempt repair then re-validate."""
        result = self.validate(text, schema)
        if result.valid:
            return result

        current_text = text
        for _attempt in range(self.max_repair_attempts):
            repair_result = self.repair(current_text)
            if not repair_result.repaired:
                continue

            revalidation = self.validate(repair_result.text, schema)
            if revalidation.valid:
                revalidation.repaired = True
                revalidation.strategies_applied = repair_result.strategies_applied
                revalidation.original_text = text
                revalidation.repaired_text = repair_result.text
                return revalidation
            # Still invalid but was repaired — feed repaired text into next attempt
            current_text = repair_result.text

        # All attempts failed — return the original validation result
        result.original_text = text
        return result

    def retry_prompt(
        self, text: str, schema: dict, errors: list[ValidationError]
    ) -> str:
        return _retry.retry_prompt(text, schema, errors)
