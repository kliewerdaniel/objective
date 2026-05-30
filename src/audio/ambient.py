"""Ambient audio generation for broadcast."""

import numpy as np
from pathlib import Path
from typing import Optional


class AmbientGenerator:
    def __init__(self, sample_rate: int = 22050):
        self.sample_rate = sample_rate
        self._cache: dict[str, np.ndarray] = {}

    def generate_intro(self, duration_sec: float = 8.0) -> np.ndarray:
        t = np.linspace(0, duration_sec, int(self.sample_rate * duration_sec), endpoint=False)
        low_drone = 0.15 * np.sin(2 * np.pi * 55 * t)
        mid_pad = 0.08 * np.sin(2 * np.pi * 110 * t)
        fade = np.minimum(1.0, t / 2.0)
        return (low_drone + mid_pad) * fade * 0.3

    def generate_outro(self, duration_sec: float = 6.0) -> np.ndarray:
        t = np.linspace(0, duration_sec, int(self.sample_rate * duration_sec), endpoint=False)
        low_drone = 0.12 * np.sin(2 * np.pi * 45 * t)
        fade = np.maximum(0.0, 1.0 - t / 3.0)
        return low_drone * fade * 0.2

    def generate_transition(self, duration_sec: float = 3.0) -> np.ndarray:
        t = np.linspace(0, duration_sec, int(self.sample_rate * duration_sec), endpoint=False)
        tone = 0.06 * np.sin(2 * np.pi * 220 * t) * np.exp(-2 * t / duration_sec)
        return tone * 0.15

    def generate_atmospheric(self, duration_sec: float = 30.0) -> np.ndarray:
        t = np.linspace(0, duration_sec, int(self.sample_rate * duration_sec), endpoint=False)
        np.random.seed(42)
        noise = np.random.randn(len(t)) * 0.01
        low = 0.05 * np.sin(2 * np.pi * 60 * t)
        mid = 0.03 * np.sin(2 * np.pi * 130 * t)
        return (noise + low + mid) * 0.2

    def mix_with_speech(self, speech: np.ndarray, ambient_type: str = "atmospheric",
                        ambient_gain: float = 0.15) -> np.ndarray:
        if ambient_type not in self._cache:
            ambient = self._generate_cached(ambient_type, len(speech) / self.sample_rate)
            self._cache[ambient_type] = ambient
        ambient = self._cache[ambient_type]
        if len(ambient) < len(speech):
            ambient = np.tile(ambient, int(np.ceil(len(speech) / len(ambient))))[:len(speech)]
        else:
            ambient = ambient[:len(speech)]
        return speech + ambient * ambient_gain

    def _generate_cached(self, ambient_type: str, duration: float) -> np.ndarray:
        gen = {
            "intro": self.generate_intro,
            "outro": self.generate_outro,
            "transition": self.generate_transition,
            "atmospheric": self.generate_atmospheric,
        }
        return gen.get(ambient_type, self.generate_atmospheric)(duration)
