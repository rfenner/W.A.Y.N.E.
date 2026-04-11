from flashrank import Ranker, RerankRequest
from config import TOP_K_RERANK


class Reranker:
    """
    CPU-optimized reranker using FlashRank with a ~30MB ONNX model.
    Implements retrieve-then-rerank for higher retrieval precision.
    """
    _rankers = {}


    def __init__(self, name:str, model:str="ms-marco-MiniLM-L-12-v2",  cache_dir='/opt'):
        # ms-marco-MiniLM-L-12-v2 is ~30MB, runs fast on CPU, high precision
        self.model = model
        self.cache_dir = cache_dir
        self.name = name
        self.ranker = Ranker(model_name=model, cache_dir=cache_dir)


    def rerank(self, query: str, candidates: list, top_k: int = TOP_K_RERANK) -> list:
        """
        Rerank a list of candidate dicts by relevance to the query.

        Each candidate must have a "content" key with the text to rank.
        Returns top_k most relevant candidates, preserving original dict structure.
        """
        if not candidates:
            return []

        passages = [
            {"id": str(i), "text": c.get("content", ""), "meta": c}
            for i, c in enumerate(candidates)
        ]

        request = RerankRequest(query=query, passages=passages)
        results = self.ranker.rerank(request)

        # Reconstruct original dicts in reranked order
        reranked = []
        for r in results[:top_k]:
            original = r["meta"]
            original["rerank_score"] = r.get("score", 0.0)
            reranked.append(original)

        return reranked

    @classmethod
    def get_or_create_reranker(cls, name:str, model:str="ms-marco-MiniLM-L-12-v2", cache_dir='/opt'):
        if name in cls._rankers:
            ranker = cls._rankers[name]
            if ranker.model != model or ranker.cache_dir != cache_dir:
                raise RuntimeError(f"A reranker exists with name '{name}' but it has a different model or cache directory than requested")
            return ranker

        ranker = Reranker(name=name, model=model, cache_dir=cache_dir)
        if name not in Reranker._rankers:
            cls._rankers[name] = ranker
        return ranker

    @classmethod
    def get_ranker(cls, name:str):
        if name not in cls._rankers:
            raise RuntimeError(f'Failed to find reranker with name: {name}')
        return cls._rankers[name]
