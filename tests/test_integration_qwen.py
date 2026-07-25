from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

from prompt_radar.config import load_config
from prompt_radar.embeddings.qwen import QwenEmbeddingService


@pytest.mark.integration
def test_real_qwen_embedding_smoke() -> None:
    if os.getenv("RUN_QWEN_INTEGRATION") != "1":
        pytest.skip("Set RUN_QWEN_INTEGRATION=1 after explicit model download")
    service = QwenEmbeddingService(
        load_config(Path("configs/pipeline.yaml")), offline=True
    )
    vectors = service.encode(
        ["Найди общий слот команды", "Подготовь сводку почты"],
        mode="query",
    )
    assert vectors.shape[0] == 2
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1e-4)

