"""
Benchmark hybrid search performance
"""
import time
import statistics
import sys
import os
from uuid import uuid4
import math
import traceback

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.retrieval_service import get_retrieval_service
from app.services.qdrant_service import QdrantService
from app.services.embedding_service import get_embedding_service

# Configurable
BATCH_SIZE = 100
SEARCH_WARMUP_RUNS = 5
SEARCH_RETRY = 3
COLLECTION_READY_TIMEOUT = 10.0  # seconds
COLLECTION_POLL_INTERVAL = 0.25  # initial poll interval


def wait_for_collection(qdrant_service: QdrantService, collection_name: str, timeout: float = COLLECTION_READY_TIMEOUT):
    """
    Poll qdrant_service.collection_exists until True or timeout.
    Returns True if exists, False if timed out.
    """
    start = time.perf_counter()
    interval = COLLECTION_POLL_INTERVAL
    while True:
        try:
            if qdrant_service.collection_exists(collection_name):
                return True
        except Exception:
            # swallow network/temporary errors and retry
            pass

        if time.perf_counter() - start > timeout:
            return False
        time.sleep(interval)
        # exponential backoff capped
        interval = min(interval * 1.5, 1.0)


def setup_benchmark_data(num_docs=1000, bot_id="benchmark_bot", organization_id="benchmark_org"):
    """Setup benchmark collection with sample data.

    Creates collection named using the same convention as retrieval service:
        bot_embeddings_{bot_id}
    """
    qdrant_service = QdrantService()
    embedding_service = get_embedding_service()

    # Use the same collection naming convention as the retrieval service
    collection_name = f"bot_embeddings_{bot_id}"

    # Delete if exists
    try:
        if qdrant_service.collection_exists(collection_name):
            qdrant_service.delete_collection(collection_name)
            print(f"Deleted existing collection: {collection_name}")
    except Exception as e:
        print(f"Note while deleting existing collection: {e}")

    # Create collection with text index
    qdrant_service.create_collection_with_text_index(
        collection_name=collection_name,
        vector_size=384
    )

    # Wait until collection is visible/ready
    ok = wait_for_collection(qdrant_service, collection_name, timeout=COLLECTION_READY_TIMEOUT)
    if not ok:
        print(f"Warning: collection {collection_name} not visible after creation. Continuing anyway (Qdrant may still be initializing).")

    print(f"Creating {num_docs} test documents...")

    # Generate test documents
    test_docs = []
    for i in range(num_docs):
        content = (
            f"Document {i}: This is a test document about topic {i % 10}. "
            f"It contains information about various subjects including "
            f"technology, science, and general knowledge. "
            f"Additional content for document {i} with keywords like "
            f"programming, data, analysis, and research."
        )
        test_docs.append({
            "content": content,
            "metadata": {
                "chunk_id": f"chunk_{i}",
                "doc_id": f"doc_{i}",
                "bot_id": bot_id,
                "organization_id": organization_id,
                "chunk_index": i,
                "source_id": f"source_{i % 100}",
                "source_type": "document",
                "topic": i % 10,
                "is_active": True
            }
        })

    # Batch insert
    total = len(test_docs)
    for start_idx in range(0, total, BATCH_SIZE):
        batch = test_docs[start_idx:start_idx + BATCH_SIZE]
        contents = [doc["content"] for doc in batch]

        # generate_embeddings expects a list of texts
        embeddings = embedding_service.generate_embeddings(contents)

        payloads = [{**doc["metadata"], "content": doc["content"]} for doc in batch]

        # Use UUIDs for Qdrant point IDs
        ids = [str(uuid4()) for _ in batch]

        qdrant_service.insert_vectors(
            collection_name=collection_name,
            vectors=embeddings,
            payloads=payloads,
            ids=ids
        )

        # Try flush if the service exposes such method (best-effort)
        try:
            qdrant_service.flush_collection(collection_name)
        except Exception:
            # not critical; continue — but the wait_for_collection below will help
            pass

        inserted = min(start_idx + BATCH_SIZE, total)
        if inserted % 500 == 0 or inserted == total:
            print(f"Inserted {inserted} documents...")

    # final wait to make collection searchable (best-effort)
    ok = wait_for_collection(qdrant_service, collection_name, timeout=COLLECTION_READY_TIMEOUT)
    if not ok:
        print(f"Final warning: collection {collection_name} may not be fully available yet.")

    print(f"Setup complete: {num_docs} documents indexed into {collection_name}")
    return collection_name


def _timed_search_with_retries(retrieval_service, search_fn, *args, **kwargs):
    """
    Call search_fn(*args, **kwargs) with retries on failure.
    Returns (latency_ms, results) on success, (None, None) on permanent failure.
    """
    for attempt in range(1, SEARCH_RETRY + 1):
        start = time.perf_counter()
        try:
            results = search_fn(*args, **kwargs)
            latency_ms = (time.perf_counter() - start) * 1000.0
            return latency_ms, results
        except Exception as e:
            # log and retry a few times
            print(f"Search attempt {attempt} failed: {e}")
            if attempt < SEARCH_RETRY:
                time.sleep(0.1 * attempt)
                continue
            else:
                # permanent failure
                print("Search permanently failed after retries. Skipping this query.")
                traceback.print_exc()
                return None, None


def benchmark_search(num_queries=50, bot_id="benchmark_bot", organization_id="benchmark_org"):
    """Benchmark search performance"""
    retrieval_service = get_retrieval_service()

    test_queries = [
        "technology and science",
        "general knowledge information",
        "test document topic",
        "various subjects including",
        "information about technology",
        "programming data analysis",
        "research and development",
        "document content keywords"
    ]

    # Warm up
    print("\nWarming up...")
    for _ in range(SEARCH_WARMUP_RUNS):
        latency, _ = _timed_search_with_retries(
            retrieval_service,
            retrieval_service.hybrid_search,
            query=test_queries[0],
            bot_id=bot_id,
            organization_id=organization_id,
            top_k=5
        )
        if latency is None:
            # If warmup fails repeatedly, continue — search body will handle failures later
            pass

    # Benchmark
    print(f"\nRunning {num_queries} queries...")
    latencies = []

    for i in range(num_queries):
        query = test_queries[i % len(test_queries)]

        latency, results = _timed_search_with_retries(
            retrieval_service,
            retrieval_service.hybrid_search,
            query=query,
            bot_id=bot_id,
            organization_id=organization_id,
            top_k=5
        )

        # Skip failed queries (do not append zero). This keeps stats correct.
        if latency is None:
            continue

        latencies.append(latency)

        if (i + 1) % 10 == 0:
            avg = statistics.mean(latencies) if latencies else float("nan")
            print(f"Completed {i + 1} queries... (avg of successful: {avg:.2f}ms)")

    # Statistics
    print("\n" + "=" * 60)
    print("BENCHMARK RESULTS")
    print("=" * 60)
    total_run = num_queries
    successful = len(latencies)
    print(f"Total queries requested: {total_run}")
    print(f"Successful queries: {successful}")

    if successful == 0:
        print("No successful queries were recorded. Check Qdrant connection / collection readiness.")
        return

    avg = statistics.mean(latencies)
    med = statistics.median(latencies)
    mn = min(latencies)
    mx = max(latencies)

    print(f"Average latency: {avg:.2f}ms")
    print(f"Median latency: {med:.2f}ms")
    print(f"Min latency: {mn:.2f}ms")
    print(f"Max latency: {mx:.2f}ms")

    # p95/p99 calculation (only if enough samples)
    def percentile(data, p):
        if not data:
            return None
        data_sorted = sorted(data)
        k = (len(data_sorted)-1) * (p/100.0)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return data_sorted[int(k)]
        d0 = data_sorted[int(f)] * (c - k)
        d1 = data_sorted[int(c)] * (k - f)
        return d0 + d1

    if successful >= 20:
        p95 = percentile(latencies, 95)
        print(f"P95 latency: {p95:.2f}ms")
    if successful >= 100:
        p99 = percentile(latencies, 99)
        print(f"P99 latency: {p99:.2f}ms")

    print("=" * 60)

    # Performance assessment
    if avg < 500:
        print("✅ EXCELLENT: Average latency < 500ms")
    elif avg < 1000:
        print("✅ GOOD: Average latency < 1s")
    elif avg < 2000:
        print("⚠️  ACCEPTABLE: Average latency < 2s")
    else:
        print("❌ NEEDS IMPROVEMENT: Average latency > 2s")


def benchmark_vector_only(num_queries=50, bot_id="benchmark_bot", organization_id="benchmark_org"):
    """Benchmark vector search only"""
    retrieval_service = get_retrieval_service()

    test_queries = [
        "technology and science",
        "general knowledge information",
        "test document topic"
    ]

    print("\n" + "=" * 60)
    print("VECTOR SEARCH ONLY BENCHMARK")
    print("=" * 60)

    latencies = []

    for i in range(num_queries):
        query = test_queries[i % len(test_queries)]

        latency, results = _timed_search_with_retries(
            retrieval_service,
            retrieval_service._vector_search,
            query=query,
            bot_id=bot_id,
            filters={"organization_id": organization_id, "bot_id": bot_id, "is_active": True},
            top_k=5
        )

        if latency is None:
            continue
        latencies.append(latency)

    if latencies:
        print(f"Vector search average: {statistics.mean(latencies):.2f}ms")
        print(f"Vector search median: {statistics.median(latencies):.2f}ms")
    else:
        print("No successful vector search results recorded.")


def benchmark_bm25_only(num_queries=50, bot_id="benchmark_bot", organization_id="benchmark_org"):
    """Benchmark BM25 search only"""
    retrieval_service = get_retrieval_service()

    test_queries = [
        "technology and science",
        "general knowledge information",
        "test document topic"
    ]

    print("\n" + "=" * 60)
    print("BM25 SEARCH ONLY BENCHMARK")
    print("=" * 60)

    latencies = []

    for i in range(num_queries):
        query = test_queries[i % len(test_queries)]

        latency, results = _timed_search_with_retries(
            retrieval_service,
            retrieval_service._bm25_search,
            query=query,
            bot_id=bot_id,
            filters={"organization_id": organization_id, "bot_id": bot_id, "is_active": True},
            top_k=5
        )

        if latency is None:
            continue
        latencies.append(latency)

    if latencies:
        print(f"BM25 search average: {statistics.mean(latencies):.2f}ms")
        print(f"BM25 search median: {statistics.median(latencies):.2f}ms")
    else:
        print("No successful BM25 search results recorded.")


def cleanup(bot_id="benchmark_bot"):
    """Cleanup benchmark data"""
    qdrant_service = QdrantService()
    collection_name = f"bot_embeddings_{bot_id}"
    try:
        qdrant_service.delete_collection(collection_name)
        print(f"\n✅ Cleanup complete: {collection_name} deleted")
    except Exception as e:
        print(f"\nCleanup note: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("HYBRID SEARCH PERFORMANCE BENCHMARK")
    print("=" * 60)

    # Parameters: change these if you want different bot/org names
    BOT_ID = "benchmark_bot"
    ORG_ID = "benchmark_org"
    NUM_DOCS = 1000
    NUM_QUERIES = 50

    try:
        # Setup
        setup_benchmark_data(num_docs=NUM_DOCS, bot_id=BOT_ID, organization_id=ORG_ID)

        # Run benchmarks
        benchmark_search(num_queries=NUM_QUERIES, bot_id=BOT_ID, organization_id=ORG_ID)
        benchmark_vector_only(num_queries=NUM_QUERIES, bot_id=BOT_ID, organization_id=ORG_ID)
        benchmark_bm25_only(num_queries=NUM_QUERIES, bot_id=BOT_ID, organization_id=ORG_ID)

        # Cleanup
        cleanup(bot_id=BOT_ID)

        print("\n✅ Benchmark complete!")

    except KeyboardInterrupt:
        print("\n\nBenchmark interrupted by user")
        cleanup(bot_id=BOT_ID)
    except Exception as e:
        print(f"\n\nBenchmark failed: {str(e)}")
        traceback.print_exc()
        cleanup(bot_id=BOT_ID)
