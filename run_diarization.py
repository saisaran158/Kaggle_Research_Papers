#!/usr/bin/env python3
"""
HOARD Speaker Diarization CLI
Usage:
    python run_diarization.py --audio path/to/audio.wav --output_rttm predictions.rttm --plot diagnostics.png
"""

import argparse
import sys
import os
import wave
import numpy as np

from hoard_diarization import HOARDDiarizationPipeline

def generate_synthetic_multitalker_wav(file_path: str, duration_s: float = 30.0, sample_rate: int = 16000):
    """Generates a multi-speaker conversational WAV file with overlaps for testing."""
    os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
    t = np.linspace(0, duration_s, int(sample_rate * duration_s), endpoint=False)
    signal = np.zeros_like(t)

    # Speaker 1: F0 ~ 130 Hz (e.g. 0-8s, 12-20s, 24-30s)
    spk1_active = ((t >= 1.0) & (t <= 9.0)) | ((t >= 13.0) & (t <= 21.0)) | ((t >= 25.0) & (t <= 29.5))
    s1_voice = 0.5 * np.sin(2 * np.pi * 130 * t) + 0.25 * np.sin(2 * np.pi * 260 * t) + 0.15 * np.sin(2 * np.pi * 390 * t)
    signal += s1_voice * spk1_active

    # Speaker 2: F0 ~ 210 Hz (e.g. 7-15s [overlap with spk1 from 7-9s and 13-15s], 18-26s)
    spk2_active = ((t >= 7.0) & (t <= 15.0)) | ((t >= 20.5) & (t <= 27.0))
    s2_voice = 0.45 * np.sin(2 * np.pi * 210 * t) + 0.22 * np.sin(2 * np.pi * 420 * t) + 0.12 * np.sin(2 * np.pi * 630 * t)
    signal += s2_voice * spk2_active

    # Speaker 3: F0 ~ 300 Hz (e.g. 26.0 - 29.5s)
    spk3_active = (t >= 26.0) & (t <= 29.5)
    s3_voice = 0.4 * np.sin(2 * np.pi * 300 * t) + 0.2 * np.sin(2 * np.pi * 600 * t)
    signal += s3_voice * spk3_active

    # Add gentle pink/gaussian background noise
    noise = 0.02 * np.random.randn(len(t))
    signal = signal + noise
    signal = np.clip(signal, -0.98, 0.98)
    int16_data = (signal * 32767).astype(np.int16)

    with wave.open(file_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(int16_data.tobytes())

def main():
    parser = argparse.ArgumentParser(description="HOARD: Handled Overlap-Aware Refined Diarization")
    parser.add_argument("--audio", type=str, default="sample_conversation.wav", help="Path to input audio .wav")
    parser.add_argument("--num_speakers", type=int, default=None, help="Number of speakers (None for auto-estimation)")
    parser.add_argument("--ground_truth_rttm", type=str, default=None, help="Path to reference RTTM for evaluation")
    parser.add_argument("--output_rttm", type=str, default="output_predictions.rttm", help="Path to save output RTTM")
    parser.add_argument("--plot", type=str, default="research_diagnostics.png", help="Path to save research diagnostics plot")
    parser.add_argument("--no_osh", action="store_true", help="Disable Overlapped Speakers Handling module")

    args = parser.parse_args()

    if not os.path.exists(args.audio):
        print(f"[*] Input audio not found at '{args.audio}'. Creating synthetic multi-speaker conversation audio...")
        generate_synthetic_multitalker_wav(args.audio, duration_s=30.0)

    print("=" * 65)
    print("      HOARD SPEAKER DIARIZATION RESEARCH FRAMEWORK")
    print("      Ref: SN Computer Science (2025) & IEEE TASLP (2024)")
    print("=" * 65)
    print(f"[*] Input Audio File    : {args.audio}")
    print(f"[*] Output RTTM Path    : {args.output_rttm}")
    print(f"[*] Diagnostic Plot Path: {args.plot}")
    print(f"[*] OSH Module Enabled  : {not args.no_osh}")
    print("-" * 65)

    pipeline = HOARDDiarizationPipeline(
        sample_rate=16000,
        window_duration_s=1.5,
        hop_duration_s=0.5,
        min_cluster_fraction=0.01,
        enable_osh=not args.no_osh
    )

    result = pipeline.diarize_audio(
        audio_path=args.audio,
        num_speakers=args.num_speakers,
        ground_truth_rttm=args.ground_truth_rttm,
        output_rttm_path=args.output_rttm,
        diagnostic_plot_path=args.plot
    )

    print("\n" + "=" * 65)
    print("                 DIARIZATION RESULTS SUMMARY")
    print("=" * 65)
    print(f"Audio URI              : {result['uri']}")
    print(f"Total Audio Duration   : {result['total_duration_sec']} seconds")
    print(f"Estimated Unique Speakers: {result['estimated_speakers']}")
    print("\n--- Speaker Distribution & Active Speaking Time ---")
    for spk, stats in result["speaker_stats"].items():
        print(f"  * {spk:>10} : {stats['total_time_sec']:>6.2f}s ({stats['speaking_percentage']:>5.2f}%) across {stats['turns_count']:>3} turns")

    print("\n--- First 8 Diarized Speaker Segments ---")
    for seg in result["segments"][:8]:
        ov_flag = " [OVERLAPPED]" if seg.get("is_overlap") else ""
        print(f"  [{seg['start']:>6.2f}s -> {seg['end']:>6.2f}s] : {seg['speaker']}{ov_flag}")

    if result.get("metrics"):
        m = result["metrics"]
        print("\n" + "=" * 65)
        print("           OFFICIAL BENCHMARK EVALUATION METRICS")
        print("=" * 65)
        print(f"  - Diarization Error Rate (DER) : {m['DER']}%  (Collar: 0.25s)")
        print(f"    * Missed Speech (MS)         : {m['Missed']}%")
        print(f"    * False Alarm (FA)           : {m['False_Alarm']}%")
        print(f"    * Speaker Confusion (CONF)   : {m['Confusion']}%")
        print(f"  - Cluster Purity               : {m['Purity']}%")
        print(f"  - Cluster Coverage             : {m['Coverage']}%")
        print(f"  - Adjusted Rand Index (ARI)    : {m['ARI']}")
        print("=" * 65)

    print(f"\n[OK] Pipeline complete. Check '{args.plot}' for full visual analytics.")

if __name__ == "__main__":
    main()
