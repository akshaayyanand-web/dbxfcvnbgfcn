"""Shared fixtures. All videos generated here are SYNTHETIC (see backend/vision/synthetic.py)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd
import pytest

from backend.vision.synthetic import SyntheticFlameSpec, write_synthetic_video, write_vfr_synthetic_video

requires_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg executable not installed")


@pytest.fixture(scope="session")
def video_dir(tmp_path_factory) -> Path:
    return tmp_path_factory.mktemp("videos")


@pytest.fixture(scope="session")
def demo_video(video_dir) -> tuple[Path, pd.DataFrame, SyntheticFlameSpec]:
    """5 s, 30 fps, growing flame with drift; extinguishes at 4.2 s."""
    spec = SyntheticFlameSpec()
    path = video_dir / "SYNTHETIC_demo.mp4"
    gt = write_synthetic_video(path, spec)
    return path, pd.DataFrame(gt["frames"]), spec


@pytest.fixture(scope="session")
def disturbed_video(video_dir) -> tuple[Path, pd.DataFrame, SyntheticFlameSpec]:
    """2 s with simulated detection dropouts and a distractor blob on some frames."""
    spec = SyntheticFlameSpec(
        duration_s=2.0, extinction_time_s=None, dropout_frames=(20, 21, 22), distractor_frames=(30, 31, 40), seed=3)
    path = video_dir / "SYNTHETIC_disturbed.mp4"
    gt = write_synthetic_video(path, spec)
    return path, pd.DataFrame(gt["frames"]), spec


@pytest.fixture(scope="session")
def vfr_video(video_dir):
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg executable not installed")
    spec = SyntheticFlameSpec(duration_s=2.0, extinction_time_s=None, seed=5)
    path = video_dir / "SYNTHETIC_vfr.mp4"
    gt = write_vfr_synthetic_video(path, spec, drop_frames=[3, 7, 8, 15, 22, 23, 24, 40, 41])
    return path, pd.DataFrame(gt["frames"]), spec
