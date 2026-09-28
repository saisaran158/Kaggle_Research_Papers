"""
Overlapped Speech Detection (OSD) Module
Identifies regions of multi-talker simultaneous speech.
References:
- Gupta & Purwar (SN Computer Science 2025): Overlap detector sequence labeling (yt = 1 if >= 2 speakers)
- Huh et al. (IEEE/ACM TASLP 2024): TS-VAD & OSD Integration
"""

import numpy as np
from typing import List, Tuple

class OverlapDetector:
    """
    Overlapped Speech Detection (OSD) using spectral variability, harmonic-to-noise ratio,
    and multi-peak energy distribution.
    """
    def __init__(
        self,
        sample_rate: int = 16000,
        frame_duration_ms: float = 30.0,
        hop_duration_ms: float = 10.0,
        overlap_sensitivity: float = 0.45
    ):
        self.sample_rate = sample_rate
        self.frame_len = int(frame_duration_ms * sample_rate / 1000)
        self.hop_len = int(hop_duration_ms * sample_rate / 1000)
        self.sensitivity = overlap_sensitivity

    def detect_overlaps(self, audio_signal: np.ndarray, speech_mask: np.ndarray = None) -> Tuple[np.ndarray, List[Tuple[float, float]]]:
        """
        Detects time segments containing overlapping speech.
        
        Returns:
            overlap_vector (Op): Binary array where 1 indicates overlapped segment, 0 otherwise.
            overlap_intervals: List of (start_sec, end_sec) overlapped intervals.
        """
        if audio_signal.ndim > 1:
            audio_signal = np.mean(audio_signal, axis=0)

        num_frames = max(1, (len(audio_signal) - self.frame_len) // self.hop_len + 1)
        overlap_scores = np.zeros(num_frames)

        window = np.hamming(self.frame_len)
        n_fft = 512

        for i in range(num_frames):
            start = i * self.hop_len
            end = start + self.frame_len
            frame = audio_signal[start:end]
            if len(frame) < self.frame_len:
                frame = np.pad(frame, (0, self.frame_len - len(frame)))
            
            w_frame = frame * window
            fft_mag = np.abs(np.fft.rfft(w_frame, n=n_fft))
            
            # Multi-pitch & Spectral Flatness Measure for overlapping speech
            spec_sum = np.sum(fft_mag) + 1e-10
            geom_mean = np.exp(np.mean(np.log(np.maximum(fft_mag, 1e-10))))
            arith_mean = np.mean(fft_mag) + 1e-10
            spectral_flatness = geom_mean / arith_mean

            # Peak counts in fundamental frequency band (80Hz - 600Hz)
            freqs = np.fft.rfftfreq(n_fft, d=1.0 / self.sample_rate)
            pitch_band = (freqs >= 80) & (freqs <= 600)
            band_mags = fft_mag[pitch_band]
            
            # Simple local maxima count in pitch band
            peaks = 0
            if len(band_mags) > 4:
                diffs = np.diff(band_mags)
                peaks = np.sum((diffs[:-1] > 0) & (diffs[1:] < 0))

            # Composite overlap probability
            score = (peaks / 12.0) * 0.6 + (1.0 - spectral_flatness) * 0.4
            overlap_scores[i] = score

        # Binary thresholding
        raw_overlap_mask = overlap_scores > (1.0 - self.sensitivity)
        
        # Only consider frames that are verified active speech
        if speech_mask is not None:
            min_len = min(len(raw_overlap_mask), len(speech_mask))
            raw_overlap_mask = raw_overlap_mask[:min_len] & speech_mask[:min_len]

        # Median filter smoothing
        smoothed = np.convolve(raw_overlap_mask.astype(float), np.ones(5) / 5, mode='same') > 0.45
        
        # Convert to intervals
        overlap_intervals = []
        in_overlap = False
        start_f = 0
        for i, val in enumerate(smoothed):
            if val and not in_overlap:
                in_overlap = True
                start_f = i
            elif not val and in_overlap:
                in_overlap = False
                st = round(start_f * self.hop_len / self.sample_rate, 3)
                et = round((i * self.hop_len + self.frame_len) / self.sample_rate, 3)
                if et - st >= 0.15:  # Filter out instantaneous false spikes
                    overlap_intervals.append((st, et))

        if in_overlap:
            st = round(start_f * self.hop_len / self.sample_rate, 3)
            et = round(len(smoothed) * self.hop_len / self.sample_rate, 3)
            overlap_intervals.append((st, et))

        return smoothed.astype(int), overlap_intervals
