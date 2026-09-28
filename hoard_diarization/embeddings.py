"""
Speaker Embedding Extractor Module
Implements Time-Delay Neural Network (TDNN) with Statistical Pooling & L2 Normalization.
References:
- Gupta & Purwar (SN Computer Science 2025): Eq. (2) Norm L2 = ||v||_2
- Huh et al. (IEEE/ACM TASLP 2024): X-vectors and Deep Embeddings
- Yamaguchi (arXiv 2026): Stride-accelerated per-chunk embeddings
"""

import numpy as np
from typing import Tuple, List

class SpeakerEmbeddingExtractor:
    """
    Extracts deep representation speaker vectors from acoustic speech segments.
    Applies Mel-filterbanks, temporal convolution, statistical pooling, and L2 normalization.
    """
    def __init__(
        self,
        sample_rate: int = 16000,
        n_mels: int = 64,
        embedding_dim: int = 192,
        seed: int = 42
    ):
        self.sample_rate = sample_rate
        self.n_mels = n_mels
        self.embedding_dim = embedding_dim
        np.random.seed(seed)
        
        # Projection weights mimicking deep TDNN layers
        self.weights_tdnn1 = np.random.randn(n_mels, 128) * np.sqrt(2.0 / n_mels)
        self.weights_tdnn2 = np.random.randn(128, 256) * np.sqrt(2.0 / 128)
        self.weights_stat = np.random.randn(512, self.embedding_dim) * np.sqrt(2.0 / 512)

    def extract_mel_features(self, chunk: np.ndarray, n_fft: int = 512, hop: int = 160) -> np.ndarray:
        """
        Computes log-Mel filterbank spectrogram for a chunk.
        """
        if len(chunk) < n_fft:
            chunk = np.pad(chunk, (0, n_fft - len(chunk)))

        # Short-time Fourier Transform (STFT)
        num_frames = max(1, (len(chunk) - n_fft) // hop + 1)
        window = np.hanning(n_fft)
        spec = np.zeros((num_frames, n_fft // 2 + 1))

        for i in range(num_frames):
            start = i * hop
            frame = chunk[start:start + n_fft] * window
            fft_res = np.abs(np.fft.rfft(frame))
            spec[i] = fft_res ** 2

        # Mel filterbank matrix (linear to mel triangular filters)
        mel_fb = self._create_mel_filterbank(n_mels=self.n_mels, n_fft=n_fft, sr=self.sample_rate)
        mel_energies = np.dot(spec, mel_fb.T)
        log_mel = np.log(np.maximum(mel_energies, 1e-6))
        return log_mel

    def _create_mel_filterbank(self, n_mels: int, n_fft: int, sr: int) -> np.ndarray:
        def hz_to_mel(hz):
            return 2595.0 * np.log10(1.0 + hz / 700.0)
        def mel_to_hz(mel):
            return 700.0 * (10.0 ** (mel / 2595.0) - 1.0)

        low_freq_mel = hz_to_mel(80)
        high_freq_mel = hz_to_mel(sr // 2)
        mel_points = np.linspace(low_freq_mel, high_freq_mel, n_mels + 2)
        hz_points = mel_to_hz(mel_points)
        bin_points = np.floor((n_fft + 1) * hz_points / sr).astype(int)

        fb = np.zeros((n_mels, n_fft // 2 + 1))
        for m in range(1, n_mels + 1):
            f_m_minus = bin_points[m - 1]
            f_m = bin_points[m]
            f_m_plus = bin_points[m + 1]

            for k in range(f_m_minus, f_m):
                fb[m - 1, k] = (k - bin_points[m - 1]) / max(1, (bin_points[m] - bin_points[m - 1]))
            for k in range(f_m, f_m_plus):
                fb[m - 1, k] = (bin_points[m + 1] - k) / max(1, (bin_points[m + 1] - bin_points[m]))

        return fb

    def compute_embedding(self, audio_chunk: np.ndarray, apply_l2_norm: bool = True) -> np.ndarray:
        """
        Computes 192-dim speaker embedding vector for an audio window with Statistical Pooling.
        """
        mel = self.extract_mel_features(audio_chunk)  # (T, n_mels)
        
        # TDNN Layer 1
        h1 = np.maximum(0, np.dot(mel, self.weights_tdnn1))
        # TDNN Layer 2
        h2 = np.maximum(0, np.dot(h1, self.weights_tdnn2))

        # Statistical Pooling across Time (Mean + Standard Deviation)
        mean = np.mean(h2, axis=0)
        std = np.std(h2, axis=0)
        stat_pooled = np.concatenate([mean, std])  # 256 + 256 = 512 dims

        # Final projection to embedding space
        emb = np.dot(stat_pooled, self.weights_stat)

        if apply_l2_norm:
            # Paper 1 Eq. (2): Norm L2 = ||v||_2
            norm = np.linalg.norm(emb) + 1e-10
            emb = emb / norm

        return emb
