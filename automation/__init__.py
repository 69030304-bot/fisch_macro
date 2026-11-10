"""
automation package - Fishing workflows, operations, and control algorithms.
"""
from automation.controller import ReelController, SigmaDeltaModulator
from automation.operations import (
    AutomationContext,
    EquipRodOperation,
    CastOperation,
    BiteWaitOperation,
    ReelOperation,
)
from automation.workflow import FishingWorkflow

__all__ = [
    "ReelController",
    "SigmaDeltaModulator",
    "AutomationContext",
    "EquipRodOperation",
    "CastOperation",
    "BiteWaitOperation",
    "ReelOperation",
    "FishingWorkflow",
]
