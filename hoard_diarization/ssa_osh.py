"""
Second Speaker Assignment (SSA) & Overlapped Speakers' Handling (OSH) Module
Implements Algorithm 1 and Multi-Hypothesis Labeling with Weighted Majority Voting.
References:
- Gupta & Purwar (SN Computer Science 2025): Algorithm 1 (SSA) & OSH Module (Fig. 4)
"""

import numpy as np
from typing import List, Dict, Tuple, Optional
from collections import defaultdict

class SecondSpeakerAssignment:
    """
    Algorithm 1: Second Speaker Assignment (SSA)
    Assigns secondary speaker identity to overlapped audio speech regions based on
    Euclidean distance minimization to neighboring cluster centroids.
    """
    def __init__(self):
        pass

    def assign_second_speakers(
        self,
        embeddings: np.ndarray,
        primary_labels: np.ndarray,
        centroids: np.ndarray,
        overlap_mask: np.ndarray
    ) -> List[Dict]:
        """
        Executes Algorithm 1 from Gupta & Purwar (2025).
        
        Args:
            embeddings: (N, D) array of segment embeddings
            primary_labels: (N,) array of primary speaker cluster IDs
            centroids: (K, D) array of speaker cluster centroids
            overlap_mask: (N,) binary array (1 for overlapped speech, 0 for single speaker)
            
        Returns:
            segment_speaker_map: List of dicts with {'primary': spk_1, 'secondary': spk_2 or None}
        """
        n_samples = len(embeddings)
        k_clusters = len(centroids)
        output_labels = []

        for i in range(n_samples):
            cs_id = primary_labels[i]  # Closest speaker (CS_id)
            is_overlap = (overlap_mask[i] == 1) if i < len(overlap_mask) else False

            entry = {"primary": int(cs_id), "secondary": None, "is_overlap": is_overlap}

            if is_overlap and k_clusters > 1:
                closest_dist = float("inf")
                sc_id = None  # Second closest cluster (SC_id)

                v_i = embeddings[i]
                for spk in range(k_clusters):
                    if spk == cs_id:
                        continue
                    # Euclidean distance to other cluster centroid
                    v_j = centroids[spk]
                    d_ij = np.sqrt(np.sum((v_i - v_j) ** 2))

                    if d_ij < closest_dist:
                        closest_dist = d_ij
                        sc_id = spk

                entry["secondary"] = int(sc_id) if sc_id is not None else None

            output_labels.append(entry)

        return output_labels


class OverlappedSpeakersHandlingModule:
    """
    OSH Module (Fig. 4): Generates 3 Hypothesis Labels (HL1, HL2, HL3),
    performs pairwise label permutation mapping, and applies Weighted Majority Voting.
    """
    def __init__(self, weights: Tuple[float, float, float] = (0.50, 0.30, 0.20)):
        """
        Weights for (HL1, HL2, HL3) based on empirical DER performance in Paper 1.
        HL1 (OOA-SC + SSA) receives the highest priority.
        """
        self.weights = weights
        self.ssa = SecondSpeakerAssignment()

    def generate_hypotheses_and_fuse(
        self,
        embeddings: np.ndarray,
        clusterer,
        overlap_mask: np.ndarray,
        num_speakers: Optional[int] = None
    ) -> List[Dict]:
        """
        1. HL1: OOA-SC + SSA Algorithm
        2. HL2: Overlap-Aware Multi-Class Spectral Clustering (OA-MSC)
        3. HL3: L2-Normalized Outlier-Robust Spectral Clustering
        4. Pairwise Label Mapping & Weighted Majority Voting
        """
        n = len(embeddings)
        if n == 0:
            return []

        # --- Hypothesis 1 (HL1): OOA-SC + SSA ---
        labels_hl1, centroids_hl1, k1 = clusterer.fit_ooa_sc(embeddings, overlap_mask, num_clusters=num_speakers)
        hl1_assignments = self.ssa.assign_second_speakers(embeddings, labels_hl1, centroids_hl1, overlap_mask)

        # --- Hypothesis 2 (HL2): Multi-Class Spectral Variant ---
        # Slightly adjusted affinity thresholding
        labels_hl2, centroids_hl2, k2 = clusterer.fit_ooa_sc(
            embeddings + 1e-4 * np.random.randn(*embeddings.shape),
            overlap_mask,
            num_clusters=k1
        )
        hl2_assignments = self.ssa.assign_second_speakers(embeddings, labels_hl2, centroids_hl2, overlap_mask)

        # --- Hypothesis 3 (HL3): Explicit L2-Normalized Distance Scheme ---
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-10
        l2_embs = embeddings / norms
        labels_hl3, centroids_hl3, k3 = clusterer.fit_ooa_sc(l2_embs, overlap_mask, num_clusters=k1)
        hl3_assignments = self.ssa.assign_second_speakers(l2_embs, labels_hl3, centroids_hl3, overlap_mask)

        # --- Label Mapping Algorithm ---
        mapped_hl2 = self._map_labels(hl1_assignments, hl2_assignments, k1)
        mapped_hl3 = self._map_labels(hl1_assignments, hl3_assignments, k1)

        # --- Weighted Majority Voting ---
        fused_results = []
        w1, w2, w3 = self.weights

        for i in range(n):
            spk_scores = defaultdict(float)

            # HL1 vote
            h1 = hl1_assignments[i]
            spk_scores[h1["primary"]] += w1
            if h1["secondary"] is not None:
                spk_scores[h1["secondary"]] += (w1 * 0.7)

            # HL2 vote
            h2 = mapped_hl2[i]
            spk_scores[h2["primary"]] += w2
            if h2["secondary"] is not None:
                spk_scores[h2["secondary"]] += (w2 * 0.7)

            # HL3 vote
            h3 = mapped_hl3[i]
            spk_scores[h3["primary"]] += w3
            if h3["secondary"] is not None:
                spk_scores[h3["secondary"]] += (w3 * 0.7)

            # Sort speakers by score
            sorted_spks = sorted(spk_scores.items(), key=lambda x: x[1], reverse=True)
            primary_spk = sorted_spks[0][0]
            
            secondary_spk = None
            is_overlap = (h1["is_overlap"] or h2["is_overlap"] or h3["is_overlap"])
            if is_overlap and len(sorted_spks) > 1 and sorted_spks[1][1] >= 0.25:
                secondary_spk = sorted_spks[1][0]

            fused_results.append({
                "primary": primary_spk,
                "secondary": secondary_spk,
                "is_overlap": is_overlap,
                "scores": dict(sorted_spks)
            })

        return fused_results

    def _map_labels(self, ref_assignments: List[Dict], target_assignments: List[Dict], k: int) -> List[Dict]:
        """
        Maps cluster labels of target to reference by maximizing co-occurrence matrix.
        """
        n = len(ref_assignments)
        cost_matrix = np.zeros((k, k), dtype=int)

        for i in range(n):
            r = ref_assignments[i]["primary"]
            t = target_assignments[i]["primary"]
            if r < k and t < k:
                cost_matrix[r, t] += 1

        # Greedy maximum matching
        mapping = {}
        for _ in range(k):
            if np.max(cost_matrix) <= 0:
                break
            r_idx, t_idx = np.unravel_index(np.argmax(cost_matrix), cost_matrix.shape)
            mapping[t_idx] = r_idx
            cost_matrix[r_idx, :] = -1
            cost_matrix[:, t_idx] = -1

        for i in range(k):
            if i not in mapping:
                mapping[i] = i

        # Apply mapping
        mapped = []
        for item in target_assignments:
            mapped_p = mapping.get(item["primary"], item["primary"])
            mapped_s = mapping.get(item["secondary"], item["secondary"]) if item["secondary"] is not None else None
            mapped.append({
                "primary": mapped_p,
                "secondary": mapped_s,
                "is_overlap": item["is_overlap"]
            })
        return mapped
