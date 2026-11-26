"""
Embedding Service

Handles text embedding generation using sentence transformers.
- Model: sentence-transformers/all-MiniLM-L6-v2 (384 dimensions)
- Batch processing for efficiency
- Model caching
- GPU/CPU optimization
"""

import logging
import os
from typing import List, Union, Dict, Any, Optional
import numpy as np
from pathlib import Path

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logging.warning("sentence-transformers not installed. Embedding generation will not be available.")

from app.config import settings
from app.services.cache_service import get_query_cache

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Service for generating text embeddings using sentence transformers.
    """
    
    # Model configuration
    DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION = 384
    
    def __init__(
        self,
        model_name: str = None,
        batch_size: int = None,
        cache_folder: str = None
    ):
        """
        Initialize embedding service.
        
        Args:
            model_name: Name of the sentence transformer model
            batch_size: Batch size for processing
            cache_folder: Folder to cache model files
        """
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise RuntimeError(
                "sentence-transformers is required for embedding generation. "
                "Install it with: pip install sentence-transformers"
            )
        
        self.model_name = model_name or self.DEFAULT_MODEL
        self.batch_size = batch_size or settings.EMBEDDING_BATCH_SIZE
        self.cache_folder = cache_folder or str(settings.EMBEDDING_MODELS_PATH)
        self.query_cache = get_query_cache()
        
        self.model = None
        self._load_model()
    
    # ========================================================================
    # MODEL MANAGEMENT
    # ========================================================================
    
    def _load_model(self):
        """
        Load sentence transformer model.
        """
        try:
            logger.info(f"Loading embedding model: {self.model_name}")
            
            # Ensure cache folder exists
            os.makedirs(self.cache_folder, exist_ok=True)
            
            # Load model
            self.model = SentenceTransformer(
                self.model_name,
                cache_folder=self.cache_folder
            )
            
            # Get embedding dimension
            self.embedding_dim = self.model.get_sentence_embedding_dimension()
            
            logger.info(
                f"Model loaded successfully. "
                f"Embedding dimension: {self.embedding_dim}"
            )
            
        except Exception as e:
            logger.error(f"Error loading embedding model: {str(e)}")
            raise
    
    def download_model(self):
        """
        Download model to cache folder (if not already cached).
        """
        if not self.model:
            self._load_model()
        logger.info(f"Model ready at: {self.cache_folder}")
    
    # ========================================================================
    # EMBEDDING GENERATION
    # ========================================================================
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Input text
            
        Returns:
            List[float]: Embedding vector
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
        
        try:
            # Check cache first
            cached_embedding = self.query_cache.get_embedding(text)
            if cached_embedding is not None:
                logger.debug(f"Cache hit for embedding: {text[:50]}...")
                return cached_embedding
            
            # Generate embedding
            embedding = self.model.encode(
                text,
                convert_to_numpy=True,
                show_progress_bar=False
            )
            
            # Convert to list
            embedding_list = embedding.tolist()
            
            # Cache the embedding
            self.query_cache.set_embedding(text, embedding_list)
            
            return embedding_list
            
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            raise
    
    def generate_embeddings(
        self,
        texts: List[str],
        show_progress: bool = False
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts (batch processing).
        
        Args:
            texts: List of input texts
            show_progress: Whether to show progress bar
            
        Returns:
            List[List[float]]: List of embedding vectors
        """
        if not texts:
            return []
        
        # Filter out empty texts
        valid_texts = [t for t in texts if t and t.strip()]
        
        if not valid_texts:
            raise ValueError("No valid texts to embed")
        
        try:
            logger.info(f"Generating embeddings for {len(valid_texts)} texts")
            
            # Generate embeddings in batches
            embeddings = self.model.encode(
                valid_texts,
                batch_size=self.batch_size,
                convert_to_numpy=True,
                show_progress_bar=show_progress
            )
            
            # Convert to list
            embeddings_list = embeddings.tolist()
            
            logger.info(f"Generated {len(embeddings_list)} embeddings")
            
            return embeddings_list
            
        except Exception as e:
            logger.error(f"Error generating embeddings: {str(e)}")
            raise
    
    # ========================================================================
    # CHUNK EMBEDDING
    # ========================================================================
    
    def embed_chunks(
        self,
        chunks: List[Dict[str, Any]],
        content_key: str = "content"
    ) -> List[Dict[str, Any]]:
        """
        Generate embeddings for chunks and add to chunk data.
        
        Args:
            chunks: List of chunk dictionaries
            content_key: Key containing the text content
            
        Returns:
            List[Dict]: Chunks with embeddings added
        """
        if not chunks:
            return []
        
        try:
            # Extract texts
            texts = [chunk.get(content_key, "") for chunk in chunks]
            
            # Generate embeddings
            embeddings = self.generate_embeddings(texts)
            
            # Add embeddings to chunks
            for chunk, embedding in zip(chunks, embeddings):
                chunk["embedding"] = embedding
            
            logger.info(f"Added embeddings to {len(chunks)} chunks")
            
            return chunks
            
        except Exception as e:
            logger.error(f"Error embedding chunks: {str(e)}")
            raise
    
    # ========================================================================
    # SIMILARITY CALCULATION
    # ========================================================================
    
    def calculate_similarity(
        self,
        embedding1: Union[List[float], np.ndarray],
        embedding2: Union[List[float], np.ndarray]
    ) -> float:
        """
        Calculate cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding
            embedding2: Second embedding
            
        Returns:
            float: Similarity score (0-1)
        """
        # Convert to numpy arrays
        emb1 = np.array(embedding1)
        emb2 = np.array(embedding2)
        
        # Calculate cosine similarity
        dot_product = np.dot(emb1, emb2)
        norm1 = np.linalg.norm(emb1)
        norm2 = np.linalg.norm(emb2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        similarity = dot_product / (norm1 * norm2)
        
        # Ensure in range [0, 1]
        similarity = max(0.0, min(1.0, similarity))
        
        return float(similarity)
    
    def find_most_similar(
        self,
        query_embedding: Union[List[float], np.ndarray],
        embeddings: List[Union[List[float], np.ndarray]],
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find most similar embeddings to query.
        
        Args:
            query_embedding: Query embedding
            embeddings: List of embeddings to compare
            top_k: Number of top results to return
            
        Returns:
            List[Dict]: List of {index, similarity} dicts
        """
        similarities = []
        
        for idx, emb in enumerate(embeddings):
            sim = self.calculate_similarity(query_embedding, emb)
            similarities.append({"index": idx, "similarity": sim})
        
        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x["similarity"], reverse=True)
        
        return similarities[:top_k]
    
    # ========================================================================
    # MODEL INFO
    # ========================================================================
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the loaded model.
        
        Returns:
            Dict: Model information
        """
        return {
            "model_name": self.model_name,
            "embedding_dimension": self.embedding_dim,
            "batch_size": self.batch_size,
            "cache_folder": self.cache_folder,
            "model_loaded": self.model is not None
        }


# ============================================================================
# GLOBAL INSTANCE
# ============================================================================

# Create a singleton instance
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """
    Get or create the global embedding service instance (Singleton pattern).
    This ensures the embedding model is loaded only once and reused across requests.
    
    Returns:
        EmbeddingService: The singleton embedding service
    """
    global _embedding_service
    
    if _embedding_service is None:
        try:
            logger.info("Initializing embedding service singleton...")
            _embedding_service = EmbeddingService()
            logger.info("✓ Embedding service singleton initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize embedding service: {str(e)}")
            raise
    else:
        logger.debug("Using existing embedding service singleton instance")
    
    return _embedding_service


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def generate_query_embedding(query: str) -> List[float]:
    """
    Generate embedding for a search query (convenience function).
    
    Args:
        query: Search query text
        
    Returns:
        List[float]: Query embedding
    """
    service = get_embedding_service()
    return service.generate_embedding(query)


def embed_document_chunks(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Generate embeddings for document chunks (convenience function).
    
    Args:
        chunks: List of chunk dictionaries
        
    Returns:
        List[Dict]: Chunks with embeddings added
    """
    service = get_embedding_service()
    return service.embed_chunks(chunks)


def download_embedding_model():
    """
    Download embedding model (convenience function).
    Useful for initial setup or deployment.
    """
    service = get_embedding_service()
    service.download_model()
    logger.info("Embedding model download complete")


# ============================================================================
# CLI FOR DOWNLOADING MODEL
# ============================================================================

if __name__ == "__main__":
    """
    Run this script to download the embedding model:
    python -m app.services.embedding_service
    """
    import sys
    
    print("=" * 60)
    print("Embedding Model Download")
    print("=" * 60)
    
    try:
        download_embedding_model()
        print("\n✓ Model downloaded successfully!")
        print(f"Location: {settings.EMBEDDING_MODEL_PATH}")
        
        # Test embedding generation
        print("\nTesting embedding generation...")
        service = get_embedding_service()
        test_embedding = service.generate_embedding("This is a test sentence.")
        print(f"✓ Test embedding generated: {len(test_embedding)} dimensions")
        
        # Print model info
        info = service.get_model_info()
        print("\nModel Information:")
        for key, value in info.items():
            print(f"  {key}: {value}")
        
        sys.exit(0)
        
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        sys.exit(1)

