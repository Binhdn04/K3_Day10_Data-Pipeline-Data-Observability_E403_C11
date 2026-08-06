from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb
import pandas as pd
from chromadb.errors import NotFoundError

from core.config import Settings
from core.utils import read_json, safe_slug, write_json
from retrieval.embeddings import MiniLMEmbeddings


@dataclass(frozen=True)
class SearchResult:
    paper_id: str
    title: str
    score: float
    content: str
    metadata: dict[str, Any]


class LocalEmbeddingIndex:
    REQUIRED_COLUMNS = {
        "paper_id",
        "title",
        "summary",
        "published",
        "authors_joined",
        "categories_joined",
        "text_for_embedding",
    }

    def __init__(
        self,
        settings: Settings,
        collection_name: str,
        documents: list[dict[str, Any]],
        persist_path: Path,
    ):
        self.settings = settings
        self.collection_name = collection_name
        self.documents = documents
        self.persist_path = persist_path
        self.embedding_backend = "chroma"
        self.embedding_model = MiniLMEmbeddings(settings.embedding_model)
        self.client = chromadb.PersistentClient(path=str(persist_path))
        try:
            self.collection = self.client.get_collection(name=collection_name)
        except NotFoundError as exc:
            raise FileNotFoundError(
                f"Chroma collection '{collection_name}' was not found at {persist_path}. "
                "Rebuild the index from the corresponding clean dataset."
            ) from exc
        self.documents_by_paper_id = {
            str(document["paper_id"]).strip().casefold(): document for document in documents
        }
        self.documents_by_title = {
            str(document["title"]).strip().casefold(): document for document in documents
        }

    @staticmethod
    def _metadata_text(value: Any) -> str:
        if value is None or pd.isna(value):
            return ""
        return str(value).strip()

    @classmethod
    def _validate_dataframe(cls, df: pd.DataFrame) -> None:
        missing = sorted(cls.REQUIRED_COLUMNS.difference(df.columns))
        if missing:
            raise ValueError(f"Clean dataframe is missing required columns: {', '.join(missing)}")
        if df.empty:
            raise ValueError("Cannot build an embedding index from an empty dataframe.")

        invalid_fields: list[str] = []
        for field in ("paper_id", "title", "text_for_embedding"):
            values = df[field]
            invalid = values.isna() | values.astype(str).str.strip().eq("")
            if invalid.any():
                invalid_fields.append(f"{field} ({int(invalid.sum())} row(s))")
        if invalid_fields:
            raise ValueError("Clean dataframe contains blank index fields: " + ", ".join(invalid_fields))

    @classmethod
    def _build_documents(cls, df: pd.DataFrame) -> list[dict[str, Any]]:
        cls._validate_dataframe(df)
        records = df.to_dict(orient="records")
        documents: list[dict[str, Any]] = []
        for index, row in enumerate(records):
            paper_id = cls._metadata_text(row["paper_id"])
            title = cls._metadata_text(row["title"])
            documents.append(
                {
                    "record_id": f"{paper_id}::{index}",
                    "paper_id": paper_id,
                    "title": title,
                    "content": cls._metadata_text(row["text_for_embedding"]),
                    "metadata": {
                        "paper_id": paper_id,
                        "title": title,
                        "published": cls._metadata_text(row["published"]),
                        "authors_joined": cls._metadata_text(row["authors_joined"]),
                        "categories_joined": cls._metadata_text(row["categories_joined"]),
                        "summary": cls._metadata_text(row["summary"]),
                        "abs_url": cls._metadata_text(row.get("abs_url")),
                        "pdf_url": cls._metadata_text(row.get("pdf_url")),
                    },
                }
            )
        return documents

    @staticmethod
    def _derive_collection_name(settings: Settings, embeddings_output_path: Path | None) -> str:
        if embeddings_output_path is None:
            return settings.baseline_collection_name

        name_map = {
            settings.paths.embeddings_json.resolve(): settings.baseline_collection_name,
            settings.paths.corrupted_embeddings_json.resolve(): settings.corrupted_collection_name,
            settings.paths.repaired_embeddings_json.resolve(): settings.repaired_collection_name,
        }
        resolved_path = embeddings_output_path.resolve()
        if resolved_path in name_map:
            return name_map[resolved_path]
        return safe_slug(embeddings_output_path.stem)

    @classmethod
    def build(
        cls,
        df: pd.DataFrame,
        settings: Settings,
        embeddings_output_path: Path | None = None,
    ) -> "LocalEmbeddingIndex":
        collection_name = cls._derive_collection_name(settings, embeddings_output_path)
        documents = cls._build_documents(df)
        persist_path = settings.paths.chroma_dir
        persist_path.mkdir(parents=True, exist_ok=True)

        embedding_model = MiniLMEmbeddings(settings.embedding_model)
        client = chromadb.PersistentClient(path=str(persist_path))
        try:
            client.delete_collection(name=collection_name)
        except NotFoundError:
            pass
        collection = client.create_collection(
            name=collection_name,
            configuration={"hnsw": {"space": "cosine"}},
        )
        embeddings = embedding_model.embed_documents([document["content"] for document in documents])
        collection.add(
            ids=[document["record_id"] for document in documents],
            embeddings=embeddings,
            documents=[document["content"] for document in documents],
            metadatas=[document["metadata"] for document in documents],
        )

        manifest_path = embeddings_output_path or settings.paths.embeddings_json
        write_json(
            manifest_path,
            {
                "manifest_version": 1,
                "backend": "chroma",
                "embedding_model": settings.embedding_model,
                "persist_path": str(persist_path.resolve()),
                "collection_name": collection_name,
                "document_count": len(documents),
                "documents": documents,
            },
        )
        return cls(
            settings=settings,
            collection_name=collection_name,
            documents=documents,
            persist_path=persist_path,
        )

    @classmethod
    def load(cls, settings: Settings, embeddings_path: Path | None = None) -> "LocalEmbeddingIndex":
        manifest_path = embeddings_path or settings.paths.embeddings_json
        payload = read_json(manifest_path)
        required_keys = {"collection_name", "documents", "persist_path"}
        missing = sorted(required_keys.difference(payload))
        if missing:
            raise ValueError(f"Embedding manifest is missing keys: {', '.join(missing)}")
        persist_path = Path(payload["persist_path"])
        if not persist_path.is_absolute():
            persist_path = settings.paths.project_dir / persist_path
        return cls(
            settings=settings,
            collection_name=payload["collection_name"],
            documents=payload["documents"],
            persist_path=persist_path,
        )

    def search(self, query: str, top_k: int | None = None) -> list[SearchResult]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Search query must not be blank.")
        requested = self.settings.top_k if top_k is None else top_k
        if not isinstance(requested, int) or isinstance(requested, bool) or requested < 1:
            raise ValueError("top_k must be a positive integer.")
        collection_size = self.collection.count()
        if collection_size == 0:
            return []

        query_embedding = self.embedding_model.embed_query(query)
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(requested, collection_size),
            include=["documents", "metadatas", "distances"],
        )
        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        scored: list[SearchResult] = []
        for record_id, content, metadata, distance in zip(ids, documents, metadatas, distances, strict=False):
            if not record_id or not metadata or not content:
                continue
            scored.append(
                SearchResult(
                    paper_id=str(metadata["paper_id"]),
                    title=str(metadata["title"]),
                    score=max(0.0, 1.0 - float(distance or 0.0)),
                    content=str(content),
                    metadata=dict(metadata),
                )
            )
        return scored

    def lookup(self, value: str) -> dict[str, Any] | None:
        if not isinstance(value, str) or not value.strip():
            return None
        needle = value.strip().casefold()
        if needle in self.documents_by_paper_id:
            return self.documents_by_paper_id[needle]
        if needle in self.documents_by_title:
            return self.documents_by_title[needle]
        return None
