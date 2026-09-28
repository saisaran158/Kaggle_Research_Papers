"""
Generates publication figures comparing baseline vs HOARD framework on VoxConverse simulation.
Produces high-resolution plots matching Figure 1, 2, 3 in the analyzed research papers.
"""

import os
import sys
import numpy as np
import matplotlib.pyplot as plt

# Ensure package is discoverable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from hoard_diarization import (
    HOARDDiarizationPipeline,
    RTTMHandler,
    DiarizationEvaluator,
    ResearchVisualizer
)
from run_diarization import generate_synthetic_multitalker_wav

def main():
    plots_dir = os.path.join(os.path.dirname(__file__), "..", "figures")
    os.makedirs(plots_dir, exist_ok=True)

    wav_path = os.path.join(plots_dir, "voxconverse_sample.wav")
    ref_rttm_path = os.path.join(plots_dir, "ground_truth.rttm")
    pred_rttm_path = os.path.join(plots_dir, "hoard_predictions.rttm")
    fig1_path = os.path.join(plots_dir, "figure1_hoard_diagnostics.png")
    fig2_path = os.path.join(plots_dir, "figure2_der_comparison.png")

    print("[1/4] Synthesizing multi-speaker conversation audio with overlaps...")
    generate_synthetic_multitalker_wav(wav_path, duration_s=45.0)

    # Generate synthetic Ground Truth RTTM
    ground_truth = [
        {"start": 1.0, "end": 9.0, "speaker": "SPEAKER_01"},
        {"start": 7.0, "end": 15.0, "speaker": "SPEAKER_02"}, # Overlap 7-9s
        {"start": 13.0, "end": 21.0, "speaker": "SPEAKER_01"}, # Overlap 13-15s
        {"start": 20.5, "end": 27.0, "speaker": "SPEAKER_02"}, # Overlap 20.5-21s
        {"start": 25.0, "end": 29.5, "speaker": "SPEAKER_01"}, # Overlap 25-27s
        {"start": 26.0, "end": 29.5, "speaker": "SPEAKER_03"}, # 3-Speaker Overlap 26-27s
        {"start": 32.0, "end": 44.0, "speaker": "SPEAKER_02"}
    ]
    RTTMHandler.write_rttm(ground_truth, ref_rttm_path, uri="voxconverse_sample")

    print("[2/4] Running HOARD Diarization Pipeline...")
    pipeline = HOARDDiarizationPipeline(
        sample_rate=16000,
        min_cluster_fraction=0.01,
        enable_osh=True
    )

    result = pipeline.diarize_audio(
        audio_path=wav_path,
        ground_truth_rttm=ref_rttm_path,
        output_rttm_path=pred_rttm_path,
        diagnostic_plot_path=fig1_path
    )

    print("[3/4] Generating Benchmark DER Comparison Bar Chart across Research Papers...")
    # Benchmark numbers from Paper 1 (Table 3, Table 5) & Paper 3 (Table IV)
    methods = [
        "Baseline MSC\n(No Overlap)",
        "Jarsanath et al.\n(CRNN + Gap)",
        "Bredin et al.\n(Bi-LSTM OSD)",
        "Singh et al.\n(SHARC GNN)",
        "Yamaguchi (2026)\n(Stride-3 + Rel MCS)",
        "Gupta et al. (2025)\n(HOARD Framework)"
    ]
    der_scores = [15.14, 25.73, 13.63, 12.56, 7.90, 8.76]
    colors = ["#7f7f7f", "#d62728", "#ff7f0e", "#1f77b4", "#2ca02c", "#9467bd"]

    fig, ax = plt.subplots(figsize=(10, 5), dpi=300)
    bars = ax.bar(methods, der_scores, color=colors, width=0.55, edgecolor="black", linewidth=0.8, alpha=0.85)

    for bar, score in zip(bars, der_scores):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.4,
            f"{score:.2f}%",
            ha="center",
            va="bottom",
            fontweight="bold",
            fontsize=9
        )

    ax.set_ylabel("Diarization Error Rate (DER %)", fontsize=11, fontweight="bold")
    ax.set_title("VoxConverse Benchmark Comparison across Research Papers (Lower is Better)", fontsize=13, fontweight="bold")
    ax.set_ylim(0, 30)
    ax.grid(axis="y", linestyle="--", alpha=0.6)
    plt.tight_layout()
    plt.savefig(fig2_path, dpi=300)
    plt.close()

    print(f"[4/4] Done! All figures generated in: {plots_dir}")
    print(f"  • Figure 1: {fig1_path}")
    print(f"  • Figure 2: {fig2_path}")

if __name__ == "__main__":
    main()
