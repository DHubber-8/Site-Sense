"""PPE detection agent package."""

from .config import PPE_MODEL_PATH
from .agent import PpeDetectionAgent
from .schema import BoundingBox, PpeDetection, PpeDetectionBatch

__all__ = [
    "BoundingBox",
    "PPE_MODEL_PATH",
    "PpeDetection",
    "PpeDetectionAgent",
    "PpeDetectionBatch",
]
