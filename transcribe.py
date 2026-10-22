#!/usr/bin/env python3
"""Transcreve os WAVs de uma pasta com faster-whisper e grava um JSON por arquivo.

Uso: transcribe.py <pasta de wavs> [modelo]
"""
import json
import sys
import wave
from pathlib import Path

import numpy as np

from faster_whisper import WhisperModel


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows usa cp1252 em pipes
    folder = Path(sys.argv[1])
    model = WhisperModel(sys.argv[2] if len(sys.argv) > 2 else "small",
                         device="cpu", compute_type="int8", cpu_threads=8)
    for wav in sorted(folder.glob("*.wav")):
        out = wav.with_suffix(".json")
        if out.exists():
            continue
        # WAV 16 kHz mono s16 gerado pelo extract_audio.py; lido direto para evitar o PyAV
        with wave.open(str(wav)) as w:
            audio = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        segments, info = model.transcribe(audio, language="pt", vad_filter=True)
        text = " ".join(s.text.strip() for s in segments)
        out.write_text(json.dumps({"file": wav.stem, "duration": info.duration,
                                   "text": text}, ensure_ascii=False))
        print(f"{wav.stem} ({info.duration:.0f}s): {text[:100]}", flush=True)


if __name__ == "__main__":
    main()
