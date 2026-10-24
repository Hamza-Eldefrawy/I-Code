import time
from pathlib import Path

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

from src import config

SAMPLE_RATE = 16000    # Whisper works on 16 kHz mono audio


class Voice:
    def __init__(self, model_size: str = config.WHISPER_MODEL,
                device: str = config.WHISPER_DEVICE,
                compute_type: str = config.WHISPER_COMPUTE,
                language: str | None = config.WHISPER_LANGUAGE):
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
        self.language = language
        self._stream = None
        self._chunks: list[np.ndarray] = []

    # ---------- recording ----------

    def start_recording(self) -> None:
        if self._stream is not None:
            raise RuntimeError("Already recording.")
        self._chunks = []

        def callback(indata, frames, time_info, status):
            self._chunks.append(indata.copy())     # called by sounddevice for every small block

        self._stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                                      dtype="float32", callback=callback)
        self._stream.start()

    def stop_recording(self) -> np.ndarray:
        """Stops and returns the audio as a 1-D float32 array (16 kHz)."""
        if self._stream is None:
            raise RuntimeError("Not recording.")
        self._stream.stop()
        self._stream.close()
        self._stream = None
        if not self._chunks:
            return np.zeros(0, dtype="float32")
        return np.concatenate(self._chunks, axis=0).flatten()

    def record(self, seconds: float) -> np.ndarray:
        """Fixed-length recording."""
        self.start_recording()
        time.sleep(seconds)
        return self.stop_recording()

    # ---------- transcribing ----------

    def transcribe(self, audio, hint: str | None = None) -> str:
        """audio: a numpy array from the recorder, or a path to an audio file.
        hint: words to bias recognition toward (for example the table's column names).
        Returns "" when nothing was said."""
        if isinstance(audio, Path):
            audio = str(audio)
        if isinstance(audio, np.ndarray):
            too_short = audio.size < SAMPLE_RATE * 0.3
            if too_short or np.abs(audio).max() < config.VOICE_MIN_LEVEL:
                return ""                          # skip Whisper text on silence
        segments, _info = self.model.transcribe(
            audio,
            language=self.language,
            beam_size=5,
            vad_filter=True,                       # drops silent parts
            initial_prompt=hint,
        )
        return " ".join(s.text.strip() for s in segments).strip()
