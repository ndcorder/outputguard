class OutputGuardError(Exception):
    """Base exception for all outputguard errors."""


class ParseError(OutputGuardError):
    """JSON could not be parsed even after repair attempts."""

    def __init__(self, message: str, original_text: str, parse_error: str | None = None):
        self.original_text = original_text
        self.parse_error = parse_error
        super().__init__(message)


class SchemaValidationError(OutputGuardError):
    """JSON parsed but doesn't match the schema, even after repair."""

    def __init__(self, message: str, data: dict | list, errors: list, schema: dict):
        self.data = data
        self.validation_errors = errors
        self.schema = schema
        super().__init__(message)


class RepairError(OutputGuardError):
    """Repair was attempted but failed."""

    def __init__(self, message: str, strategies_tried: list[str], original_text: str):
        self.strategies_tried = strategies_tried
        self.original_text = original_text
        super().__init__(message)


class StrategyError(OutputGuardError):
    """A specific repair strategy encountered an error."""

    def __init__(self, message: str, strategy_name: str):
        self.strategy_name = strategy_name
        super().__init__(message)
