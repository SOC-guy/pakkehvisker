import atexit
from collections.abc import Iterable, Iterator
from hashlib import sha256
from typing import Any

from lpw_init import getLpwPath, log_message

MAX_CHUNK_CHARS = 2400
EMBED_BATCH_SIZE = 32
_cleanup_registered = False


def chunk_packets(
    packet_texts: Iterable[str],
    max_chars: int = MAX_CHUNK_CHARS,
) -> Iterator[tuple[str, int, int]]:
    buffer: list[str] = []
    buffer_length = 0
    first_packet = 1
    last_packet = 0

    def emit() -> tuple[str, int, int]:
        return "\n\n".join(buffer), first_packet, last_packet

    for packet_number, packet_text in enumerate(packet_texts, start=1):
        packet_text = packet_text.strip()
        if not packet_text:
            continue

        segments = [
            packet_text[offset : offset + max_chars]
            for offset in range(0, len(packet_text), max_chars)
        ]
        for segment in segments:
            separator_length = 2 if buffer else 0
            if buffer and buffer_length + separator_length + len(segment) > max_chars:
                yield emit()
                buffer.clear()
                buffer_length = 0

            if not buffer:
                first_packet = packet_number
            buffer.append(segment)
            buffer_length += (2 if len(buffer) > 1 else 0) + len(segment)
            last_packet = packet_number

    if buffer:
        yield emit()


def _collection_name(capture_bytes: bytes, display_filter: str, embedding_model: str) -> str:
    digest = sha256()
    digest.update(capture_bytes)
    digest.update(display_filter.encode("utf-8"))
    digest.update(embedding_model.encode("utf-8"))
    return f"pcap_{digest.hexdigest()[:32]}"


def _get_database() -> Any:
    import chromadb

    return chromadb.PersistentClient(path=getLpwPath("index"))


def cleanup_rag_database() -> None:
    database = _get_database()
    collections = database.list_collections()
    for collection in collections:
        collection_name = getattr(collection, "name", collection)
        database.delete_collection(name=collection_name)
    log_message(f"Cleaned up RAG database ({len(collections)} collections)")


def register_rag_cleanup() -> None:
    global _cleanup_registered
    if _cleanup_registered:
        return

    cleanup_rag_database()
    atexit.register(cleanup_rag_database)
    _cleanup_registered = True


def index_capture(
    packet_texts: Iterable[str],
    capture_bytes: bytes,
    display_filter: str,
    embedding_model: str,
    ollama_client: Any,
) -> dict[str, int | str]:
    database = _get_database()
    collection_name = _collection_name(capture_bytes, display_filter, embedding_model)
    collection = database.get_or_create_collection(
        name=collection_name,
        metadata={
            "hnsw:space": "cosine",
            "embedding_model": embedding_model,
            "status": "building",
        },
    )

    metadata = collection.metadata or {}
    if metadata.get("status") == "ready":
        return {
            "capture_id": collection_name,
            "packet_count": int(metadata.get("packet_count", 0)),
            "chunk_count": int(metadata.get("chunk_count", collection.count())),
            "decoded_chars": int(metadata.get("decoded_chars", 0)),
        }

    if collection.count():
        database.delete_collection(name=collection_name)
        collection = database.create_collection(
            name=collection_name,
            metadata={
                "hnsw:space": "cosine",
                "embedding_model": embedding_model,
                "status": "building",
            },
        )

    packet_count = 0
    chunk_count = 0
    decoded_chars = 0
    batch_documents: list[str] = []
    batch_metadatas: list[dict[str, int]] = []

    def track_packets() -> Iterator[str]:
        nonlocal packet_count, decoded_chars
        for packet_text in packet_texts:
            packet_count += 1
            decoded_chars += len(packet_text)
            yield packet_text

    def flush_batch() -> None:
        nonlocal chunk_count
        if not batch_documents:
            return
        response = ollama_client.embed(model=embedding_model, input=batch_documents)
        embeddings = response.embeddings
        first_id = chunk_count - len(batch_documents)
        collection.add(
            ids=[f"chunk_{first_id + offset}" for offset in range(len(batch_documents))],
            documents=batch_documents,
            embeddings=embeddings,
            metadatas=batch_metadatas,
        )
        batch_documents.clear()
        batch_metadatas.clear()

    try:
        # Chunks are emitted incrementally so large captures stay bounded in memory.
        for document, packet_start, packet_end in chunk_packets(track_packets()):
            batch_documents.append(document)
            batch_metadatas.append(
                {"packet_start": packet_start, "packet_end": packet_end}
            )
            chunk_count += 1
            if len(batch_documents) >= EMBED_BATCH_SIZE:
                flush_batch()

        if packet_count == 0:
            raise ValueError("No packets matched the selected display filter.")

        flush_batch()
        collection.modify(
            metadata={
                "embedding_model": embedding_model,
                "status": "ready",
                "packet_count": packet_count,
                "chunk_count": chunk_count,
                "decoded_chars": decoded_chars,
            }
        )
    except Exception:
        database.delete_collection(name=collection_name)
        raise

    log_message(
        f"Indexed capture {collection_name}: {packet_count} packets, "
        f"{chunk_count} chunks using {embedding_model}"
    )
    return {
        "capture_id": collection_name,
        "packet_count": packet_count,
        "chunk_count": chunk_count,
        "decoded_chars": decoded_chars,
    }


def search_capture(
    capture_id: str,
    query: str,
    embedding_model: str,
    ollama_client: Any,
    top_k: int | None = None,
) -> list[dict[str, Any]]:
    collection = _get_database().get_collection(name=capture_id)
    result_count = collection.count() if top_k is None else min(top_k, collection.count())
    if result_count == 0:
        return []

    response = ollama_client.embed(model=embedding_model, input=query)
    results = collection.query(
        query_embeddings=[response.embeddings[0]],
        n_results=result_count,
        include=["documents", "metadatas", "distances"],
    )
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]
    return [
        {"text": document, **metadata, "distance": distance}
        for document, metadata, distance in zip(documents, metadatas, distances)
    ]


def format_context(results: list[dict[str, Any]]) -> str:
    return "\n\n".join(
        f"[Packets {result['packet_start']}-{result['packet_end']}]\n{result['text']}"
        for result in results
    )