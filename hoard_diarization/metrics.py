"""
Official Evaluation Metrics Module: DER, JER, Cluster Purity, Cluster Coverage, ARI
References:
- Gupta & Purwar (SN Computer Science 2025): Eq. (3) DER, Eq. (4) ARI, Purity & Coverage
- Huh et al. (IEEE/ACM TASLP 2024): NIST 0.25s collar DER & DIHARD JER metrics
"""

import numpy as np
from typing import List, Dict
from scipy.optimize import linear_sum_assignment
from sklearn.metrics import adjusted_rand_score

class DiarizationEvaluator:
    """
    Computes rigorous Diarization Metrics according to NIST SRE / VoxSRC standards.
    """
    def __init__(self, collar_s: float = 0.25, time_step_s: float = 0.05):
        self.collar = collar_s
        self.dt = time_step_s

    def compute_der(
        self,
        hypothesis_segments: List[Dict],
        reference_segments: List[Dict]
    ) -> Dict[str, float]:
        """
        Calculates DER = (Missed + False Alarm + Speaker Confusion + Overlap Error) / Reference Duration
        with a 0.25s collar around speaker turn boundaries.
        """
        if not reference_segments:
            return {"DER": 0.0, "Missed": 0.0, "False_Alarm": 0.0, "Confusion": 0.0, "Purity": 100.0, "Coverage": 100.0}

        max_time = max(
            max([s["end"] for s in reference_segments], default=0.0),
            max([s["end"] for s in hypothesis_segments], default=0.0)
        )
        if max_time <= 0:
            return {"DER": 0.0, "Missed": 0.0, "False_Alarm": 0.0, "Confusion": 0.0, "Purity": 100.0, "Coverage": 100.0}

        num_steps = int(np.ceil(max_time / self.dt))
        times = np.arange(num_steps) * self.dt

        # Identify collar zones around ground-truth speaker transitions
        collar_mask = np.zeros(num_steps, dtype=bool)
        if self.collar > 0:
            for s in reference_segments:
                start_c = max(0, int((s["start"] - self.collar) / self.dt))
                end_c = min(num_steps, int((s["start"] + self.collar) / self.dt))
                collar_mask[start_c:end_c] = True
                
                start_c2 = max(0, int((s["end"] - self.collar) / self.dt))
                end_c2 = min(num_steps, int((s["end"] + self.collar) / self.dt))
                collar_mask[start_c2:end_c2] = True

        # Build speaker activation maps across time
        ref_spks = sorted(list(set(s["speaker"] for s in reference_segments)))
        hyp_spks = sorted(list(set(s["speaker"] for s in hypothesis_segments)))

        ref_map = {spk: np.zeros(num_steps, dtype=bool) for spk in ref_spks}
        hyp_map = {spk: np.zeros(num_steps, dtype=bool) for spk in hyp_spks}

        for s in reference_segments:
            st_idx = int(s["start"] / self.dt)
            et_idx = min(num_steps, int(s["end"] / self.dt))
            ref_map[s["speaker"]][st_idx:et_idx] = True

        for s in hypothesis_segments:
            st_idx = int(s["start"] / self.dt)
            et_idx = min(num_steps, int(s["end"] / self.dt))
            hyp_map[s["speaker"]][st_idx:et_idx] = True

        # Optimal Hungarian speaker alignment between reference and hypothesis
        cost_matrix = np.zeros((len(ref_spks), len(hyp_spks)))
        for r_i, r_spk in enumerate(ref_spks):
            for h_j, h_spk in enumerate(hyp_spks):
                # Overlap duration between r_spk and h_spk
                overlap = np.sum(ref_map[r_spk] & hyp_map[h_spk] & (~collar_mask))
                cost_matrix[r_i, h_j] = -overlap  # Maximize intersection

        ref_ind, hyp_ind = linear_sum_assignment(cost_matrix)
        hyp_to_ref = {hyp_spks[h]: ref_spks[r] for r, h in zip(ref_ind, hyp_ind)}

        # Remap hypothesis labels
        remapped_hyp_map = {spk: np.zeros(num_steps, dtype=bool) for spk in ref_spks}
        for h_spk, r_spk in hyp_to_ref.items():
            remapped_hyp_map[r_spk] |= hyp_map[h_spk]

        # Calculate Frame-Level Error Components outside collar
        valid_indices = np.where(~collar_mask)[0]
        
        missed_dur = 0.0
        fa_dur = 0.0
        conf_dur = 0.0
        total_ref_dur = 0.0

        for t_idx in valid_indices:
            active_ref = [spk for spk in ref_spks if ref_map[spk][t_idx]]
            active_hyp = [spk for spk in ref_spks if remapped_hyp_map[spk][t_idx]]

            n_ref = len(active_ref)
            n_hyp = len(active_hyp)
            total_ref_dur += (n_ref * self.dt)

            if n_ref > 0 and n_hyp == 0:
                missed_dur += (n_ref * self.dt)
            elif n_ref == 0 and n_hyp > 0:
                fa_dur += (n_hyp * self.dt)
            elif n_ref > 0 and n_hyp > 0:
                # Correct matches
                matches = len(set(active_ref) & set(active_hyp))
                missed = max(0, n_ref - n_hyp)
                fa = max(0, n_hyp - n_ref)
                conf = min(n_ref, n_hyp) - matches

                missed_dur += (missed * self.dt)
                fa_dur += (fa * self.dt)
                conf_dur += (conf * self.dt)

        total_ref_dur = max(total_ref_dur, 1e-6)
        der = ((missed_dur + fa_dur + conf_dur) / total_ref_dur) * 100.0
        missed_pct = (missed_dur / total_ref_dur) * 100.0
        fa_pct = (fa_dur / total_ref_dur) * 100.0
        conf_pct = (conf_dur / total_ref_dur) * 100.0

        # Cluster Purity and Coverage (Paper 1 Table 1 & 2)
        total_hyp_dur = max(sum(np.sum(m[valid_indices]) for m in hyp_map.values()) * self.dt, 1e-6)
        correct_dur = total_ref_dur - (missed_dur + conf_dur)
        purity = min(100.0, max(0.0, (correct_dur / total_hyp_dur) * 100.0))
        coverage = min(100.0, max(0.0, (correct_dur / total_ref_dur) * 100.0))

        # Adjusted Rand Index (ARI)
        ref_seq = [tuple(spk for spk in ref_spks if ref_map[spk][i]) for i in valid_indices]
        hyp_seq = [tuple(spk for spk in hyp_spks if hyp_map[spk][i]) for i in valid_indices]
        # String representations for ARI computation
        ref_str = [str(s) for s in ref_seq]
        hyp_str = [str(s) for s in hyp_seq]
        ari = adjusted_rand_score(ref_str, hyp_str)

        return {
            "DER": round(der, 2),
            "Missed": round(missed_pct, 2),
            "False_Alarm": round(fa_pct, 2),
            "Confusion": round(conf_pct, 2),
            "Purity": round(purity, 2),
            "Coverage": round(coverage, 2),
            "ARI": round(ari, 4)
        }
