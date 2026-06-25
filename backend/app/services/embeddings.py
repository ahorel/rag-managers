import json
import logging
import re
from pathlib import Path

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

from app.config import settings
from app.services.cv_parser import SUPPORTED_EXTENSIONS, extract_text, name_from_filename

logger = logging.getLogger(__name__)

_META_FILE   = Path(settings.cv_directory).parent / "consultants_meta.json"


def _extract_years_from_text(text: str) -> int | None:
    """Extrait le nombre total d'années d'expérience depuis le texte brut du CV."""
    patterns = [
        r"(\d+)\s*ans?\s+d['’]exp[eé]rience",  # "15 ans d'expérience"
        r"exp[eé]rience\s+de\s+(\d+)\s*ans?",        # "expérience de 15 ans"
        r"(\d+)\s*years?\s+of\s+experience",           # "15 years of experience"
    ]
    for pat in patterns:
        m = re.search(pat, text[:3000], re.IGNORECASE)
        if m:
            val = int(m.group(1))
            if 1 <= val <= 50:
                return val
    return None


_MODEL_NAME      = "paraphrase-multilingual-MiniLM-L12-v2"
_MAX_CHARS       = 6000   # limite pour l'embedding de requête
_MIN_CHUNK_CHARS = 300    # taille minimum avant fusion avec le chunk suivant
_MAX_CHUNK_CHARS = 2000   # ~512 tokens — taille maximum d'un chunk de CV
_CHUNK_OVERLAP   = 200    # overlap utilisé uniquement si un bloc dépasse _MAX_CHUNK_CHARS
_VECTOR_SIZE     = 384
_COLLECTION      = "matchconsult_cvs"


def _make_semantic_chunks(text: str) -> list[str]:
    """Découpe le CV sur les frontières naturelles (sections / paragraphes).

    Stratégie :
    1. Split sur les sauts de paragraphe (≥2 newlines).
    2. Regroupe les blocs courts jusqu'à _MAX_CHUNK_CHARS.
    3. Si un bloc unique dépasse _MAX_CHUNK_CHARS, découpe en fixe avec overlap.
    4. Fusionne les chunks résiduels trop courts avec leur voisin.
    """
    raw_blocks = [b.strip() for b in re.split(r"\n{2,}", text) if b.strip()]

    chunks: list[str] = []
    current = ""

    for block in raw_blocks:
        if len(block) > _MAX_CHUNK_CHARS:
            # Bloc géant : on flush le courant et on découpe en fixe
            if current:
                chunks.append(current.strip())
                current = ""
            start = 0
            while start < len(block):
                end = min(start + _MAX_CHUNK_CHARS, len(block))
                chunks.append(block[start:end])
                if end == len(block):
                    break
                start = end - _CHUNK_OVERLAP
            continue

        candidate = (current + "\n\n" + block).strip() if current else block
        if len(candidate) > _MAX_CHUNK_CHARS:
            chunks.append(current.strip())
            current = block
        else:
            current = candidate

    if current:
        chunks.append(current.strip())

    # Fusionne les chunks trop courts avec le suivant
    merged: list[str] = []
    i = 0
    while i < len(chunks):
        if len(chunks[i]) < _MIN_CHUNK_CHARS and i + 1 < len(chunks):
            combined = chunks[i] + "\n\n" + chunks[i + 1]
            if len(combined) <= _MAX_CHUNK_CHARS:
                chunks[i + 1] = combined
                i += 1
                continue
        merged.append(chunks[i])
        i += 1

    return merged if merged else [text[:_MAX_CHUNK_CHARS]]


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

        # Suppression + recréation tolérante aux race conditions (2 workers uvicorn)
        try:
            self.qdrant.delete_collection(_COLLECTION)
        except Exception:
            pass
        try:
            self.qdrant.create_collection(
                collection_name=_COLLECTION,
                vectors_config=VectorParams(size=_VECTOR_SIZE, distance=Distance.COSINE),
            )
        except Exception:
            # Un autre worker a déjà recréé la collection — on continue
            logger.warning("Collection déjà créée par un autre worker, on continue.")

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
                cv_meta   = meta.get(cv_id, {})
                available = cv_meta.get("available", True)
                status    = cv_meta.get("status", "intercontrat" if available else "en_mission")
                years_exp = _extract_years_from_text(text)
                payload_base = {
                    "cv_id":             cv_id,
                    "name":              cv_meta.get("name", name_from_filename(cv_path.name)),
                    "title":             cv_meta.get("title", ""),
                    "available":         available,
                    "status":            status,
                    "availability_date": cv_meta.get("availability_date"),
                    "location":          cv_meta.get("location"),
                    "remote":            cv_meta.get("remote", "partial"),
                    "languages":         cv_meta.get("languages", ["fr"]),
                    "domains":           cv_meta.get("domains", []),
                    "email":             cv_meta.get("email"),
                    "years_experience":  years_exp,
                    "text":              text,   # texte complet pour keyword matching
                    "filename":          cv_path.name,
                }
                chunks = _make_semantic_chunks(text)
                logger.debug("[embeddings] %s → %d chunk(s)", cv_id, len(chunks))
                for chunk in chunks:
                    embedding = self.model.encode(chunk)
                    points.append(PointStruct(
                        id=idx,
                        vector=embedding.tolist(),
                        payload=payload_base,
                    ))
                    idx += 1
            except Exception as e:
                logger.error("Failed to process %s: %s", cv_path.name, e)

        if points:
            self.qdrant.upsert(collection_name=_COLLECTION, points=points)

        # Compte les CVs uniques (pas les chunks)
        unique_cvs = len({p.payload["cv_id"] for p in points})
        self._cv_count = unique_cvs
        logger.info(
            "Indexed %d CVs → %d chunks into Qdrant (%s).",
            unique_cvs, len(points), _COLLECTION,
        )

    def rank_by_similarity(self, query_text: str, qdrant_filter=None) -> list[dict]:
        if self.qdrant is None or self.model is None:
            return []

        query_emb = self.model.encode(query_text[:_MAX_CHARS]).tolist()
        hits = self.qdrant.search(
            collection_name=_COLLECTION,
            query_vector=query_emb,
            limit=200,   # large pool car N chunks par CV
            with_payload=True,
            query_filter=qdrant_filter,
        )

        # Max-pool : on garde le meilleur chunk par CV (score cosinus le plus élevé)
        best: dict[str, dict] = {}
        for hit in hits:
            cv_id = hit.payload["cv_id"]
            if cv_id not in best or hit.score > best[cv_id]["score"]:
                best[cv_id] = {**hit.payload, "score": hit.score}

        return sorted(best.values(), key=lambda x: x["score"], reverse=True)[:50]

    @property
    def cv_count(self) -> int:
        return self._cv_count

    @property
    def is_ready(self) -> bool:
        return self.model is not None and self.qdrant is not None


embedding_service = EmbeddingService()
