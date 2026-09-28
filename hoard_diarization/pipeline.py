"""
Unified HOARD (Handled Overlap-Aware Refined Diarization) Pipeline
Orchestrates VAD, OSD, Embeddings, OOA-SC Clustering, SSA, OSH Multi-Hypothesis Fusion, and Diagnostics.
References:
- Gupta & Purwar (SN Computer Science 2025): HOARD Framework (Fig. 1)
- Huh et al. (IEEE/ACM TASLP 2024): VoxSRC Standards & SOTA Diarization Recipe
- Yamaguchi (arXiv 2026): Stride Acceleration & Adaptive Relative Cluster Sizing
"""

import os
import wave
import numpy as np
from typing import Dict, List, Optional, Tuple

from .vad import VoiceActivityDetector
from .embeddings import SpeakerEmbeddingExtractor
from .overlap_detector import OverlapDetector
from .clustering import SpectralAndHierarchicalClusterer
from .ssa_osh import OverlappedSpeakersHandlingModule
from .rttm_handler import RTTMHandler
from .metrics import DiarizationEvaluator
from .visualizer import ResearchVisualizer

class HOARDDiarizationPipeline:
    """
    End-to-end research-grade speaker diarization pipeline.
    """
    def __init__(
        self,
        sample_rate: int = 16000,
        window_duration_s: float = 1.5,
        hop_duration_s: float = 0.5,
        min_cluster_fraction: float = 0.01,
        max_speakers: int = 10,
        enable_osh: bool = True
    ):
        self.sample_rate = sample_rate
        self.window_len = int(window_duration_s * sample_rate)
        self.hop_len = int(hop_duration_s * sample_rate)
        self.enable_osh = enable_osh

        # Sub-modules
        self.vad = VoiceActivityDetector(sample_rate=sample_rate)
        self.embedder = SpeakerEmbeddingExtractor(sample_rate=sample_rate)
        self.osd = OverlapDetector(sample_rate=sample_rate)
        self.clusterer = SpectralAndHierarchicalClusterer(
            min_cluster_fraction=min_cluster_fraction,
            max_clusters=max_speakers
        )
        self.osh = OverlappedSpeakersHandlingModule()
        self.evaluator = DiarizationEvaluator(collar_s=0.25)

    def load_wav(self, file_path: str) -> Tuple[np.ndarray, float]:
        """Loads WAV audio file as float numpy array."""
        with wave.open(file_path, "rb") as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            n_frames = wf.getnframes()
            audio_bytes = wf.readframes(n_frames)

        if sampwidth == 2:
            data = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        elif sampwidth == 4:
            data = np.frombuffer(audio_bytes, dtype=np.int32).astype(np.float32) / 2147483648.0
        else:
            data = np.frombuffer(audio_bytes, dtype=np.uint8).astype(np.float32) / 128.0 - 1.0

        if n_channels > 1:
            data = data.reshape(-1, n_channels).mean(axis=1)

        # Simple linear resample if sample rate doesn't match
        if framerate != self.sample_rate:
            target_len = int(len(data) * self.sample_rate / framerate)
            data = np.interp(
                np.linspace(0, len(data), target_len, endpoint=False),
                np.arange(len(data)),
                data
            )

        duration = len(data) / self.sample_rate
        return data, duration

    def diarize_audio(
        self,
        audio_path: str,
        num_speakers: Optional[int] = None,
        ground_truth_rttm: Optional[str] = None,
        output_rttm_path: Optional[str] = None,
        diagnostic_plot_path: Optional[str] = None
    ) -> Dict:
        """
        Executes full HOARD speaker diarization pipeline on an audio file.
        """
        signal, total_duration = self.load_wav(audio_path)
        uri = os.path.splitext(os.path.basename(audio_path))[0]

        # 1. Voice Activity Detection (VAD)
        speech_mask, speech_intervals = self.vad.detect(signal)

        # 2. Overlap Speech Detection (OSD)
        overlap_mask, overlap_intervals = self.osd.detect_overlaps(signal, speech_mask)

        # 3. Sliding-window Embedding Extraction
        embeddings = []
        timestamps = []
        chunk_overlap_flags = []

        total_samples = len(signal)
        for start_idx in range(0, total_samples - self.window_len + 1, self.hop_len):
            end_idx = start_idx + self.window_len
            chunk = signal[start_idx:end_idx]

            # Check if chunk contains significant speech
            mid_sample = (start_idx + end_idx) // 2
            mid_frame = int((mid_sample / self.sample_rate) * 100)  # 10ms frame rate
            if mid_frame < len(speech_mask) and not speech_mask[mid_frame]:
                continue

            emb = self.embedder.compute_embedding(chunk, apply_l2_norm=True)
            embeddings.append(emb)

            start_t = round(start_idx / self.sample_rate, 3)
            end_t = round(end_idx / self.sample_rate, 3)
            timestamps.append((start_t, end_t))

            is_ov = (mid_frame < len(overlap_mask) and overlap_mask[mid_frame] == 1)
            chunk_overlap_flags.append(1 if is_ov else 0)

        if not embeddings:
            return {"uri": uri, "segments": [], "stats": {}, "total_duration": total_duration}

        embeddings = np.array(embeddings)
        chunk_overlap_flags = np.array(chunk_overlap_flags)

        # 4. Clustering & Multi-Hypothesis Overlap Handling
        if self.enable_osh:
            fused_assignments = self.osh.generate_hypotheses_and_fuse(
                embeddings=embeddings,
                clusterer=self.clusterer,
                overlap_mask=chunk_overlap_flags,
                num_speakers=num_speakers
            )
            primary_labels = np.array([fa["primary"] for fa in fused_assignments])
        else:
            primary_labels, _, _ = self.clusterer.fit_ooa_sc(
                embeddings,
                chunk_overlap_flags,
                num_clusters=num_speakers
            )
            fused_assignments = [{"primary": p, "secondary": None, "is_overlap": False} for p in primary_labels]

        # 5. Form Output Segments (with multi-speaker overlapping tracks)
        raw_segments = []
        for (st, et), assign in zip(timestamps, fused_assignments):
            spk1_id = f"SPEAKER_{assign['primary'] + 1:02d}"
            raw_segments.append({"start": st, "end": et, "speaker": spk1_id, "is_overlap": False})

            # If overlapping, also emit second speaker turn
            if assign.get("secondary") is not None:
                spk2_id = f"SPEAKER_{assign['secondary'] + 1:02d}"
                raw_segments.append({"start": st, "end": et, "speaker": spk2_id, "is_overlap": True})

        # Temporal Segment Merging for each speaker
        merged_segments = self._merge_speaker_segments(raw_segments)

        # 6. Compute Speaker Statistics
        spk_stats = {}
        for seg in merged_segments:
            spk = seg["speaker"]
            dur = seg["end"] - seg["start"]
            if spk not in spk_stats:
                spk_stats[spk] = {"total_time_sec": 0.0, "turns_count": 0}
            spk_stats[spk]["total_time_sec"] += dur
            spk_stats[spk]["turns_count"] += 1

        for spk in spk_stats:
            spk_stats[spk]["total_time_sec"] = round(spk_stats[spk]["total_time_sec"], 2)
            spk_stats[spk]["speaking_percentage"] = round(
                (spk_stats[spk]["total_time_sec"] / max(total_duration, 1e-6)) * 100, 2
            )

        unique_speakers = sorted(list(spk_stats.keys()))

        # 7. Optional Ground Truth Evaluation (DER, JER, Purity, Coverage, ARI)
        metrics = None
        if ground_truth_rttm and os.path.exists(ground_truth_rttm):
            ref_segs = RTTMHandler.read_rttm(ground_truth_rttm)
            metrics = self.evaluator.compute_der(merged_segments, ref_segs)

        # 8. Export RTTM
        if output_rttm_path:
            RTTMHandler.write_rttm(merged_segments, output_rttm_path, uri=uri)

        # 9. Generate Diagnostics Figure
        if diagnostic_plot_path:
            ResearchVisualizer.plot_publication_diagnostics(
                embeddings=embeddings,
                speaker_labels=primary_labels,
                segments=merged_segments,
                total_duration=total_duration,
                der_metrics=metrics,
                save_path=diagnostic_plot_path
            )

        return {
            "uri": uri,
            "total_duration_sec": round(total_duration, 2),
            "estimated_speakers": len(unique_speakers),
            "speaker_stats": spk_stats,
            "segments": merged_segments,
            "metrics": metrics
        }

    def _merge_speaker_segments(self, segments: List[Dict]) -> List[Dict]:
        """Merges contiguous or closely overlapping intervals for the same speaker."""
        by_spk = {}
        for s in segments:
            by_spk.setdefault(s["speaker"], []).append(s)

        merged = []
        for spk, seg_list in by_spk.items():
            seg_list.sort(key=lambda x: x["start"])
            cur_seg = None
            for s in seg_list:
                if cur_seg is None:
                    cur_seg = dict(s)
                else:
                    if s["start"] <= cur_seg["end"] + 0.15:  # Tolerance merge
                        cur_seg["end"] = max(cur_seg["end"], s["end"])
                        cur_seg["is_overlap"] = cur_seg["is_overlap"] or s.get("is_overlap", False)
                    else:
                        merged.append(cur_seg)
                        cur_seg = dict(s)
            if cur_seg is not None:
                merged.append(cur_seg)

        merged.sort(key=lambda x: (x["start"], x["speaker"]))
        for m in merged:
            m["start"] = round(m["start"], 2)
            m["end"] = round(m["end"], 2)
            m["duration"] = round(m["end"] - m["start"], 2)

        return merged
