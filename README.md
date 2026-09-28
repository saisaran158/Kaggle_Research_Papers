# HOARD: Handled Overlap-Aware Refined Diarization Framework for Multi-Speaker Audio

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Research: VoxConverse](https://img.shields.io/badge/Benchmark-VoxConverse%20SOTA-success.svg)](https://www.robots.ox.ac.uk/~vgg/data/voxconverse/)

A research-grade Speaker Diarization framework implementing the state-of-the-art methodology from three foundational papers:
1. **Paper 1:** *"A Novel Framework to Handle Overlapped Speech for Multiple Speakers in Speaker Diarization"* (Gupta & Purwar, *SN Computer Science*, 2025).
2. **Paper 2:** *"The VoxCeleb Speaker Recognition Challenge: A Retrospective"* (Huh, Chung, Nagrani, Zisserman, et al., *IEEE/ACM Transactions on Audio, Speech, and Language Processing*, 2024).
3. **Paper 3:** *"Fast and Robust On-Device Speaker Diarization: Relative Minimum Cluster Size for Stride-Accelerated Pipelines"* (Yamaguchi, *arXiv:2606.08505*, 2026).

---

## 🔬 Key Architectural Highlights

```
Raw Audio (.wav)
      │
      ▼
┌──────────────────────────────────────────────┐
│       1. Voice Activity Detection (VAD)      │  ◄── Energy + Spectral Hangover Smoothing
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│     2. Overlapped Speech Detection (OSD)     │  ◄── Multi-pitch & Spectral Flatness (yt = 1 if >= 2 speakers)
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│    3. Deep Speaker Embedding Extractor       │  ◄── TDNN with Statistical Pooling + L2 Normalization (||v||_2)
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│ 4. Optimized Overlap-Aware Spectral          │
│    Clustering (OOA-SC) & Adaptive Rel. MCS   │  ◄── Alternating Optimization (AO) + mcs = round(f * n), f=0.01
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│ 5. Second Speaker Assignment (SSA)           │  ◄── Algorithm 1: Euclidean Distance Centroid Minimization
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│ 6. Overlapped Speakers' Handling (OSH)       │  ◄── 3 Hypotheses (HL1, HL2, HL3) + Weighted Majority Voting
└──────────────────────┬───────────────────────┘
                       │
                       ▼
 ┌───────────────────────────────────────────┐
 │ • NIST Standard .rttm Predictions         │
 │ • Multi-Track Overlap Diarization Gantt   │
 │ • DER / JER / Purity / Coverage / ARI     │
 └───────────────────────────────────────────┘
```

---

## 📊 Benchmark Results on VoxConverse

| Method / Architecture | Reference | Overlap Aware? | Dev DER (%) | Test DER (%) |
| :--- | :--- | :---: | :---: | :---: |
| Baseline Multi-Class Spectral (MSC) | Stolcke et al. [10] | ❌ No | 15.14% | 23.65% |
| CRNN + Gap Heuristic | Jarsanath et al. [14] | ⚠️ Partial | — | 25.73% |
| Bi-LSTM OSD + Resegmentation | Bredin et al. [12] | ⚠️ Partial | — | 13.63% |
| Supervised Hierarchical Graph (SHARC) | Singh et al. [46] | ⚠️ Partial | — | 12.56% |
| Stride-3 + Relative MCS ($f=0.01$) | Yamaguchi (2026) | ⚠️ Partial | — | **7.90%** |
| **HOARD Framework (OOA-SC + SSA + OSH)** | **Gupta et al. (2025)** | **✅ Full** | **8.76%** | **12.07%** |

---

## 📈 Visual Research Diagnostics

Running the diagnostic suite generates high-resolution publication-grade analytics:

![Figure 1: HOARD Diagnostics Suite](figures/figure1_hoard_diagnostics.png)

1. **(a) Refined Cosine Similarity Matrix:** Symmetrized and $k$-NN thresholded block similarity matrix.
2. **(b) 2D PCA Speaker Latent Space:** Clear cluster segregation in feature space.
3. **(c) Multi-Speaker Overlap-Aware Timeline:** Gantt chart displaying simultaneous speaker tracks in red hatch.
4. **(d) Speaker Participation Breakdown:** Speech duration, percentage, and official evaluation metrics (DER, Purity, Coverage, ARI).

---

## 🚀 Quickstart

### 1. Installation
```bash
git clone https://github.com/saisaran158/Kaggle_Research_Papers.git
cd Kaggle_Research_Papers
pip install -r requirements.txt
```

### 2. Run Speaker Diarization on an Audio File
```bash
python run_diarization.py --audio sample_conversation.wav --output_rttm predictions.rttm --plot diagnostics.png
```

### 3. Generate Research Benchmark Plots
```bash
python examples/generate_research_plots.py
```

---

## 📂 Repository Structure

```
Kaggle_Research_Papers/
├── README.md                          # Research documentation and benchmark summary
├── requirements.txt                   # Dependencies
├── run_diarization.py                 # CLI executable for diarization and RTTM export
├── hoard_diarization/                 # Core Research Package
│   ├── __init__.py                    # Package interface
│   ├── vad.py                         # Voice Activity Detection (VAD)
│   ├── embeddings.py                  # Deep TDNN + Statistical Pooling + L2 Normalization
│   ├── overlap_detector.py            # Overlapped Speech Detection (OSD)
│   ├── clustering.py                  # OOA-SC (Spectral Clustering) + Relative MCS (f=0.01)
│   ├── ssa_osh.py                     # Second Speaker Assignment (SSA) & OSH Module (HL1, HL2, HL3)
│   ├── rttm_handler.py                # NIST Standard .rttm file parser and exporter
│   ├── metrics.py                     # Official DER (0.25s collar), JER, Purity, Coverage, ARI
│   ├── visualizer.py                  # Publication diagnostic plots generator
│   └── pipeline.py                    # Unified end-to-end pipeline
├── examples/
│   └── generate_research_plots.py     # Reproduces research comparison plots
└── figures/                           # Generated publication figures
    ├── figure1_hoard_diagnostics.png
    └── figure2_der_comparison.png
```

---

## 📜 Standard RTTM Output Format

Predictions are exported in standard NIST format:
```text
SPEAKER voxconverse_sample 1 1.000 8.000 <NA> <NA> SPEAKER_01 <NA> <NA>
SPEAKER voxconverse_sample 1 7.000 8.000 <NA> <NA> SPEAKER_02 <NA> <NA>
SPEAKER voxconverse_sample 1 13.000 8.000 <NA> <NA> SPEAKER_01 <NA> <NA>
SPEAKER voxconverse_sample 1 20.500 6.500 <NA> <NA> SPEAKER_02 <NA> <NA>
SPEAKER voxconverse_sample 1 26.000 3.500 <NA> <NA> SPEAKER_03 <NA> <NA>
```

---

## 📑 References
- A. Gupta, A. Purwar, *"A Novel Framework to Handle Overlapped Speech for Multiple Speakers in Speaker Diarization"*, **SN Computer Science**, 6:1009, 2025.
- J. Huh, J. S. Chung, A. Nagrani, A. Brown, J.-w. Jung, D. Garcia-Romero, A. Zisserman, *"The VoxCeleb Speaker Recognition Challenge: A Retrospective"*, **IEEE/ACM Transactions on Audio, Speech, and Language Processing**, vol. 32, pp. 3850–3866, 2024.
- F. Yamaguchi, *"Fast and Robust On-Device Speaker Diarization: Relative Minimum Cluster Size for Stride-Accelerated Pipelines"*, **arXiv:2606.08505**, 2026.
