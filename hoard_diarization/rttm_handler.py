"""
RTTM (Rich Transcription Time-Marked) File Handler
Reads, writes, and parses NIST-compliant .rttm files for VoxConverse benchmarking.
References:
- Huh et al. (IEEE/ACM TASLP 2024): NIST SRE / VoxSRC RTTM Evaluation Formats
"""

import os
from typing import List, Dict

class RTTMHandler:
    """
    Standard NIST Rich Transcription Time-Marked (RTTM) parser and exporter.
    Line format:
    SPEAKER <file_id> <channel_id> <tbeg> <tdur> <ortho> <stype> <speaker_name> <conf> <slat>
    """
    @staticmethod
    def read_rttm(file_path: str) -> List[Dict]:
        """
        Parses an RTTM file into structured segment dictionaries.
        """
        segments = []
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"RTTM file not found: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) >= 8 and parts[0] == "SPEAKER":
                    uri = parts[1]
                    channel = int(parts[2])
                    tbeg = float(parts[3])
                    tdur = float(parts[4])
                    speaker = parts[7]
                    segments.append({
                        "uri": uri,
                        "channel": channel,
                        "start": round(tbeg, 3),
                        "end": round(tbeg + tdur, 3),
                        "duration": round(tdur, 3),
                        "speaker": speaker
                    })
        return segments

    @staticmethod
    def write_rttm(segments: List[Dict], output_path: str, uri: str = "voxconverse_rec"):
        """
        Exports diarization segments to NIST standard RTTM file.
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        # Sort by start time
        sorted_segs = sorted(segments, key=lambda x: (x["start"], x["speaker"]))

        with open(output_path, "w", encoding="utf-8") as f:
            for seg in sorted_segs:
                start = seg["start"]
                dur = seg.get("duration", round(seg["end"] - seg["start"], 3))
                spk = seg["speaker"]
                f.write(f"SPEAKER {uri} 1 {start:.3f} {dur:.3f} <NA> <NA> {spk} <NA> <NA>\n")

        print(f"[OK] Saved {len(sorted_segs)} speaker turns to RTTM: {output_path}")
