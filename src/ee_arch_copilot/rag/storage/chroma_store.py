import hashlib
import json
import sqlite3
from pathlib import Path
from threading import RLock
from typing import Literal, cast

import chromadb
from chromadb.api.types import Embeddings, Metadata, Where
from chromadb.config import Settings as ChromaSettings

from ee_arch_copilot.rag.embeddings.base import validate_vectors
from ee_arch_copilot.rag.errors import ConfigurationError
from ee_arch_copilot.rag.models import (
    Chunk,
    Document,
    DocumentSummary,
    SearchFilter,
)


class ChromaStore:
    """Single-process store. Catalog commits activate fully written Chroma revisions.

    New vectors are staged before the catalog transaction. Queries restrict Chroma
    to active revision fingerprints; failed staging cannot expose partial documents.
    Old vectors are pruned after commit. Catalog chunks are authoritative citations.
    """

    def __init__(self, path: Path, embedding_identity: str, dimension: int) -> None:
        path.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()
        self.dimension = dimension
        self.embedding_identity = embedding_identity
        self.client = chromadb.PersistentClient(
            path=str(path / "chroma"), settings=ChromaSettings(anonymized_telemetry=False)
        )
        self.collection = self.client.get_or_create_collection(
            "requirements",
            embedding_function=None,
            metadata={
                "embedding_identity": embedding_identity,
                "dimension": dimension,
                "schema_version": "1",
            },
            configuration={"hnsw": {"space": "cosine"}},
        )
        meta = self.collection.metadata or {}
        if (
            meta.get("embedding_identity") != embedding_identity
            or meta.get("dimension") != dimension
            or meta.get("schema_version") != "1"
        ):
            raise ConfigurationError(
                "Index model/dimension/schema mismatch; use a new VECTOR_DB_PATH and reindex"
            )
        self._db = sqlite3.connect(path / "catalog.sqlite3", check_same_thread=False)
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY, payload TEXT NOT NULL, revision TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id)
                ON DELETE CASCADE, payload TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS chunk_document ON chunks(document_id);
        """)

    def revision_for(self, document: Document, chunks: list[Chunk]) -> str:
        payload = [
            document.model_dump(mode="json", exclude={"ingestion_timestamp"}),
            [chunk.model_dump(mode="json") for chunk in chunks],
            self.embedding_identity,
        ]
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    def is_current(self, document_id: str, revision: str) -> bool:
        with self.lock:
            row = self._db.execute(
                "SELECT revision FROM documents WHERE id=?", (document_id,)
            ).fetchone()
            return row is not None and row[0] == revision

    def replace(
        self,
        document: Document,
        chunks: list[Chunk],
        vectors: list[list[float]],
        revision: str,
    ) -> Literal["created", "replaced"]:
        validate_vectors(vectors, len(chunks), self.dimension)
        if not chunks:
            raise ValueError("Document must have indexable chunks")
        with self.lock:
            old_ids = [
                chunk.chunk_id
                for chunk in self.chunks(SearchFilter(document_id=document.document_id))
            ]
            existed = self.get_document(document.document_id) is not None
            # Vector IDs include revision: metadata-only updates cannot overwrite active staging.
            for offset in range(0, len(chunks), 128):
                batch = chunks[offset : offset + 128]
                metadata: list[Metadata] = [
                    {
                        "document_id": chunk.document_id,
                        "requirement_id": chunk.requirement_id or "",
                        "version": chunk.document_version or "",
                        "revision": revision,
                        "chunk_id": chunk.chunk_id,
                        "filename": chunk.filename,
                    }
                    for chunk in batch
                ]
                self.collection.upsert(
                    ids=[f"{revision}:{chunk.chunk_id}" for chunk in batch],
                    embeddings=cast(Embeddings, vectors[offset : offset + 128]),
                    documents=[chunk.text for chunk in batch],
                    metadatas=metadata,
                )
            previous = self._db.execute(
                "SELECT revision FROM documents WHERE id=?", (document.document_id,)
            ).fetchone()
            with self._db:
                self._db.execute(
                    "INSERT OR REPLACE INTO documents VALUES (?, ?, ?)",
                    (document.document_id, document.model_dump_json(), revision),
                )
                self._db.execute("DELETE FROM chunks WHERE document_id=?", (document.document_id,))
                self._db.executemany(
                    "INSERT INTO chunks VALUES (?, ?, ?)",
                    [
                        (chunk.chunk_id, document.document_id, chunk.model_dump_json())
                        for chunk in chunks
                    ],
                )
            if previous and previous[0] != revision and old_ids:
                self.collection.delete(
                    ids=[f"{previous[0]}:{identifier}" for identifier in old_ids]
                )
            return "replaced" if existed else "created"

    def get_document(self, document_id: str) -> Document | None:
        with self.lock:
            row = self._db.execute(
                "SELECT payload FROM documents WHERE id=?", (document_id,)
            ).fetchone()
            return Document.model_validate_json(row[0]) if row else None

    def documents(self) -> list[DocumentSummary]:
        with self.lock:
            rows = self._db.execute(
                "SELECT d.payload, COUNT(c.id) FROM documents d LEFT JOIN chunks c "
                "ON c.document_id=d.id GROUP BY d.id ORDER BY d.id"
            ).fetchall()
            return [
                DocumentSummary(
                    **Document.model_validate_json(payload).model_dump(exclude={"content"}),
                    chunk_count=count,
                )
                for payload, count in rows
            ]

    def chunks(self, filters: SearchFilter | None = None) -> list[Chunk]:
        filters = filters or SearchFilter()
        with self.lock:
            rows = self._db.execute("SELECT payload FROM chunks ORDER BY id").fetchall()
            chunks = [Chunk.model_validate_json(row[0]) for row in rows]
            return [
                chunk
                for chunk in chunks
                if (filters.document_id is None or chunk.document_id == filters.document_id)
                and (
                    filters.requirement_id is None or chunk.requirement_id == filters.requirement_id
                )
                and (filters.version is None or chunk.document_version == filters.version)
            ]

    def get_chunk(self, chunk_id: str) -> Chunk | None:
        with self.lock:
            row = self._db.execute("SELECT payload FROM chunks WHERE id=?", (chunk_id,)).fetchone()
            return Chunk.model_validate_json(row[0]) if row else None

    def search(
        self,
        vector: list[float],
        top_k: int,
        filters: SearchFilter,
        min_similarity: float,
    ) -> list[tuple[Chunk, float]]:
        validate_vectors([vector], 1, self.dimension)
        with self.lock:
            candidates = {chunk.chunk_id: chunk for chunk in self.chunks(filters)}
            if not candidates:
                return []
            revisions = [
                row[0] for row in self._db.execute("SELECT revision FROM documents").fetchall()
            ]
            clauses: list[Where] = [cast(Where, {"revision": {"$in": revisions}})]
            for key, value in filters.model_dump(exclude_none=True).items():
                clauses.append(cast(Where, {key: {"$eq": value}}))
            where: Where = {"$and": clauses} if len(clauses) > 1 else clauses[0]
            result = self.collection.query(
                query_embeddings=cast(Embeddings, [vector]),
                n_results=min(top_k, len(candidates)),
                where=where,
                include=["metadatas", "distances"],
            )
            distances = (result["distances"] or [[]])[0]
            metadata = (result["metadatas"] or [[]])[0]
            hits = []
            for item, distance in zip(metadata, distances, strict=True):
                chunk = candidates.get(str(item["chunk_id"]))
                similarity = max(-1.0, min(1.0, 1 - distance))
                if chunk is not None and similarity >= min_similarity:
                    hits.append((chunk, similarity))
            return sorted(hits, key=lambda hit: (-hit[1], hit[0].chunk_id))

    def delete(self, document_id: str) -> bool:
        with self.lock:
            if self.get_document(document_id) is None:
                return False
            # Delete vectors first so a failure leaves the authoritative catalog intact.
            self.collection.delete(where={"document_id": document_id})
            with self._db:
                self._db.execute("DELETE FROM documents WHERE id=?", (document_id,))
            return True
