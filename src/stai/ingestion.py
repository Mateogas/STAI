"""Verified immutable handbook-page ingestion and atomic activation."""

from __future__ import annotations

import hashlib
import json

from langchain_core.documents import Document

from stai.config import settings
from stai.handbook import HandbookArtifacts
from stai.retriever import load_page_records
from stai.state import Repo

class RetrievalBuildVerificationError(RuntimeError):
    pass


def stage_handbook_build(
    repo: Repo,
    artifacts: HandbookArtifacts,
    *,
    vector_builder,
    build_salt: str = "",
) -> dict:
    """Verify immutable page artifacts and atomically activate a new build."""
    manifest = json.loads(artifacts.manifest_path.read_text(encoding="utf-8"))
    records = load_page_records(artifacts.rag_pages_path, expected_manifest=manifest)
    identity_input = f"{manifest['manifest_sha256']}:{settings.embed_model}:{build_salt}".encode()
    build_id = hashlib.sha256(identity_input).hexdigest()[:24]
    collection = f"aisha_v{manifest['handbook_version'].replace('.', '_')}_{build_id[:12]}"
    result = vector_builder(collection, records)
    if result.get("count") != len(records) or not isinstance(result.get("dimension"), int) or result["dimension"] <= 0:
        raise RetrievalBuildVerificationError("staged vector build count or dimension mismatch")
    repo.register_retrieval_build(
        build_id,
        manifest["handbook_version"],
        manifest["manifest_sha256"],
        collection,
        verified=True,
    )
    repo.activate_retrieval_build(build_id)
    return {
        "build_id": build_id,
        "collection_name": collection,
        "record_count": len(records),
        "manifest_identity": manifest["manifest_sha256"],
        "embedding_model": settings.embed_model,
        "dimension": result["dimension"],
    }


def ingest_handbook(repo: Repo | None = None, artifacts: HandbookArtifacts | None = None) -> dict:
    """Build a hash-named Chroma collection; never reset the active collection in place."""
    from stai.handbook import build_handbook

    target_repo = repo or Repo()
    target_artifacts = artifacts or build_handbook()

    def build_vector(collection_name, records):
        from langchain_chroma import Chroma
        from langchain_ollama import OllamaEmbeddings

        store = Chroma(
            collection_name=collection_name,
            embedding_function=OllamaEmbeddings(model=settings.embed_model, base_url=settings.ollama_base_url),
            persist_directory=str(settings.chroma_dir),
        )
        documents = [
            Document(
                page_content=record.content,
                metadata={
                    "record_id": record.record_id,
                    "policy_id": record.policy_id or "",
                    "handbook_version": record.handbook_version,
                    "page": record.page,
                    "page_kind": record.page_kind,
                    "page_content_sha256": record.page_content_sha256,
                },
            )
            for record in records
        ]
        store.add_documents(documents, ids=[record.record_id for record in records])
        dimension = len(store._collection.peek(1).get("embeddings", [[0]])[0])
        return {"count": store._collection.count(), "dimension": dimension}

    return stage_handbook_build(target_repo, target_artifacts, vector_builder=build_vector)


def main() -> None:
    result = ingest_handbook()
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
