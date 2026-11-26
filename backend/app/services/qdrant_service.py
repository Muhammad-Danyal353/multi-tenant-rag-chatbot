"""
Qdrant Service

Handles all interactions with the Qdrant vector database:
- Collection management
- Vector insertion
- Vector search
- Collection deletion
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    SearchRequest,
    PayloadSchemaType
)
from app.config import settings
from app.core.exceptions import QdrantException
import logging
import uuid

logger = logging.getLogger(__name__)

class IndexField(Enum):
    # Core identifiers
    CHUNK_ID = ("chunk_id", PayloadSchemaType.KEYWORD)
    ORGANIZATION_ID = ("organization_id", PayloadSchemaType.KEYWORD)
    BOT_ID = ("bot_id", PayloadSchemaType.KEYWORD)
    SOURCE_ID = ("source_id", PayloadSchemaType.KEYWORD)
    SOURCE_TYPE = ("source_type", PayloadSchemaType.KEYWORD)
    
    # Additional source identifiers
    DOCUMENT_ID = ("document_id", PayloadSchemaType.KEYWORD)
    WEBPAGE_ID = ("webpage_id", PayloadSchemaType.KEYWORD)
    TEXT_CONTENT_ID = ("text_content_id", PayloadSchemaType.KEYWORD)
    
    # Status and metadata
    IS_ACTIVE = ("is_active", PayloadSchemaType.BOOL)
    CREATED_AT = ("created_at", PayloadSchemaType.DATETIME)
    
    # Content field
    CONTENT = ("content", PayloadSchemaType.TEXT)


class QdrantService:
    """
    Service class for managing Qdrant vector database operations.
    """
    
    def __init__(self):
        """Initialize Qdrant client"""
        try:
            # Configure Qdrant client with proper settings
            client_config = {
                "host": settings.QDRANT_HOST,
                "port": settings.QDRANT_PORT,
                "prefer_grpc": settings.QDRANT_PREFER_GRPC,
                "https": settings.QDRANT_USE_HTTPS,  # Use config setting
                "timeout": 10,   # Add timeout
            }
            
            # Add API key if provided
            if settings.QDRANT_API_KEY:
                client_config["api_key"] = settings.QDRANT_API_KEY
            
            # Add gRPC port if not using default
            if settings.QDRANT_GRPC_PORT != 6334:
                client_config["grpc_port"] = settings.QDRANT_GRPC_PORT
            
            self.client = QdrantClient(**client_config)
            logger.info(f"Qdrant client initialized successfully with config: {client_config}")
        except Exception as e:
            logger.error(f"Failed to initialize Qdrant client: {str(e)}")
            raise QdrantException(f"Failed to connect to Qdrant: {str(e)}")
    
    def get_payload_schema(self) -> Dict[str, str]:
        """
        Get the complete payload schema definition for Qdrant collections.
        
        Returns:
            Dict[str, str]: Payload schema mapping field names to types
        """
        return {
            # Core identifiers
            "chunk_id": "keyword",
            "organization_id": "keyword",
            "bot_id": "keyword", 
            "source_id": "keyword",
            "source_type": "keyword",
            
            # Additional source identifiers
            "document_id": "keyword",
            "webpage_id": "keyword",
            "text_content_id": "keyword",
            
            # Content and metadata
            "content": "text",
            "is_active": "bool",
            "created_at": "datetime",
            
            # Note: 'metadata' is stored as JSON and not indexed
            # Individual metadata fields can be indexed separately if needed
        }
    
    def create_collection(self, collection_name: str, create_indexes: bool = True) -> bool:
        """
        Create a new collection in Qdrant with optional payload indexes.
        
        Args:
            collection_name: Name of the collection to create
            create_indexes: Whether to create payload indexes for common fields
            
        Returns:
            bool: True if successful
            
        Raises:
            QdrantException: If collection creation fails
        """
        try:
            # Check if collection already exists
            collections = self.client.get_collections().collections
            if any(col.name == collection_name for col in collections):
                logger.info(f"Collection {collection_name} already exists")
                return True
            
            # Create collection with vector configuration
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=settings.EMBEDDING_DIMENSION,
                    distance=Distance.COSINE
                )
            )
            
            logger.info(f"Collection {collection_name} created successfully")
            
            # Create payload indexes for better query performance
            if create_indexes:
                self._create_payload_indexes(collection_name)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to create collection {collection_name}: {str(e)}")
            raise QdrantException(f"Failed to create collection: {str(e)}")
    
    def create_collection_with_text_index(
        self,
        collection_name: str,
        vector_size: int = 384,
        distance: str = "Cosine"
    ) -> bool:
        """
        Create collection with text indexing for hybrid search.
        
        Args:
            collection_name: Name of the collection
            vector_size: Dimension of vectors (default 384 for all-MiniLM-L6-v2)
            distance: Distance metric (Cosine, Euclid, Dot)
            
        Returns:
            bool: True if successful
            
        Raises:
            QdrantException: If collection creation fails
        """
        try:
            # Check if collection already exists
            collections = self.client.get_collections().collections
            if any(col.name == collection_name for col in collections):
                logger.info(f"Collection {collection_name} already exists")
                return True
            
            # Map distance string to enum
            distance_map = {
                "Cosine": Distance.COSINE,
                "Euclid": Distance.EUCLID,
                "Dot": Distance.DOT
            }
            
            # Create collection with vector configuration
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=distance_map.get(distance, Distance.COSINE)
                ),
                # Enable on-disk payload for better memory usage
                on_disk_payload=True
            )
            
            logger.info(f"Collection '{collection_name}' created with vector config")
            
            # Create text index on content field for BM25-like search
            self.client.create_payload_index(
                collection_name=collection_name,
                field_name="content",
                field_schema=PayloadSchemaType.TEXT
            )
            
            logger.info(f"Text index created for 'content' field in '{collection_name}'")
            
            # Create other payload indexes
            self._create_payload_indexes(collection_name)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to create collection with text index: {str(e)}")
            raise QdrantException(f"Failed to create collection with text index: {str(e)}")

            
    def validate_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and normalize payload data against the schema.
        
        Args:
            payload: Raw payload data
            
        Returns:
            Dict[str, Any]: Validated and normalized payload
            
        Raises:
            QdrantException: If payload validation fails
        """
        try:
            validated_payload = {}
            schema = self.get_payload_schema()
            
            # Validate required fields
            required_fields = ["chunk_id", "organization_id", "bot_id", "source_id", "source_type"]
            for field in required_fields:
                if field not in payload:
                    raise QdrantException(f"Required field '{field}' missing from payload")
                validated_payload[field] = payload[field]
            
            # Validate optional fields
            optional_fields = ["document_id", "webpage_id", "text_content_id", "content", "is_active", "created_at", "metadata"]
            for field in optional_fields:
                if field in payload:
                    validated_payload[field] = payload[field]
            
            # Set defaults for missing optional fields
            if "is_active" not in validated_payload:
                validated_payload["is_active"] = True
            
            if "created_at" not in validated_payload:
                from datetime import datetime
                validated_payload["created_at"] = datetime.utcnow().isoformat()
            
            if "metadata" not in validated_payload:
                validated_payload["metadata"] = {}
            
            logger.debug(f"Payload validated successfully: {len(validated_payload)} fields")
            return validated_payload
            
        except Exception as e:
            logger.error(f"Payload validation failed: {str(e)}")
            raise QdrantException(f"Payload validation failed: {str(e)}")
    
    def delete_collection(self, collection_name: str) -> bool:
        """
        Delete a collection from Qdrant.
        
        Args:
            collection_name: Name of the collection to delete
            
        Returns:
            bool: True if successful
        """
        try:
            self.client.delete_collection(collection_name=collection_name)
            logger.info(f"Collection {collection_name} deleted successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to delete collection {collection_name}: {str(e)}")
            raise QdrantException(f"Failed to delete collection: {str(e)}")
    
    def insert_vectors(
        self,
        collection_name: str,
        vectors: List[List[float]],
        payloads: List[Dict[str, Any]],
        ids: Optional[List[str]] = None
    ) -> bool:
        """
        Insert vectors into a collection with full payload data.
        
        RECOMMENDED: Store chunk content in payload for single-query retrieval.
        This avoids the need for PostgreSQL lookups after vector search.
        
        Args:
            collection_name: Name of the collection
            vectors: List of embedding vectors
            payloads: List of metadata payloads for each vector (INCLUDING content)
            ids: Optional list of IDs for the vectors
            
        Returns:
            bool: True if successful
            
        Example payload structure:
        {
            # Core identifiers
            "chunk_id": "chunk_123",
            "organization_id": "org_abc",
            "bot_id": "bot_xyz",
            "source_id": "source_456",
            "source_type": "document",
            
            # Additional source identifiers (optional, based on source type)
            "document_id": "doc_789",           # If source_type is "document"
            "webpage_id": "web_101",            # If source_type is "webpage"
            "text_content_id": "text_202",      # If source_type is "text"
            
            # Content and metadata
            "content": "The actual chunk text content...",  # STORED HERE
            "is_active": True,
            "created_at": "2024-01-01T00:00:00Z",
            
            # Additional metadata (stored as JSON, not indexed)
            "metadata": {
                "page_number": 5,
                "document_name": "guide.pdf",
                "section": "Introduction",
                "url": "https://example.com/page",
                "author": "John Doe",
                "tags": ["tutorial", "beginner"]
            }
        }
        """
        try:
            # Generate IDs if not provided
            if ids is None:
                ids = [str(uuid.uuid4()) for _ in range(len(vectors))]
            
            # Validate and normalize payloads
            validated_payloads = []
            for payload in payloads:
                validated_payload = self.validate_payload(payload)
                validated_payloads.append(validated_payload)
            
            # Create points
            points = [
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload
                )
                for point_id, vector, payload in zip(ids, vectors, validated_payloads)
            ]
            
            # Upsert points into collection
            self.client.upsert(
                collection_name=collection_name,
                points=points
            )
            
            logger.info(f"Inserted {len(points)} vectors into {collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to insert vectors into {collection_name}: {str(e)}")
            raise QdrantException(f"Failed to insert vectors: {str(e)}")
    
    def search_vectors(
        self,
        collection_name: str,
        query_vector: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        score_threshold: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar vectors in a collection.
        
        Args:
            collection_name: Name of the collection to search
            query_vector: Query embedding vector
            top_k: Number of results to return
            filters: Optional filters for metadata
            score_threshold: Minimum similarity score threshold
            
        Returns:
            List of search results with scores and payloads
        """
        try:
            # Build filter if provided
            query_filter = None
            if filters:
                conditions = []
                for key, value in filters.items():
                    conditions.append(
                        FieldCondition(
                            key=key,
                            match=MatchValue(value=value)
                        )
                    )
                query_filter = Filter(must=conditions)
            
            # Perform search
            search_results = self.client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=top_k,
                query_filter=query_filter,
                score_threshold=score_threshold
            )
            
            # Format results
            results = []
            for result in search_results:
                results.append({
                    "id": result.id,
                    "score": result.score,
                    "payload": result.payload
                })
            
            logger.info(f"Found {len(results)} results in {collection_name}")
            return results
            
        except Exception as e:
            logger.error(f"Failed to search vectors in {collection_name}: {str(e)}")
            raise QdrantException(f"Failed to search vectors: {str(e)}")
    
    def search_text(
        self,
        collection_name: str,
        query_text: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform text-based search using Qdrant's full-text search.
        
        Args:
            collection_name: Name of the collection
            query_text: Text query
            top_k: Number of results
            filters: Metadata filters
            
        Returns:
            List of search results
        """
        try:
            # Build filter conditions
            filter_conditions = None
            if filters:
                conditions = []
                for key, value in filters.items():
                    if isinstance(value, list):
                        # Handle list values (e.g., source_types)
                        for v in value:
                            conditions.append(
                                FieldCondition(
                                    key=key,
                                    match=MatchValue(value=v)
                                )
                            )
                    else:
                        conditions.append(
                            FieldCondition(
                                key=key,
                                match=MatchValue(value=value)
                            )
                        )
                
                if conditions:
                    filter_conditions = Filter(must=conditions)
            
            # Perform text search using scroll
            results = self.client.scroll(
                collection_name=collection_name,
                scroll_filter=filter_conditions,
                limit=top_k,
                with_payload=True,
                with_vectors=False
            )
            
            # Format results
            formatted_results = []
            for point in results[0]:  # results is tuple (points, next_offset)
                # Calculate simple text match score
                content = point.payload.get("content", "").lower()
                query_lower = query_text.lower()
                
                # Simple scoring: count query term occurrences
                score = sum(content.count(term) for term in query_lower.split())
                
                formatted_results.append({
                    "id": point.id,
                    "score": score,
                    "payload": point.payload
                })
            
            # Sort by score
            formatted_results.sort(key=lambda x: x["score"], reverse=True)
            
            return formatted_results[:top_k]
            
        except Exception as e:
            logger.error(f"Text search failed: {str(e)}")
            return []
    
    def delete_vectors(
        self,
        collection_name: str,
        point_ids: List[str]
    ) -> bool:
        """
        Delete vectors from a collection.
        
        Args:
            collection_name: Name of the collection
            point_ids: List of point IDs to delete
            
        Returns:
            bool: True if successful
        """
        try:
            self.client.delete(
                collection_name=collection_name,
                points_selector=point_ids
            )
            
            logger.info(f"Deleted {len(point_ids)} vectors from {collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete vectors from {collection_name}: {str(e)}")
            raise QdrantException(f"Failed to delete vectors: {str(e)}")
    
    def delete_points_by_filter(
        self,
        collection_name: str,
        filter_dict: Dict[str, Any]
    ) -> bool:
        """
        Delete points from a collection using metadata filters.
        
        Args:
            collection_name: Name of the collection
            filter_dict: Dictionary with field-value pairs to filter by
                        Example: {"source_id": "abc-123", "bot_id": "bot-456"}
        
        Returns:
            bool: True if successful
        """
        try:
            from qdrant_client.models import FilterSelector
            
            # Build filter conditions
            must_conditions = []
            for field, value in filter_dict.items():
                must_conditions.append(
                    FieldCondition(
                        key=field,
                        match=MatchValue(value=value)
                    )
                )
            
            # Create filter
            filter_selector = FilterSelector(
                filter=Filter(must=must_conditions)
            )
            
            # Delete points matching the filter
            self.client.delete(
                collection_name=collection_name,
                points_selector=filter_selector
            )
            
            logger.info(f"Deleted points from {collection_name} with filter: {filter_dict}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete points by filter from {collection_name}: {str(e)}")
            raise QdrantException(f"Failed to delete points by filter: {str(e)}")
    
    def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """
        Get information about a collection.
        
        Args:
            collection_name: Name of the collection
            
        Returns:
            Dictionary with collection information
        """
        try:
            collection_info = self.client.get_collection(collection_name=collection_name)
            
            return {
                "name": collection_name,
                "vectors_count": collection_info.points_count,
                "vector_size": collection_info.config.params.vectors.size,
                "distance": collection_info.config.params.vectors.distance.name
            }
            
        except Exception as e:
            logger.error(f"Failed to get info for collection {collection_name}: {str(e)}")
            raise QdrantException(f"Failed to get collection info: {str(e)}")
    
    def get_collection_vectors(
        self,
        collection_name: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Get vectors from a collection for text search.
        
        Args:
            collection_name: Name of the collection
            filters: Optional metadata filters
            limit: Maximum number of vectors to return
            
        Returns:
            List of vectors with payloads
        """
        try:
            # Build filter if provided
            query_filter = None
            if filters:
                conditions = []
                for key, value in filters.items():
                    if isinstance(value, list):
                        # Handle list values (e.g., source_type in [document, web])
                        conditions.append(
                            FieldCondition(
                                key=key,
                                match=MatchValue(value=value[0])  # Simplified for now
                            )
                        )
                    else:
                        conditions.append(
                            FieldCondition(
                                key=key,
                                match=MatchValue(value=value)
                            )
                        )
                query_filter = Filter(must=conditions)
            
            # Scroll through collection
            vectors = []
            offset = None
            
            while len(vectors) < limit:
                # Use scroll to get vectors
                scroll_result = self.client.scroll(
                    collection_name=collection_name,
                    limit=min(100, limit - len(vectors)),
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,  # We don't need vectors for text search
                    scroll_filter=query_filter
                )
                
                points = scroll_result[0]
                if not points:
                    break
                
                for point in points:
                    vectors.append({
                        "id": point.id,
                        "payload": point.payload
                    })
                
                offset = scroll_result[1]
                if offset is None:
                    break
            
            logger.debug(f"Retrieved {len(vectors)} vectors from {collection_name}")
            return vectors
            
        except Exception as e:
            logger.error(f"Failed to get vectors from {collection_name}: {str(e)}")
            raise QdrantException(f"Failed to get collection vectors: {str(e)}")
    
    def _create_payload_indexes(self, collection_name: str) -> None:
        """
        Create payload indexes for frequently filtered fields.
        
        This is CRITICAL for performance, especially for:
        - Multi-tenant isolation (organization_id)
        - Bot-specific searches (bot_id)
        - Source filtering (source_id, source_type)
        - Active status filtering (is_active)
        
        Args:
            collection_name: Name of the collection
        """
        # Define fields to index
        # Using keyword type for exact matching on IDs and strings
        # Using bool type for boolean fields
        # Using datetime type for timestamp fields
        indexes_to_create = [field.value for field in IndexField]
        
        for field_name, schema_type in indexes_to_create:
            self._safe_create_index(collection_name, field_name, schema_type)
    
    def _safe_create_index(
        self,
        collection_name: str,
        field_name: str,
        schema_type: PayloadSchemaType,
    ) -> None:
        """
        Safely create a payload index, logging warnings on failure.
        
        Args:
            collection_name: Name of the collection
            field_name: Name of the field to index
            schema_type: Type of the field (keyword, integer, bool, etc.)
        """
        try:
            self.client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=schema_type,
            )
            logger.info(
                f"Created index for field '{field_name}' in collection '{collection_name}'"
            )
        except Exception as e:
            # Don't fail collection creation if index creation fails
            # Some indexes might already exist
            logger.warning(
                f"Index creation skipped for field '{field_name}' in '{collection_name}': {e}"
            )
    
    def create_payload_index(
        self,
        collection_name: str,
        field_name: str,
        schema_type: PayloadSchemaType
    ) -> bool:
        """
        Manually create a payload index for a specific field.
        
        Args:
            collection_name: Name of the collection
            field_name: Name of the field to index
            schema_type: Type of the field
            
        Returns:
            bool: True if successful
            
        Example:
            >>> from qdrant_client.models import PayloadSchemaType
            >>> qdrant_service.create_payload_index(
            ...     "my_collection",
            ...     "custom_field",
            ...     PayloadSchemaType.KEYWORD
            ... )
        """
        try:
            self.client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=schema_type
            )
            logger.info(f"Created index for '{field_name}' in '{collection_name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to create index for '{field_name}': {str(e)}")
            raise QdrantException(f"Failed to create payload index: {str(e)}")
    
    def test_connection(self) -> bool:
        """
        Test the connection to Qdrant service.
        
        Returns:
            bool: True if connection is successful
        """
        try:
            # Try to get collections to test connection
            self.client.get_collections()
            logger.debug("Qdrant connection test successful")
            return True
        except Exception as e:
            logger.error(f"Qdrant connection test failed: {str(e)}")
            
            # Try to reconnect with different settings
            try:
                logger.info("Attempting to reconnect with HTTP only...")
                self._reconnect_with_http()
                self.client.get_collections()
                logger.info("Qdrant reconnection successful")
                return True
            except Exception as reconnect_error:
                logger.error(f"Qdrant reconnection failed: {str(reconnect_error)}")
                return False
    
    def _reconnect_with_http(self):
        """
        Reconnect to Qdrant using HTTP only (no gRPC).
        """
        try:
            # Create new client with HTTP only
            self.client = QdrantClient(
                host=settings.QDRANT_HOST,
                port=settings.QDRANT_PORT,
                prefer_grpc=False,  # Force HTTP
                https=False,        # Disable HTTPS
                timeout=10
            )
            logger.info("Reconnected to Qdrant with HTTP only")
        except Exception as e:
            logger.error(f"Failed to reconnect with HTTP: {str(e)}")
            raise
    
    def list_collections(self) -> List[str]:
        """
        List all collections in Qdrant.
        
        Returns:
            List[str]: List of collection names
        """
        try:
            collections = self.client.get_collections()
            collection_names = [col.name for col in collections.collections]
            logger.info(f"Found {len(collection_names)} collections")
            return collection_names
        except Exception as e:
            logger.error(f"Failed to list collections: {str(e)}")
            raise QdrantException(f"Failed to list collections: {str(e)}")
    
    def collection_exists(self, collection_name: str) -> bool:
        """
        Check if a collection exists.
        
        Args:
            collection_name: Name of the collection
            
        Returns:
            bool: True if collection exists
        """
        try:
            collections = self.client.get_collections().collections
            return any(col.name == collection_name for col in collections)
        except Exception as e:
            logger.error(f"Failed to check collection existence: {str(e)}")
            return False
    
    def check_health(self) -> bool:
        """
        Check if Qdrant service is healthy.
        
        Returns:
            bool: True if healthy
        """
        try:
            collections = self.client.get_collections()
            return True
        except Exception as e:
            logger.error(f"Qdrant health check failed: {str(e)}")
            return False


# Global variable to store the singleton instance
_qdrant_service_instance = None


def get_qdrant_service() -> QdrantService:
    """
    Get the singleton instance of QdrantService.
    
    This function ensures only one instance of QdrantService is created
    and reused throughout the application lifecycle.
    
    Returns:
        QdrantService: The singleton instance
        
    Example:
        >>> qdrant_service = get_qdrant_service()
        >>> qdrant_service.create_collection("my_collection")
    """
    global _qdrant_service_instance
    
    if _qdrant_service_instance is None:
        logger.info("Creating new QdrantService instance")
        _qdrant_service_instance = QdrantService()
    else:
        logger.debug("Returning existing QdrantService instance")
    
    return _qdrant_service_instance


# Backward compatibility - create instance on import
qdrant_service = get_qdrant_service()


# Export
__all__ = ["get_qdrant_service", "qdrant_service", "QdrantService"]

