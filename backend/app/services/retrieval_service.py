"""
Retrieval Service

Implements hybrid search combining vector similarity and BM25 keyword search:
- Vector search using Qdrant
- BM25 text search for keyword matching
- Hybrid ranking with Reciprocal Rank Fusion (RRF)
- Metadata filtering for tenant isolation
- Deduplication logic
"""

import logging
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
import math

from app.services.qdrant_service import get_qdrant_service
from app.services.embedding_service import get_embedding_service
from app.services.cache_service import get_query_cache, get_cache_service
from app.core.exceptions import RetrievalException
from app.config import settings

logger = logging.getLogger(__name__)


class RetrievalService:
    """
    Service for hybrid search combining vector similarity and BM25 keyword search.
    """
    
    def __init__(self):
        """Initialize retrieval service."""
        self.qdrant_service = get_qdrant_service()
        self.embedding_service = get_embedding_service()
        self.query_cache = get_query_cache()
        self.cache_service = get_cache_service()
        
        # Hybrid search parameters
        self.alpha = settings.HYBRID_SEARCH_ALPHA  # Weight for vector vs BM25
        self.rrf_k = 60  # RRF parameter
        self.similarity_threshold = settings.SIMILARITY_THRESHOLD
        
    def hybrid_search(
        self,
        query: str,
        bot_id: str,
        organization_id: str,
        top_k: int = None,
        filters: Optional[Dict[str, Any]] = None,
        source_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search combining vector similarity and BM25.
        
        Args:
            query: Search query text
            bot_id: Bot ID for collection name
            organization_id: Organization ID for tenant isolation
            top_k: Number of results to return
            filters: Additional metadata filters
            source_types: Filter by source types (document, web, text)
            
        Returns:
            List of ranked search results with metadata
        """
        try:
            top_k = top_k or settings.DEFAULT_TOP_K
            
            # Check cache first
            cached_results = self.query_cache.get_query_result(
                query=query,
                bot_id=bot_id,
                organization_id=organization_id,
                filters=filters
            )
            
            if cached_results is not None:
                logger.debug(f"Cache hit for query: {query[:50]}...")
                return cached_results[:top_k]
            
            # Build base filters for tenant isolation
            base_filters = {
                "organization_id": organization_id,
                "bot_id": bot_id,
                "is_active": True
            }
            
            # Add source type filter if specified
            if source_types:
                base_filters["source_type"] = source_types
            
            # Merge with additional filters
            if filters:
                base_filters.update(filters)
            
            # 1. Vector search
            vector_results = self._vector_search(
                query=query,
                bot_id=bot_id,
                filters=base_filters,
                top_k=top_k * 2  # Get more results for better ranking
            )
            
            # 2. BM25 keyword search
            bm25_results = self._bm25_search(
                query=query,
                bot_id=bot_id,
                filters=base_filters,
                top_k=top_k * 2
            )
            
            # 3. Combine results with RRF
            hybrid_results = self._combine_with_rrf(
                vector_results=vector_results,
                bm25_results=bm25_results,
                top_k=top_k
            )
            
            # 4. Apply similarity threshold
            filtered_results = self._apply_similarity_threshold(hybrid_results)
            
            # 5. Deduplicate results
            deduplicated_results = self._deduplicate_results(filtered_results)
            
            # Cache the results
            self.query_cache.set_query_result(
                query=query,
                bot_id=bot_id,
                organization_id=organization_id,
                results=deduplicated_results,
                filters=filters
            )
            
            logger.info(
                f"Hybrid search completed: {len(deduplicated_results)} results for query '{query[:50]}...'"
            )
            
            return deduplicated_results[:top_k]
            
        except Exception as e:
            logger.error(f"Hybrid search failed: {str(e)}")
            raise RetrievalException(f"Hybrid search failed: {str(e)}")
    
    def _vector_search(
        self,
        query: str,
        bot_id: str,
        filters: Dict[str, Any],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Perform vector similarity search using embeddings.
        
        Args:
            query: Search query
            bot_id: Bot ID for collection
            filters: Metadata filters
            top_k: Number of results
            
        Returns:
            List of vector search results
        """
        try:
            # Generate query embedding
            query_embedding = self.embedding_service.generate_embedding(query)
            
            # Collection name for this bot
            collection_name = f"bot_{bot_id}"
            
            # Search in Qdrant
            results = self.qdrant_service.search_vectors(
                collection_name=collection_name,
                query_vector=query_embedding,
                top_k=top_k,
                filters=filters,
                score_threshold=self.similarity_threshold
            )
            
            # Format results
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "id": result["id"],
                    "score": result["score"],
                    "content": result["payload"].get("content", ""),
                    "metadata": result["payload"],
                    "search_type": "vector"
                })
            
            logger.debug(f"Vector search returned {len(formatted_results)} results")
            return formatted_results
            
        except Exception as e:
            logger.error(f"Vector search failed: {str(e)}")
            return []
    
    def _bm25_search(
        self,
        query: str,
        bot_id: str,
        filters: Dict[str, Any],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Perform BM25-like keyword search using Qdrant text search.
        
        Args:
            query: Search query
            bot_id: Bot ID for collection
            filters: Metadata filters
            top_k: Number of results
            
        Returns:
            List of BM25 search results
        """
        try:
            collection_name = f"bot_{bot_id}"
            
            # Use Qdrant's text search
            results = self.qdrant_service.search_text(
                collection_name=collection_name,
                query_text=query,
                top_k=top_k,
                filters=filters
            )
            
            # Format results
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "id": result["id"],
                    "score": result["score"],
                    "content": result["payload"].get("content", ""),
                    "metadata": result["payload"],
                    "search_type": "bm25"
                })
            
            logger.debug(f"BM25 search returned {len(formatted_results)} results")
            return formatted_results
            
        except Exception as e:
            logger.error(f"BM25 search failed: {str(e)}")
            return []
    
    def _combine_with_rrf(
        self,
        vector_results: List[Dict[str, Any]],
        bm25_results: List[Dict[str, Any]],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Combine vector and BM25 results using Reciprocal Rank Fusion (RRF).
        
        Args:
            vector_results: Results from vector search
            bm25_results: Results from BM25 search
            top_k: Number of final results
            
        Returns:
            Combined and ranked results
        """
        # Create score maps
        vector_scores = {}
        bm25_scores = {}
        
        # Map vector results
        for rank, result in enumerate(vector_results):
            doc_id = result["id"]
            vector_scores[doc_id] = 1.0 / (self.rrf_k + rank + 1)
        
        # Map BM25 results
        for rank, result in enumerate(bm25_results):
            doc_id = result["id"]
            bm25_scores[doc_id] = 1.0 / (self.rrf_k + rank + 1)
        
        # Combine scores
        combined_scores = defaultdict(float)
        all_docs = set(vector_scores.keys()) | set(bm25_scores.keys())
        
        for doc_id in all_docs:
            vector_score = vector_scores.get(doc_id, 0)
            bm25_score = bm25_scores.get(doc_id, 0)
            
            # Weighted combination
            combined_score = (
                self.alpha * vector_score + 
                (1 - self.alpha) * bm25_score
            )
            combined_scores[doc_id] = combined_score
        
        # Create result map
        result_map = {}
        for result in vector_results + bm25_results:
            doc_id = result["id"]
            if doc_id not in result_map:
                result_map[doc_id] = result
        
        # Sort by combined score
        sorted_docs = sorted(
            combined_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Build final results
        final_results = []
        for doc_id, score in sorted_docs:
            if doc_id in result_map:
                result = result_map[doc_id].copy()
                result["hybrid_score"] = score
                result["vector_score"] = vector_scores.get(doc_id, 0)
                result["bm25_score"] = bm25_scores.get(doc_id, 0)
                final_results.append(result)
        
        return final_results
    
    def _apply_similarity_threshold(
        self,
        results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Apply similarity threshold to filter results.
        
        Args:
            results: Search results
            
        Returns:
            Filtered results above threshold
        """
        filtered_results = []
        
        for result in results:
            # Use hybrid score if available, otherwise use original score
            score = result.get("hybrid_score", result.get("score", 0))
            
            if score >= self.similarity_threshold:
                filtered_results.append(result)
        
        return filtered_results
    
    def _deduplicate_results(
        self,
        results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Remove duplicate results based on content similarity.
        
        Args:
            results: Search results
            
        Returns:
            Deduplicated results
        """
        if not results:
            return results
        
        # Group by content hash for exact duplicates
        content_hashes = {}
        deduplicated = []
        
        for result in results:
            content = result.get("content", "")
            content_hash = hashlib.md5(content.encode()).hexdigest()
            
            if content_hash not in content_hashes:
                content_hashes[content_hash] = result
                deduplicated.append(result)
            else:
                # Keep the one with higher score
                existing = content_hashes[content_hash]
                if result.get("hybrid_score", 0) > existing.get("hybrid_score", 0):
                    # Replace with better result
                    content_hashes[content_hash] = result
                    # Update in deduplicated list
                    for i, dedup_result in enumerate(deduplicated):
                        if dedup_result["id"] == existing["id"]:
                            deduplicated[i] = result
                            break
        
        return deduplicated
    
    def get_source_attribution(
        self,
        results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Format results for source attribution in chat responses.
        
        Args:
            results: Search results
            
        Returns:
            Formatted source attribution data
        """
        sources = []
        
        for result in results:
            metadata = result.get("metadata", {})
            source_type = metadata.get("source_type", "unknown")
            
            source_info = {
                "content": result.get("content", ""),
                "source_type": source_type,
                "source_id": metadata.get("source_id"),
                "score": result.get("hybrid_score", result.get("score", 0))
            }
            
            # Add source-specific information
            if source_type == "document":
                source_info.update({
                    "source_name": metadata.get("document_name", "Unknown Document"),
                    "page": metadata.get("page_number"),
                    "section": metadata.get("section")
                })
            elif source_type == "web":
                source_info.update({
                    "source_name": metadata.get("webpage_title", "Unknown Webpage"),
                    "url": metadata.get("url"),
                    "domain": metadata.get("domain")
                })
            elif source_type == "text":
                source_info.update({
                    "source_name": metadata.get("text_title", "Unknown Text"),
                    "category": metadata.get("category"),
                    "tags": metadata.get("tags", [])
                })
            
            sources.append(source_info)
        
        return sources


# ============================================================================
# GLOBAL INSTANCE
# ============================================================================

# Create a singleton instance
_retrieval_service: Optional[RetrievalService] = None


def get_retrieval_service() -> RetrievalService:
    """
    Get the global retrieval service instance.
    
    Returns:
        RetrievalService: Global instance
    """
    global _retrieval_service
    
    if _retrieval_service is None:
        _retrieval_service = RetrievalService()
    
    return _retrieval_service
