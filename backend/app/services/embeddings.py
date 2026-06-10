import json
import logging
from pathlib import Path

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

from app.config import settings
from app.services.cv_parser import SUPPORTED_EXTENSIONS, extract_text, name_from_filename

logger = logging.getLogger(__name__)

_META_FILE   = Path(settings.cv_directory).parent / "consultants_meta.json"
_MODEL_NAME  = "paraphrase-multilingual-MiniLM-L12-v2"
_MAX_CHARS   = 6000
_VECTOR_SIZE = 384
_COLLECTION  = "matchconsult_cvs"


class EmbeddingService:
    def __init__(self):
        self.model:  SentenceTransformer | None = None
        self.qdrant: QdrantClient | None = None
        self._cv_count: int = 0

    def _ensure_model(self):
        if self.model is None:
            logger.info("Loading sentence-transformer model…")
            self.model = SentenceTransformer(_MODEL_NAME)
            logger.info("Model ready.")

    def _ensure_qdrant(self):
        if self.qdrant is None:
            self.qdrant = QdrantClient(url=settings.qdrant_url)
            logger.info("Qdrant connected at %s", settings.qdrant_url)

    def _load_meta(self) -> dict:
        if _META_FILE.exists():
            with open(_META_FILE, encoding="utf-8") as f:
                return json.load(f)
        return {}

    async def load_cvs(self):
        if settings.demo_mode:
            logger.info("Demo mode — skipping CV/model loading.")
            return

        cv_dir = Path(settings.cv_directory)
        if not cv_dir.exists():
            logger.warning("CV directory not found: %s", cv_dir)
            return

        self._ensure_model()
        self._ensure_qdrant()

        if self.qdrant.collection_exists(_COLLECTION):
            self.qdrant.delete_collection(_COLLECTION)
        self.qdrant.create_collection(
            collection_name=_COLLECTION,
            vectors_config=VectorParams(size=_VECTOR_SIZE, distance=Distance.COSINE),
        )

        meta   = self._load_meta()
        points = []
        idx    = 0

        for cv_path in cv_dir.iterdir():
            if cv_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            cv_id = cv_path.stem
            try:
                text = extract_text(str(cv_path))
                if not text.strip():
                    continue
                embedding = self.model.encode(text[:_MAX_CHARS])
                cv_meta   = meta.get(cv_id, {})
                available = cv_meta.get("available", True)
                status    = cv_meta.get("status", "intercontrat" if available else "en_mission")
                points.append(PointStruct(
                    id=idx,
                    vector=embedding.tolist(),
                    payload={
                        "cv_id":            cv_id,
                        "name":             cv_meta.get("name", name_from_filename(cv_path.name)),
                        "title":            cv_meta.get("title", ""),
                        "available":        available,
                        "status":           status,
                        "availability_date": cv_meta.get("availability_date"),
                        "location":         cv_meta.get("location"),
                        "remote":           cv_meta.get("remote", "partial"),
                        "languages":        cv_meta.get("languages", ["fr"]),
                        "domains":          cv_meta.get("domains", []),
                        "email":            cv_meta.get("email"),
                        "text":             text,
                        "filename":         cv_path.name,
                    },
                ))
                idx += 1
            except Exception as e:
                logger.error("Failed to process %s: %s", cv_path.name, e)

        if points:
            self.qdrant.upsert(collection_name=_COLLECTION, points=points)

        self._cv_count = len(points)
        logger.info("Indexed %d CVs into Qdrant (%s).", self._cv_count, _COLLECTION)

    def rank_by_similarity(self, query_text: str) -> list[dict]:
        if self.qdrant is None or self.model is None:
            return []

        query_emb = self.model.encode(query_text[:_MAX_CHARS]).tolist()
        hits = self.qdrant.search(
            collection_name=_COLLECTION,
            query_vector=query_emb,
            limit=50,
            with_payload=True,
        )

        return [{**hit.payload, "score": hit.score} for hit in hits]

    @property
    def cv_count(self) -> int:
        return self._cv_count

    @property
    def is_ready(self) -> bool:
        return self.model is not None and self.qdrant is not None


embedding_service = EmbeddingService()
