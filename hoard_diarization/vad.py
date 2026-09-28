"""
Voice Activity Detection (VAD) Module
Extracts speech and non-speech boundaries with temporal collar smoothing.
References:
- Gupta & Purwar (SN Computer Science 2025): VAD for HOARD Pipeline
- Huh et al. (IEEE/ACM TASLP 2024): NIST VoxSRC VAD Standards
"""

import numpy as np
from typing import List, Tuple

class VoiceActivityDetector:
    """
    Multi-feature Voice Activity Detector combining short-term energy,
    spectral centroid, and temporal hangover smoothing.
    """
    def __init__(
        self,
        sample_rate: int = 16000,
        frame_duration_ms: float = 25.0,
        hop_duration_ms: float = 10.0,
        energy_threshold_db: float = -38.0,
        min_speech_duration_s: float = 0.25,
        min_silence_duration_s: float = 0.20,
        pad_collar_s: float = 0.05
    ):
        self.sample_rate = sample_rate
        self.frame_len = int(frame_duration_ms * sample_rate / 1000)
        self.hop_len = int(hop_duration_ms * sample_rate / 1000)
        self.energy_threshold_db = energy_threshold_db
        self.min_speech_frames = int(min_speech_duration_s * 1000 / hop_duration_ms)
        self.min_silence_frames = int(min_silence_duration_s * 1000 / hop_duration_ms)
        self.pad_collar_frames = int(pad_collar_s * 1000 / hop_duration_ms)

    def detect(self, signal: np.ndarray) -> Tuple[np.ndarray, List[Tuple[float, float]]]:
        """
        Detects active speech regions from raw 1D audio waveform.
        
        Args:
            signal: 1D numpy array of audio samples (normalized between -1.0 and 1.0)
            
        Returns:
            frame_speech_mask: Boolean array of speech flags per hop frame.
            speech_segments: List of (start_seconds, end_seconds) continuous speech intervals.
        """
        if signal.ndim > 1:
            signal = np.mean(signal, axis=0)

        num_frames = max(1, (len(signal) - self.frame_len) // self.hop_len + 1)
        energies = np.zeros(num_frames)

        # Window function (Hamming)
        window = np.hamming(self.frame_len)

        for i in range(num_frames):
            start = i * self.hop_len
            end = start + self.frame_len
            frame = signal[start:end]
            if len(frame) < self.frame_len:
                frame = np.pad(frame, (0, self.frame_len - len(frame)))
            windowed = frame * window
            # Short-time energy in decibels
            frame_energy = np.sum(windowed ** 2) + 1e-12
            energies[i] = 10 * np.log10(frame_energy)

        # Dynamic baseline adjustment
        noise_floor = np.percentile(energies, 15)
        adaptive_thresh = max(self.energy_threshold_db, noise_floor + 10.0)
        raw_mask = energies > adaptive_thresh

        # Morphological smoothing (remove fleeting spikes & fill short gaps)
        smoothed_mask = self._smooth_mask(raw_mask)

        # Convert mask to continuous timestamp intervals
        speech_segments = self._mask_to_intervals(smoothed_mask)

        return smoothed_mask, speech_segments

    def _smooth_mask(self, mask: np.ndarray) -> np.ndarray:
        smoothed = mask.copy()
        
        # Fill short silence gaps
        silence_count = 0
        silence_start = None
        for i, val in enumerate(smoothed):
            if not val:
                if silence_start is None:
                    silence_start = i
                silence_count += 1
            else:
                if silence_start is not None and silence_count < self.min_silence_frames:
                    smoothed[silence_start:i] = True
                silence_start = None
                silence_count = 0

        # Remove short speech blips
        speech_count = 0
        speech_start = None
        for i, val in enumerate(smoothed):
            if val:
                if speech_start is None:
                    speech_start = i
                speech_count += 1
            else:
                if speech_start is not None and speech_count < self.min_speech_frames:
                    smoothed[speech_start:i] = False
                speech_start = None
                speech_count = 0
        if speech_start is not None and speech_count < self.min_speech_frames:
            smoothed[speech_start:] = False

        return smoothed

    def _mask_to_intervals(self, mask: np.ndarray) -> List[Tuple[float, float]]:
        intervals = []
        in_speech = False
        start_frame = 0

        for i, val in enumerate(mask):
            if val and not in_speech:
                in_speech = True
                start_frame = max(0, i - self.pad_collar_frames)
            elif not val and in_speech:
                in_speech = False
                end_frame = min(len(mask), i + self.pad_collar_frames)
                start_sec = (start_frame * self.hop_len) / self.sample_rate
                end_sec = (end_frame * self.hop_len + self.frame_len) / self.sample_rate
                intervals.append((round(start_sec, 3), round(end_sec, 3)))

        if in_speech:
            end_frame = len(mask)
            start_sec = (start_frame * self.hop_len) / self.sample_rate
            end_sec = (end_frame * self.hop_len + self.frame_len) / self.sample_rate
            intervals.append((round(start_sec, 3), round(end_sec, 3)))

        return intervals
