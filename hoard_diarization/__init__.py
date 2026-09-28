"""
HOARD: Handled Overlap-Aware Refined Diarization Framework
Integrated with SOTA Research from:
1. Gupta & Purwar (SN Computer Science 2025): HOARD, OOA-SC, SSA & OSH
2. Huh, Chung, Nagrani, Zisserman et al. (IEEE/ACM TASLP 2024): VoxSRC Standards & DER/JER
3. Yamaguchi (arXiv 2026): Stride Acceleration & Adaptive Relative Cluster Sizing
"""

from .pipeline import HOARDDiarizationPipeline
from .vad import VoiceActivityDetector
from .embeddings import SpeakerEmbeddingExtractor
from .overlap_detector import OverlapDetector
from .clustering import SpectralAndHierarchicalClusterer
from .ssa_osh import SecondSpeakerAssignment, OverlappedSpeakersHandlingModule
from .rttm_handler import RTTMHandler
from .metrics import DiarizationEvaluator
from .visualizer import ResearchVisualizer

__version__ = "2.0.0"
__all__ = [
    "HOARDDiarizationPipeline",
    "VoiceActivityDetector",
    "SpeakerEmbeddingExtractor",
    "OverlapDetector",
    "SpectralAndHierarchicalClusterer",
    "SecondSpeakerAssignment",
    "OverlappedSpeakersHandlingModule",
    "RTTMHandler",
    "DiarizationEvaluator",
    "ResearchVisualizer"
]
