"""FastEmbed real ate o tokenizer, com tokenizer/ONNX locais e sem downloads."""

from pathlib import Path
from types import SimpleNamespace

import numpy as np
from fastembed import TextEmbedding
from fastembed.common.model_description import PoolingType
from fastembed.text.custom_text_embedding import CustomTextEmbedding


def install_fake_fastembed(monkeypatch):
    received: list[str] = []

    class Tokenizer:
        def encode_batch(self, texts):
            received.extend(texts)
            return [SimpleNamespace(ids=[1, 2], attention_mask=[1, 1]) for _ in texts]

    class OnnxSession:
        def get_inputs(self):
            return [SimpleNamespace(name=name) for name in ("input_ids", "attention_mask")]

        def run(self, names, inputs):
            return [np.ones((len(inputs["input_ids"]), 2, 384), dtype=np.float32)]

    # Nao chama __init__: ele resolveria/baixaria os arquivos do modelo.
    encoder = CustomTextEmbedding.__new__(CustomTextEmbedding)
    encoder.model_name = "intfloat/multilingual-e5-small"
    encoder.cache_dir = Path(".")
    encoder.providers = None
    encoder.cuda = False
    encoder.device_ids = None
    encoder.model = OnnxSession()
    encoder.tokenizer = Tokenizer()
    encoder._pooling = PoolingType.MEAN
    encoder._normalization = True
    wrapper = TextEmbedding.__new__(TextEmbedding)
    wrapper.model = encoder
    monkeypatch.setattr("fastembed.TextEmbedding", lambda **kwargs: wrapper)
    return SimpleNamespace(received=received, wrapper=wrapper, encoder=encoder)
