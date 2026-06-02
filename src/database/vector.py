"""hnswlib-backed in-process vector store."""

import json
from pathlib import Path
from typing import Optional


class VectorStore:
    """Vector similarity search via hnswlib (in-process, no external service)."""

    def __init__(self, vector_size: int = 384, persist_path: Optional[str] = None):
        import hnswlib

        self.vector_size = vector_size
        self.persist_path = Path(persist_path) if persist_path else None

        self._id_map: dict[str, int] = {}
        self._reverse_map: dict[int, str] = {}
        self._payloads: dict[int, dict] = {}
        self._next_label = 0
        self._deleted: set[str] = set()

        # Try to load persisted index; otherwise create fresh
        loaded = self._load()
        if not loaded:
            self._index = hnswlib.Index(space="cosine", dim=vector_size)
            self._index.init_index(max_elements=100_000, ef_construction=200, M=16)
            self._index.set_ef(64)

    # -- Persistence ----------------------------------------------------------

    def _load(self) -> bool:
        """Load persisted index. Returns True if loaded successfully."""
        if not self.persist_path or not self.persist_path.exists():
            return False
        try:
            index_path = self.persist_path / "index.bin"
            meta_path = self.persist_path / "meta.json"

            if not (index_path.exists() and meta_path.exists()):
                return False

            with open(meta_path) as f:
                meta = json.load(f)

            self._next_label = meta["next_label"]
            self._deleted = set(meta.get("deleted", []))
            self._id_map = {k: v for k, v in meta["id_map"].items()}
            self._reverse_map = {int(k): v for k, v in meta["reverse_map"].items()}
            self._payloads = {int(k): v for k, v in meta["payloads"].items()}

            count = len(self._id_map)
            if count > 0:
                import hnswlib
                self._index = hnswlib.Index(space="cosine", dim=self.vector_size)
                self._index.load_index(str(index_path), max_elements=max(count * 2, 100_000))
                self._index.set_ef(64)
            return True
        except Exception:
            return False

    def _save(self):
        if not self.persist_path:
            return
        self.persist_path.mkdir(parents=True, exist_ok=True)

        import hnswlib as _hnswlib

        try:
            count = self._index.get_current_count()
            if count > 0:
                self._index.save_index(str(self.persist_path / "index.bin"))
        except Exception:
            pass

        meta = {
            "next_label": self._next_label,
            "deleted": list(self._deleted),
            "id_map": self._id_map,
            "reverse_map": {str(k): v for k, v in self._reverse_map.items()},
            "payloads": {str(k): v for k, v in self._payloads.items()},
        }
        with open(self.persist_path / "meta.json", "w") as f:
            json.dump(meta, f)

    # -- Internal helpers -----------------------------------------------------

    def _ensure_label(self, point_id: str) -> int:
        if point_id in self._id_map:
            return self._id_map[point_id]
        label = self._next_label
        self._next_label += 1
        self._id_map[point_id] = label
        self._reverse_map[label] = point_id
        return label

    def _match_filters(self, label: int, filter_conditions: dict) -> bool:
        payload = self._payloads.get(label, {})
        for key, value in filter_conditions.items():
            if key not in payload:
                return False
            if isinstance(value, dict):
                if "gte" in value and payload[key] < value["gte"]:
                    return False
                if "lte" in value and payload[key] > value["lte"]:
                    return False
            elif payload[key] != value:
                return False
        return True

    # -- Public API -----------------------------------------------------------

    def insert(self, point_id: str, vector: list[float], payload: Optional[dict] = None):
        label = self._ensure_label(point_id)
        self._index.add_items([vector], [label])
        if payload:
            self._payloads[label] = payload
        self._save()

    def upsert_batch(self, points: list[dict]):
        if not points:
            return
        vectors = []
        labels = []
        for p in points:
            label = self._ensure_label(p["id"])
            vectors.append(p["vector"])
            labels.append(label)
            if "payload" in p:
                self._payloads[label] = p["payload"]
        self._index.add_items(vectors, labels)
        self._save()

    def search(self, vector: list[float], top_k: int = 20,
               score_threshold: Optional[float] = None,
               filter_conditions: Optional[dict] = None) -> list[tuple[str, float]]:
        count = self._index.get_current_count()
        if count == 0:
            return []

        search_limit = min(top_k * 3 if filter_conditions else top_k, count)
        labels, distances = self._index.knn_query([vector], k=search_limit)

        results = []
        for label, distance in zip(labels[0], distances[0]):
            point_id = self._reverse_map.get(label)
            if not point_id or point_id in self._deleted:
                continue
            score = 1.0 - distance
            if score_threshold is not None and score < score_threshold:
                continue
            if filter_conditions and not self._match_filters(label, filter_conditions):
                continue
            results.append((point_id, score))
            if len(results) >= top_k:
                break
        return results

    def search_with_payload(self, vector: list[float], top_k: int = 20,
                            score_threshold: Optional[float] = None) -> list[dict]:
        results = self.search(vector, top_k, score_threshold)
        out = []
        for point_id, _score in results:
            label = self._id_map.get(point_id)
            if label is not None:
                out.append(self._payloads.get(label, {}))
        return out

    def delete(self, point_id: str):
        self._deleted.add(point_id)
        self._save()

    def count(self) -> int:
        return self._index.get_current_count() - len(self._deleted)

    def close(self):
        self._save()
