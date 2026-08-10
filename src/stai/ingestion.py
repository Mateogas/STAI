"""Knowledge-base ingestion: data/hr_docs/*.md -> chunk -> embed -> Chroma.

Run with:  python -m stai.ingestion
Idempotent: the collection is reset and rebuilt on every run, so editing a
handbook doc and re-running is always safe.
"""

from __future__ import annotations

import re
import hashlib
import json
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from stai.config import settings
from stai.handbook import HandbookArtifacts
from stai.retriever import load_page_records
from stai.state import Repo

_FRONT_MATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    """Split a markdown file into (front-matter dict, body).

    Front matter is a simple ``key: value`` block between ``---`` fences; we
    deliberately avoid a YAML dependency for three flat string fields.
    """
    match = _FRONT_MATTER.match(text)
    if not match:
        return {}, text
    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    return meta, text[match.end():]


def load_documents(hr_docs_dir: Path | None = None) -> list[Document]:
    docs_dir = Path(hr_docs_dir or settings.hr_docs_dir)
    documents = []
    for path in sorted(docs_dir.glob("*.md")):
        meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
        documents.append(
            Document(
                page_content=body.strip(),
                metadata={
                    "source": path.name,
                    "title": meta.get("title", path.stem),
                    "doc_type": meta.get("doc_type", "guide"),
                    "department": meta.get("department", "all"),
                },
            )
        )
    return documents


def split_documents(
    documents: list[Document],
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size or settings.chunk_size,
        chunk_overlap=chunk_overlap if chunk_overlap is not None else settings.chunk_overlap,
    )
    return splitter.split_documents(documents)


def ingest() -> tuple[int, int]:
    """Rebuild the Chroma collection from the hr_docs folder.

    Imports are local so that pure-logic callers (and tests) of this module
    never need the embedding stack.
    """
    from langchain_chroma import Chroma
    from langchain_ollama import OllamaEmbeddings

    documents = load_documents()
    if not documents:
        raise FileNotFoundError(f"No .md docs found in {settings.hr_docs_dir}")
    chunks = split_documents(documents)

    store = Chroma(
        collection_name=settings.collection_name,
        embedding_function=OllamaEmbeddings(
            model=settings.embed_model, base_url=settings.ollama_base_url
        ),
        persist_directory=str(settings.chroma_dir),
    )
    store.reset_collection()
    store.add_documents(chunks)
    return len(documents), len(chunks)


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
    n_docs, n_chunks = ingest()
    print(
        f"Ingested {n_docs} docs -> {n_chunks} chunks into collection "
        f"'{settings.collection_name}' at {settings.chroma_dir}"
    )


if __name__ == "__main__":
    main()
