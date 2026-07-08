import logging
import os
from pathlib import Path
from typing import List, Dict, Any
import uuid

import ollama as ollama_lib
from qdrant_client import QdrantClient, models
from qdrant_client.models import PointStruct, VectorParams, Distance, SparseVectorParams, Modifier

from config import (
    QDRANT_URL, SPARSE_VECTOR_NAME,
    OLLAMA_EMBED_MODEL, TOP_K_RETRIEVAL, OLLAMA_BASE_URL
)

from core.reranker import Reranker
from core.chunking import FileChunker, CodeChunk, ChunkType

CODE_EXTENSIONS = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".jsx": "JavaScript",
    ".java": "Java",
    ".c": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".h": "C/C++ Header",
    ".hpp": "C++ Header",
    ".cs": "C#",
    ".go": "Go",
    ".rs": "Rust",
    ".php": "PHP",
    ".rb": "Ruby",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".scala": "Scala",
    ".m": "Objective-C",
    ".mm": "Objective-C++",
    ".sh": "Shell",
    ".tf": 'Terraform',
    ".bash": "Shell",
    ".zsh": "Shell",
    ".fish": "Shell",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "SASS",
    ".less": "Less",
    ".json": "JSON",
    ".xml": "XML",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".md": "Markdown",
    ".txt": "Text",
    ".sql": "SQL",
    ".r": "R",
    ".R": "R",
    ".lua": "Lua",
    ".vim": "VimL",
    ".pl": "Perl",
}


class CodeIndexer:
    """
    Indexes code files into the specified collection
    """
    def __init__(self, collection: str):
        self.ollama = ollama_lib.Client(host=OLLAMA_BASE_URL)
        self.qdrant = QdrantClient(url=QDRANT_URL, timeout=60)
        self.reranker = Reranker.get_or_create_reranker('default')
        self.chunker = FileChunker()
        self.collection = collection
        self._files_cache: dict[str, dict] = {}

        self._ensure_collection()
        self._build_files_cache()

    def _embed(self, text: str) -> List[float]:
        response = self.ollama.embeddings(model=OLLAMA_EMBED_MODEL, prompt=text)
        return response["embedding"]

    def _ensure_collection(self):
        if not self.qdrant.collection_exists(self.collection):
            print(f"[INDEXER] Creating Qdrant collection: {self.collection}")
            # nomic-embed-text produces 768-dim vectors
            self.qdrant.create_collection(
                collection_name=self.collection,
                vectors_config={"dense": VectorParams(size=768, distance=Distance.COSINE)},
                sparse_vectors_config={
                    SPARSE_VECTOR_NAME: SparseVectorParams(
                        index=models.SparseIndexParams(on_disk=False),
                        modifier=Modifier.IDF
                    )
                }
            )

    def _build_files_cache(self):
        """Build a local cache of indexed files for metadata queries."""
        seen = set()
        result, _ = self.qdrant.scroll(
            collection_name=self.collection,
            limit=10000,
            with_payload=True
        )
        for point in result:
            fp = point.payload.get("file_path", None)
            lang = point.payload.get("language", "unknown")
            modified = int(point.payload.get("modified", '0'))
            if fp is not None and fp not in seen:
                seen.add(fp)
                self._files_cache[fp] = {"path": fp, "language": lang, 'modified': modified}

    def _get_language(self, file):
        p_file = Path(file)
        ext = p_file.suffix
        if ext not in CODE_EXTENSIONS:
            return "Unknown"
        return CODE_EXTENSIONS[ext]

    def build_index(self, files_list: dict[str, int]):
        points = []
        file_cache = {}

        for file, modified in files_list.items():
            if not os.path.exists(file):
                continue

            if file in self._files_cache:
                if self._files_cache[file]["modified"] == modified:
                    continue

            lang = self._get_language(file)
            if lang == "Unknown":
                continue
            try:
                if os.path.getsize(file) > 200_000:
                    continue
            except OSError:
                continue

            with open(file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            if content == "":
                continue

            chunk_type, typed_chunks = self.chunker.chunk_file(file, content, lang)

            for chunk_text, start, end in typed_chunks:
                points.append(PointStruct(
                    id=str(uuid.uuid4()),
                    vector={
                        "dense": self._embed(chunk_text),
                        SPARSE_VECTOR_NAME: models.Document(text=chunk_text, model="Qdrant/bm25")
                    },
                    payload={
                        "file_path": file,
                        "language": lang,
                        "start_line": start,
                        "end_line": end,
                        "content": chunk_text,
                        "type": chunk_type.value,
                        "modified": modified,
                    }
                ))
                # keep the number of points we upload smaller since
                # seeing error for exceeding max payload
                if len(points) == 500:
                    self.qdrant.upsert(collection_name=self.collection, points=points)
                    points = []
            file_cache[file] = {"modified": modified, "path": file, "language": lang}

        if len(points) > 0:
            self.qdrant.upsert(collection_name=self.collection, points=points)
            self._files_cache |= file_cache

    def search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Hybrid search (dense + sparse/BM25) with reranking."""
        query_dense = self._embed(query)

        response = self.qdrant.query_points(
            collection_name=self.collection,
            prefetch=[
                models.Prefetch(query=query_dense, using="dense", limit=TOP_K_RETRIEVAL),
                models.Prefetch(
                    query=models.Document(text=query, model="Qdrant/bm25"),
                    using=SPARSE_VECTOR_NAME,
                    limit=50
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=TOP_K_RETRIEVAL,
            with_payload=models.PayloadSelector(includes=['path', 'start_line', 'end_line', 'content', 'language']),
        )

        candidates = [
            {**p.payload, "score": p.score if hasattr(p, "score") else 0.0}
            for p in response.points
        ]

        reranked = self.reranker.rerank(query, candidates, top_k=k)
        return reranked

    # ─── Public API (unchanged signatures) ────────────────────────────────

    def get_file_list(self) -> dict[str, dict]:
        return self._files_cache

    def get_file_count(self) -> int:
        return len(self._files_cache)

    def get_architecture_summary(self) -> str:
        by_lang: Dict[str, List[str]] = {}
        for f, i in self._files_cache.items():
            lang = i.get("language", "unknown")
            by_lang.setdefault(lang, []).append(f)
        lines = [f"Repository has {len(self._files_cache)} indexed files:\n"]
        for lang, paths in sorted(by_lang.items()):
            lines.append(f"  {lang} ({len(paths)} files):")
            for p in paths[:5]:
                lines.append(f"    - {p}")
            if len(paths) > 5:
                lines.append(f"    ... and {len(paths) - 5} more")
        return "\n".join(lines)
