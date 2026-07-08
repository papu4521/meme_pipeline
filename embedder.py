class SemanticEmbedder:
    def __init__(self):
        self._model = None

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer('all-MiniLM-L6-v2')
        return self._model

    def encode(self, text: str) -> list[float]:
        model = self._get_model()
        # encode returns a numpy array, convert to list
        return model.encode(text).tolist()

embedder = SemanticEmbedder()
