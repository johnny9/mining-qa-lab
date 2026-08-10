class LabError(Exception):
    """Base error for mining-qa-lab failures."""


class ConfigError(LabError, ValueError):
    """The lab orchestration configuration is invalid."""
