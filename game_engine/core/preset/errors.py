# ========================
# file: game_engine/core/preset/errors.py
# ========================
class PresetError(Exception):
    """Base error for preset system."""


class ValidationError(PresetError):
    """Raised when a preset fails validation."""


class MigrationError(PresetError):
    """Raised when migrating an old preset fails."""


class NotFoundError(PresetError):
    """Raised when a preset id or path cannot be resolved."""
