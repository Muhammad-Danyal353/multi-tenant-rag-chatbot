"""
Document Processor Service

Handles document parsing, text extraction, and chunking for various file types:
- PDF (.pdf)
- Microsoft Word (.docx)
- Text files (.txt)
- Markdown (.md)
"""

import os
import re
import logging
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path
import mimetypes

# PDF parsing
try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False
    logging.warning("PyPDF2 not installed. PDF parsing will not be available.")

# DOCX parsing
try:
    import docx
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    logging.warning("python-docx not installed. DOCX parsing will not be available.")

from app.config import settings

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """
    Document processor for extracting text from various file formats.
    """
    
    # Supported file types
    SUPPORTED_EXTENSIONS = {
        '.pdf': 'application/pdf',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.txt': 'text/plain',
        '.md': 'text/markdown'
    }
    
    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None
    ):
        """
        Initialize document processor.
        
        Args:
            chunk_size: Size of text chunks (in characters)
            chunk_overlap: Overlap between chunks (in characters)
        """
        self.chunk_size = chunk_size or settings.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP
        
    # ========================================================================
    # FILE VALIDATION
    # ========================================================================
    
    def is_supported_file(self, filename: str) -> bool:
        """
        Check if file type is supported.
        
        Args:
            filename: Name of the file
            
        Returns:
            bool: True if supported, False otherwise
        """
        ext = Path(filename).suffix.lower()
        return ext in self.SUPPORTED_EXTENSIONS
    
    def get_file_type(self, filename: str) -> Optional[str]:
        """
        Get MIME type of file.
        
        Args:
            filename: Name of the file
            
        Returns:
            str: MIME type or None if unsupported
        """
        ext = Path(filename).suffix.lower()
        return self.SUPPORTED_EXTENSIONS.get(ext)
    
    # ========================================================================
    # TEXT EXTRACTION
    # ========================================================================
    
    def extract_text(self, file_path: str, file_type: str) -> Tuple[str, Dict[str, Any]]:
        """
        Extract text from document based on file type.
        
        Args:
            file_path: Path to the file
            file_type: MIME type of the file
            
        Returns:
            Tuple[str, Dict]: Extracted text and metadata
            
        Raises:
            ValueError: If file type is not supported
            Exception: If extraction fails
        """
        ext = Path(file_path).suffix.lower()
        
        if ext == '.pdf':
            return self._extract_from_pdf(file_path)
        elif ext == '.docx':
            return self._extract_from_docx(file_path)
        elif ext == '.txt':
            return self._extract_from_txt(file_path)
        elif ext == '.md':
            return self._extract_from_markdown(file_path)
        else:
            raise ValueError(f"Unsupported file type: {ext}")
    
    def _extract_from_pdf(self, file_path: str) -> Tuple[str, Dict[str, Any]]:
        """
        Extract text from PDF file.
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            Tuple[str, Dict]: Extracted text and metadata
        """
        if not PYPDF2_AVAILABLE:
            raise RuntimeError("PyPDF2 is not installed. Cannot process PDF files.")
        
        try:
            text_content = []
            metadata = {"pages": [], "page_count": 0}
            
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                metadata["page_count"] = len(pdf_reader.pages)
                
                # Extract PDF metadata
                if pdf_reader.metadata:
                    metadata["title"] = pdf_reader.metadata.get("/Title", "")
                    metadata["author"] = pdf_reader.metadata.get("/Author", "")
                    metadata["subject"] = pdf_reader.metadata.get("/Subject", "")
                
                # Extract text from each page
                for page_num, page in enumerate(pdf_reader.pages, start=1):
                    try:
                        page_text = page.extract_text()
                        if page_text.strip():
                            text_content.append(page_text)
                            metadata["pages"].append({
                                "page_number": page_num,
                                "char_count": len(page_text)
                            })
                    except Exception as e:
                        logger.warning(f"Error extracting text from page {page_num}: {str(e)}")
                        continue
            
            full_text = "\n\n".join(text_content)
            return full_text, metadata
            
        except Exception as e:
            logger.error(f"Error processing PDF {file_path}: {str(e)}")
            raise
    
    def _extract_from_docx(self, file_path: str) -> Tuple[str, Dict[str, Any]]:
        """
        Extract text from DOCX file.
        
        Args:
            file_path: Path to DOCX file
            
        Returns:
            Tuple[str, Dict]: Extracted text and metadata
        """
        if not DOCX_AVAILABLE:
            raise RuntimeError("python-docx is not installed. Cannot process DOCX files.")
        
        try:
            doc = docx.Document(file_path)
            
            # Extract paragraphs
            paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
            
            # Extract tables
            tables_text = []
            for table in doc.tables:
                for row in table.rows:
                    row_text = [cell.text for cell in row.cells]
                    tables_text.append(" | ".join(row_text))
            
            # Combine text
            full_text = "\n\n".join(paragraphs)
            if tables_text:
                full_text += "\n\n" + "\n".join(tables_text)
            
            metadata = {
                "paragraph_count": len(paragraphs),
                "table_count": len(doc.tables),
                "section_count": len(doc.sections)
            }
            
            # Extract core properties if available
            try:
                if hasattr(doc.core_properties, 'title'):
                    metadata["title"] = doc.core_properties.title
                if hasattr(doc.core_properties, 'author'):
                    metadata["author"] = doc.core_properties.author
            except:
                pass
            
            return full_text, metadata
            
        except Exception as e:
            logger.error(f"Error processing DOCX {file_path}: {str(e)}")
            raise
    
    def _extract_from_txt(self, file_path: str) -> Tuple[str, Dict[str, Any]]:
        """
        Extract text from TXT file.
        
        Args:
            file_path: Path to TXT file
            
        Returns:
            Tuple[str, Dict]: Extracted text and metadata
        """
        try:
            # Try different encodings
            encodings = ['utf-8', 'utf-16', 'latin-1', 'cp1252']
            text = None
            used_encoding = None
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as file:
                        text = file.read()
                        used_encoding = encoding
                        break
                except UnicodeDecodeError:
                    continue
            
            if text is None:
                raise ValueError("Unable to decode text file with supported encodings")
            
            metadata = {
                "encoding": used_encoding,
                "line_count": len(text.splitlines()),
                "char_count": len(text)
            }
            
            return text, metadata
            
        except Exception as e:
            logger.error(f"Error processing TXT {file_path}: {str(e)}")
            raise
    
    def _extract_from_markdown(self, file_path: str) -> Tuple[str, Dict[str, Any]]:
        """
        Extract text from Markdown file.
        
        Args:
            file_path: Path to MD file
            
        Returns:
            Tuple[str, Dict]: Extracted text and metadata
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                text = file.read()
            
            # Extract headers for metadata
            headers = re.findall(r'^#+\s+(.+)$', text, re.MULTILINE)
            
            metadata = {
                "encoding": "utf-8",
                "line_count": len(text.splitlines()),
                "header_count": len(headers),
                "headers": headers[:10]  # First 10 headers
            }
            
            return text, metadata
            
        except Exception as e:
            logger.error(f"Error processing MD {file_path}: {str(e)}")
            raise
    
    # ========================================================================
    # TEXT CHUNKING
    # ========================================================================
    
    def chunk_text(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Split text into chunks with overlap.
        
        Args:
            text: Text to chunk
            metadata: Optional metadata to include with each chunk
            
        Returns:
            List[Dict]: List of chunks with metadata
        """
        if not text or not text.strip():
            return []
        
        # Clean text
        text = self._clean_text(text)
        
        chunks = []
        start = 0
        chunk_index = 0
        
        while start < len(text):
            # Calculate end position
            end = start + self.chunk_size
            
            # If not at the end, try to break at sentence boundary
            if end < len(text):
                # Look for sentence endings
                sentence_end = self._find_sentence_boundary(text, end, start)
                if sentence_end > start:
                    end = sentence_end
            
            # Extract chunk
            chunk_text = text[start:end].strip()
            
            if chunk_text:
                chunk_data = {
                    "content": chunk_text,
                    "chunk_index": chunk_index,
                    "start_char": start,
                    "end_char": end,
                    "char_count": len(chunk_text)
                }
                
                # Add metadata if provided
                if metadata:
                    chunk_data["metadata"] = metadata.copy()
                
                chunks.append(chunk_data)
                chunk_index += 1
            
            # Move to next chunk with overlap
            start = end - self.chunk_overlap
            
            # Prevent infinite loop
            if start >= len(text):
                break
        
        logger.info(f"Created {len(chunks)} chunks from {len(text)} characters")
        return chunks
    
    def _find_sentence_boundary(self, text: str, preferred_end: int, start: int) -> int:
        """
        Find nearest sentence boundary before preferred_end.
        
        Args:
            text: Text to search
            preferred_end: Preferred end position
            start: Start position
            
        Returns:
            int: Position of sentence boundary
        """
        # Look backwards from preferred_end for sentence endings
        search_window = 100  # characters to look back
        search_start = max(start, preferred_end - search_window)
        search_text = text[search_start:preferred_end]
        
        # Sentence endings
        sentence_endings = ['. ', '! ', '? ', '.\n', '!\n', '?\n']
        
        best_pos = -1
        for ending in sentence_endings:
            pos = search_text.rfind(ending)
            if pos > best_pos:
                best_pos = pos + len(ending)
        
        if best_pos > 0:
            return search_start + best_pos
        
        # If no sentence boundary found, look for paragraph break
        para_break = search_text.rfind('\n\n')
        if para_break > 0:
            return search_start + para_break + 2
        
        # Otherwise, return preferred_end
        return preferred_end
    
    def _clean_text(self, text: str) -> str:
        """
        Clean and normalize text.
        
        Args:
            text: Text to clean
            
        Returns:
            str: Cleaned text
        """
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove excessive newlines (keep paragraph breaks)
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        # Trim
        text = text.strip()
        
        return text
    
    # ========================================================================
    # FULL PROCESSING PIPELINE
    # ========================================================================
    
    def process_document(
        self,
        file_path: str,
        source_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Full document processing pipeline: extract text and create chunks.
        
        Args:
            file_path: Path to document file
            source_metadata: Additional metadata about the source
            
        Returns:
            Dict: Processing results with chunks and metadata
        """
        try:
            # Validate file exists
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            
            # Get file info
            filename = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            file_type = self.get_file_type(filename)
            
            if not file_type:
                raise ValueError(f"Unsupported file type: {filename}")
            
            logger.info(f"Processing document: {filename} ({file_size} bytes)")
            
            # Extract text
            text, extraction_metadata = self.extract_text(file_path, file_type)
            
            if not text or not text.strip():
                raise ValueError("No text could be extracted from document")
            
            # Prepare metadata for chunks
            chunk_metadata = {
                "filename": filename,
                "file_type": file_type,
                "file_size": file_size,
                **extraction_metadata
            }
            
            if source_metadata:
                chunk_metadata.update(source_metadata)
            
            # Create chunks
            chunks = self.chunk_text(text, chunk_metadata)
            
            result = {
                "success": True,
                "filename": filename,
                "file_size": file_size,
                "file_type": file_type,
                "text_length": len(text),
                "chunk_count": len(chunks),
                "chunks": chunks,
                "metadata": extraction_metadata
            }
            
            logger.info(
                f"Successfully processed {filename}: "
                f"{len(text)} chars -> {len(chunks)} chunks"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing document {file_path}: {str(e)}")
            return {
                "success": False,
                "filename": os.path.basename(file_path) if os.path.exists(file_path) else "unknown",
                "error": str(e),
                "chunk_count": 0,
                "chunks": []
            }


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def validate_file_size(file_size: int, max_size_mb: int = None) -> bool:
    """
    Validate file size is within limits.
    
    Args:
        file_size: File size in bytes
        max_size_mb: Maximum allowed size in MB
        
    Returns:
        bool: True if valid, False otherwise
    """
    max_size = (max_size_mb or settings.MAX_FILE_SIZE_MB) * 1024 * 1024
    return file_size <= max_size


def get_file_extension(filename: str) -> str:
    """
    Get file extension from filename.
    
    Args:
        filename: Name of file
        
    Returns:
        str: File extension (lowercase, with dot)
    """
    return Path(filename).suffix.lower()


def is_allowed_file_type(filename: str) -> bool:
    """
    Check if file type is allowed.
    
    Args:
        filename: Name of file
        
    Returns:
        bool: True if allowed, False otherwise
    """
    ext = get_file_extension(filename)
    return ext in DocumentProcessor.SUPPORTED_EXTENSIONS

