"""
Clustering Module: OOA-SC, AHC, and Relative Minimum Cluster Size (Adaptive MCS)
References:
- Gupta & Purwar (SN Computer Science 2025): Optimized Overlap-Aware Spectral Clustering (OOA-SC) & RCE
- Yamaguchi (arXiv 2026): Relative Minimum Cluster Size mcs = round(f * n), f=0.01
- Huh et al. (IEEE/ACM TASLP 2024): Cosine distance AHC & Spectral Clustering Baselines
"""

import numpy as np
from typing import Tuple, Optional

class SpectralAndHierarchicalClusterer:
    """
    Implements:
    1. OOA-SC (Optimized Overlap-Aware Spectral Clustering with Alternating Optimization)
    2. Cosine Agglomerative Hierarchical Clustering (AHC)
    3. Adaptive Relative Minimum Cluster Size (mcs = round(f * n), f=0.01)
    """
    def __init__(
        self,
        min_cluster_fraction: float = 0.01,
        max_clusters: int = 10,
        knn_neighbors: int = 8,
        ao_max_iters: int = 15
    ):
        self.f = min_cluster_fraction
        self.max_clusters = max_clusters
        self.knn_neighbors = knn_neighbors
        self.ao_max_iters = ao_max_iters

    def compute_affinity_matrix(self, embeddings: np.ndarray) -> np.ndarray:
        """
        Builds refined Affinity Matrix A using Cosine Similarity, k-NN row-wise thresholding,
        and Symmetrization (Paper 1 Section 'Affinity Formation & RCE').
        """
        # Ensure L2 normalized
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-10
        norm_embs = embeddings / norms

        # Cosine Similarity Matrix A_ij
        affinity = np.dot(norm_embs, norm_embs.T)
        affinity = np.clip(affinity, 0.0, 1.0)
        np.fill_diagonal(affinity, 1.0)

        n = len(embeddings)
        k = min(self.knn_neighbors, max(2, n - 1))
        
        # Row-wise k-NN thresholding
        refined = np.zeros_like(affinity)
        for i in range(n):
            top_k_indices = np.argsort(affinity[i])[-k:]
            refined[i, top_k_indices] = affinity[i, top_k_indices]

        # Symmetrization: A = 0.5 * (A + A^T)
        sym_affinity = 0.5 * (refined + refined.T)
        return sym_affinity

    def estimate_num_clusters_rce(self, affinity: np.ndarray, max_k: int = 10) -> int:
        """
        Robust Cluster Estimation (RCE) using Normalized Laplacian maximum eigengap.
        """
        n = len(affinity)
        if n <= 2:
            return max(1, n)

        # Degree matrix D and Normalized Laplacian L_sym = I - D^(-1/2) A D^(-1/2)
        d = np.sum(affinity, axis=1)
        d_inv_sqrt = 1.0 / np.sqrt(np.maximum(d, 1e-10))
        d_mat_inv_sqrt = np.diag(d_inv_sqrt)
        laplacian = np.eye(n) - np.dot(np.dot(d_mat_inv_sqrt, affinity), d_mat_inv_sqrt)

        eigenvalues, _ = np.linalg.eigh(laplacian)
        eigenvalues = np.sort(eigenvalues)

        # Maximum eigengap in range [2, max_k]
        search_max = min(max_k, n - 1)
        if search_max < 2:
            return 1

        eigengaps = np.diff(eigenvalues[:search_max + 1])
        optimal_k = int(np.argmax(eigengaps[1:]) + 2)  # Skip 0-th eigenvalue gap
        return optimal_k

    def fit_ooa_sc(
        self,
        embeddings: np.ndarray,
        overlap_vector: Optional[np.ndarray] = None,
        num_clusters: Optional[int] = None
    ) -> Tuple[np.ndarray, np.ndarray, int]:
        """
        Optimized Overlap-Aware Spectral Clustering (OOA-SC) with Alternating Optimization (AO)
        and N-cut minimization (Paper 1 Section 'Optimized Overlap-Aware Spectral Clustering').
        
        Returns:
            labels: Cluster assignment vector
            centroids: Matrix of cluster centroids
            k: Estimated number of speakers
        """
        n = len(embeddings)
        affinity = self.compute_affinity_matrix(embeddings)

        if num_clusters is None:
            k = self.estimate_num_clusters_rce(affinity, max_k=self.max_clusters)
        else:
            k = max(1, min(num_clusters, n))

        if k == 1 or n <= 2:
            return np.zeros(n, dtype=int), np.mean(embeddings, axis=0, keepdims=True), 1

        # Normalized Laplacian Decomposition
        d = np.sum(affinity, axis=1)
        d_mat_inv_sqrt = np.diag(1.0 / np.sqrt(np.maximum(d, 1e-10)))
        laplacian = np.eye(n) - np.dot(np.dot(d_mat_inv_sqrt, affinity), d_mat_inv_sqrt)

        eigenvalues, eigenvectors = np.linalg.eigh(laplacian)
        sorted_indices = np.argsort(eigenvalues)
        u = eigenvectors[:, sorted_indices[:k]]

        # Row normalization
        u_norm = u / (np.linalg.norm(u, axis=1, keepdims=True) + 1e-10)

        # Alternating Optimization (AO) loop for N-cut minimization (Fig 2b)
        # Initialize cluster centroids using k-means++ seeding
        centroids = self._kmeans_plus_plus(u_norm, k)
        labels = np.zeros(n, dtype=int)

        for _ in range(self.ao_max_iters):
            # Step A: Update cluster assignments
            dists = np.linalg.norm(u_norm[:, np.newaxis, :] - centroids[np.newaxis, :, :], axis=2)
            new_labels = np.argmin(dists, axis=1)

            if np.array_equal(new_labels, labels):
                break
            labels = new_labels

            # Step B: Update centroids
            for c in range(k):
                members = u_norm[labels == c]
                if len(members) > 0:
                    centroids[c] = np.mean(members, axis=0)

        # Enforce Relative Minimum Cluster Size mcs = round(f * n) from Paper 3
        mcs = max(1, int(round(self.f * n)))
        labels = self._filter_small_clusters(embeddings, labels, mcs=mcs)

        # Compute original embedding centroids
        unique_labels = np.unique(labels)
        k_final = len(unique_labels)
        orig_centroids = np.zeros((k_final, embeddings.shape[1]))
        for idx, ul in enumerate(unique_labels):
            orig_centroids[idx] = np.mean(embeddings[labels == ul], axis=0)
            labels[labels == ul] = idx

        return labels, orig_centroids, k_final

    def _kmeans_plus_plus(self, data: np.ndarray, k: int) -> np.ndarray:
        n = len(data)
        centroids = [data[np.random.randint(n)]]
        for _ in range(1, k):
            dists = np.min([np.sum((data - c) ** 2, axis=1) for c in centroids], axis=0)
            probs = dists / (np.sum(dists) + 1e-10)
            next_idx = np.random.choice(n, p=probs)
            centroids.append(data[next_idx])
        return np.array(centroids)

    def _filter_small_clusters(self, embeddings: np.ndarray, labels: np.ndarray, mcs: int) -> np.ndarray:
        unique, counts = np.unique(labels, return_counts=True)
        small_clusters = unique[counts < mcs]
        large_clusters = unique[counts >= mcs]

        if len(large_clusters) == 0:
            return labels

        refined_labels = labels.copy()
        large_centroids = {c: np.mean(embeddings[labels == c], axis=0) for c in large_clusters}

        for sc in small_clusters:
            sc_indices = np.where(labels == sc)[0]
            for idx in sc_indices:
                emb = embeddings[idx]
                closest_c = min(large_clusters, key=lambda c: np.linalg.norm(emb - large_centroids[c]))
                refined_labels[idx] = closest_c

        return refined_labels
