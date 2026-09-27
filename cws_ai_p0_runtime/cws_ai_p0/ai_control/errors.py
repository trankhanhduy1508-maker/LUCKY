# SPDX-License-Identifier: GPL-3.0-or-later

class AIControlError(RuntimeError):
    """Base error for the experimental AI control lane."""


class PlanValidationError(AIControlError):
    """Raised before any mutation when a plan is invalid."""


class ExecutionError(AIControlError):
    """Raised when a validated command cannot be executed."""


class PolicyError(AIControlError):
    """Raised when bounded bpy policy rejects a script."""
