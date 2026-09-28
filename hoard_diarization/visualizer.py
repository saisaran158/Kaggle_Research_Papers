"""
Research Diagnostics & Visualizer Module
Generates publication-quality figures matching Springer Nature (HOARD) and arXiv (Stride-Accelerated Diarization).
References:
- Gupta & Purwar (SN Computer Science 2025): Fig. 3 Euclidean distance & OSH module figures
- Yamaguchi (arXiv 2026): Fig. 1 Clustering intermediates (Cosine similarity, PCA, Timeline) & Fig. 2 DER curves
"""

import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from sklearn.decomposition import PCA
from typing import List, Dict, Optional

class ResearchVisualizer:
    """
    Generates multi-panel diagnostic and presentation charts for speaker diarization.
    """
    @staticmethod
    def plot_publication_diagnostics(
        embeddings: np.ndarray,
        speaker_labels: np.ndarray,
        segments: List[Dict],
        total_duration: float,
        der_metrics: Optional[Dict] = None,
        save_path: Optional[str] = None
    ):
        """
        Creates a 4-panel comprehensive research diagnostic figure:
        1. Cosine Similarity Matrix (sorted by speaker clusters)
        2. 2D PCA Latent Space Projection
        3. Multi-Speaker Overlap-Aware Timeline (Gantt Chart)
        4. Speaker Turn & Duration Distribution
        """
        fig = plt.figure(figsize=(16, 12), dpi=300)
        gs = fig.add_gridspec(2, 2, hspace=0.3, wspace=0.25)

        unique_spks = sorted(list(set(speaker_labels)))
        k = len(unique_spks)
        color_palette = plt.get_cmap("tab10", max(10, k))

        # -------------------------------------------------------------
        # 1. Cosine Similarity Heatmap (Sorted by cluster)
        # -------------------------------------------------------------
        ax1 = fig.add_subplot(gs[0, 0])
        sort_order = np.argsort(speaker_labels)
        sorted_embs = embeddings[sort_order]
        norms = np.linalg.norm(sorted_embs, axis=1, keepdims=True) + 1e-10
        norm_sorted = sorted_embs / norms
        sim_mat = np.dot(norm_sorted, norm_sorted.T)

        im1 = ax1.imshow(sim_mat, cmap="coolwarm", vmin=0.0, vmax=1.0, origin="lower")
        ax1.set_title("(a) Refined Cosine Similarity Matrix", fontsize=12, fontweight="bold")
        ax1.set_xlabel("Segment Index (Cluster-Sorted)", fontsize=10)
        ax1.set_ylabel("Segment Index (Cluster-Sorted)", fontsize=10)
        cbar1 = plt.colorbar(im1, ax=ax1, fraction=0.046, pad=0.04)
        cbar1.set_label("Cosine Similarity", fontsize=9)

        # -------------------------------------------------------------
        # 2. 2D PCA Latent Space Projection
        # -------------------------------------------------------------
        ax2 = fig.add_subplot(gs[0, 1])
        if len(embeddings) >= 2:
            pca = PCA(n_components=2)
            embs_2d = pca.fit_transform(embeddings)
            for idx, spk in enumerate(unique_spks):
                mask = (speaker_labels == spk)
                ax2.scatter(
                    embs_2d[mask, 0],
                    embs_2d[mask, 1],
                    label=f"SPEAKER_{spk+1:02d}",
                    color=color_palette(idx),
                    alpha=0.8,
                    edgecolors="none",
                    s=45
                )
            var_exp = pca.explained_variance_ratio_ * 100
            ax2.set_xlabel(f"PC1 ({var_exp[0]:.1f}% var)", fontsize=10)
            ax2.set_ylabel(f"PC2 ({var_exp[1]:.1f}% var)", fontsize=10)
        ax2.set_title("(b) 2D PCA Speaker Latent Space", fontsize=12, fontweight="bold")
        ax2.legend(loc="upper right", fontsize=8, framealpha=0.8)
        ax2.grid(True, linestyle=":", alpha=0.6)

        # -------------------------------------------------------------
        # 3. Multi-Speaker Overlap-Aware Timeline (Gantt Chart)
        # -------------------------------------------------------------
        ax3 = fig.add_subplot(gs[1, 0])
        spk_names = sorted(list(set(s["speaker"] for s in segments)))
        spk_to_y = {spk: i for i, spk in enumerate(spk_names)}

        for seg in segments:
            y = spk_to_y[seg["speaker"]]
            dur = seg["end"] - seg["start"]
            color = color_palette(y % 10)
            is_overlap = seg.get("is_overlap", False)
            edge_color = "red" if is_overlap else "none"
            hatch = "//" if is_overlap else None

            ax3.barh(
                y,
                dur,
                left=seg["start"],
                height=0.55,
                color=color,
                edgecolor=edge_color,
                hatch=hatch,
                linewidth=1.2 if is_overlap else 0,
                alpha=0.85
            )

        ax3.set_yticks(range(len(spk_names)))
        ax3.set_yticklabels(spk_names, fontsize=9)
        ax3.set_xlim(0, max(total_duration, 1.0))
        ax3.set_xlabel("Time (seconds)", fontsize=10)
        ax3.set_title("(c) Multi-Speaker Overlap-Aware Timeline", fontsize=12, fontweight="bold")
        ax3.grid(axis="x", linestyle="--", alpha=0.7)

        # Legend for overlap
        overlap_patch = mpatches.Patch(facecolor="lightgray", edgecolor="red", hatch="//", label="Overlapped Speech")
        ax3.legend(handles=[overlap_patch], loc="lower right", fontsize=8)

        # -------------------------------------------------------------
        # 4. Speaker Participation & DER Metrics Breakdown
        # -------------------------------------------------------------
        ax4 = fig.add_subplot(gs[1, 1])
        
        # Calculate speaking duration per speaker
        spk_durations = {spk: 0.0 for spk in spk_names}
        for seg in segments:
            spk_durations[seg["speaker"]] += (seg["end"] - seg["start"])

        dur_values = [spk_durations[s] for s in spk_names]
        bars = ax4.bar(spk_names, dur_values, color=[color_palette(i) for i in range(len(spk_names))], width=0.5, alpha=0.85)

        for bar, dur in zip(bars, dur_values):
            pct = (dur / max(total_duration, 1e-6)) * 100
            ax4.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.5,
                f"{dur:.1f}s\n({pct:.1f}%)",
                ha="center",
                va="bottom",
                fontsize=8
            )

        ax4.set_title("(d) Speaker Participation & Speaking Time", fontsize=12, fontweight="bold")
        ax4.set_ylabel("Total Speaking Duration (s)", fontsize=10)
        ax4.set_ylim(0, max(dur_values, default=10) * 1.25)
        ax4.grid(axis="y", linestyle=":", alpha=0.7)

        # Add text box with research metrics if provided
        if der_metrics:
            textstr = (
                f"Evaluation Benchmark:\n"
                f"• DER: {der_metrics.get('DER', 0.0):.2f}%\n"
                f"• Confusion: {der_metrics.get('Confusion', 0.0):.2f}%\n"
                f"• Missed: {der_metrics.get('Missed', 0.0):.2f}%\n"
                f"• False Alarm: {der_metrics.get('False_Alarm', 0.0):.2f}%\n"
                f"• Purity: {der_metrics.get('Purity', 0.0):.1f}%\n"
                f"• ARI: {der_metrics.get('ARI', 0.0):.4f}"
            )
            props = dict(boxstyle="round,pad=0.5", facecolor="aliceblue", alpha=0.9, edgecolor="steelblue")
            ax4.text(0.98, 0.95, textstr, transform=ax4.transAxes, fontsize=8, va="top", ha="right", bbox=props)

        plt.suptitle("HOARD Speaker Diarization Diagnostic Suite (VoxConverse)", fontsize=15, fontweight="bold", y=0.98)

        if save_path:
            os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
            plt.savefig(save_path, bbox_inches="tight", dpi=300)
            print(f"[OK] Saved publication-grade diagnostic plot to: {save_path}")

        plt.close(fig)
