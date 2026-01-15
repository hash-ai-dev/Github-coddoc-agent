"""
Code Embedder Module
Generates embeddings for code using sentence-transformers.
"""

import logging
from typing import List, Dict, Optional
import hashlib
from sentence_transformers import SentenceTransformer
import numpy as np

logger = logging.getLogger(__name__)


class CodeEmbedder:
    """Generates embeddings for code chunks using sentence-transformers."""
    
    # Maximum tokens per chunk (for all-MiniLM-L6-v2)
    MAX_CHUNK_SIZE = 512
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize the code embedder.
        
        Args:
            model_name: Sentence-transformers model name
        """
        self.model_name = model_name
        logger.info(f"Loading embedding model: {model_name}")
        
        try:
            self.model = SentenceTransformer(model_name)
            logger.info("Embedding model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise
    
    def _generate_chunk_id(self, file_path: str, start_line: int, end_line: int) -> str:
        """Generate unique ID for a code chunk."""
        content = f"{file_path}:{start_line}:{end_line}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def chunk_code(self, file_content: str, file_path: str, language: str = "python") -> List[Dict]:
        """
        Chunk code intelligently based on structure.
        
        Args:
            file_content: Full file content
            file_path: Path to the file
            language: Programming language
            
        Returns:
            List of code chunks with metadata
        """
        chunks = []
        lines = file_content.split('\n')
        
        # Simple chunking strategy: by function/class or fixed size
        current_chunk = []
        current_start = 1
        function_name = None
        
        for i, line in enumerate(lines, start=1):
            current_chunk.append(line)
            
            # Detect function/class definitions (Python-specific for now)
            if language == "python":
                stripped = line.strip()
                if stripped.startswith('def ') or stripped.startswith('class '):
                    # Extract function/class name
                    parts = stripped.split('(')[0].split()
                    if len(parts) >= 2:
                        function_name = parts[1].rstrip(':')
                
                # End of function/class (dedent or empty line after content)
                if function_name and (not line.strip() or (line and not line[0].isspace())):
                    if len(current_chunk) > 1:
                        chunk_content = '\n'.join(current_chunk[:-1])
                        if chunk_content.strip():
                            chunks.append({
                                'id': self._generate_chunk_id(file_path, current_start, i-1),
                                'content': chunk_content,
                                'file_path': file_path,
                                'function_name': function_name,
                                'start_line': current_start,
                                'end_line': i - 1
                            })
                        current_chunk = [line]
                        current_start = i
                        function_name = None
            
            # Fallback: chunk by size
            if len('\n'.join(current_chunk)) > self.MAX_CHUNK_SIZE * 4:  # Rough estimate
                chunk_content = '\n'.join(current_chunk)
                chunks.append({
                    'id': self._generate_chunk_id(file_path, current_start, i),
                    'content': chunk_content,
                    'file_path': file_path,
                    'function_name': function_name,
                    'start_line': current_start,
                    'end_line': i
                })
                current_chunk = []
                current_start = i + 1
                function_name = None
        
        # Add remaining chunk
        if current_chunk:
            chunk_content = '\n'.join(current_chunk)
            if chunk_content.strip():
                chunks.append({
                    'id': self._generate_chunk_id(file_path, current_start, len(lines)),
                    'content': chunk_content,
                    'file_path': file_path,
                    'function_name': function_name,
                    'start_line': current_start,
                    'end_line': len(lines)
                })
        
        logger.info(f"Created {len(chunks)} chunks for {file_path}")
        return chunks
    
    def embed_chunks(self, chunks: List[Dict]) -> List[Dict]:
        """
        Generate embeddings for code chunks.
        
        Args:
            chunks: List of code chunks
            
        Returns:
            Chunks with embeddings added
        """
        if not chunks:
            return []
        
        try:
            # Extract content for embedding
            contents = [chunk['content'] for chunk in chunks]
            
            # Generate embeddings in batch
            logger.info(f"Generating embeddings for {len(contents)} chunks...")
            embeddings = self.model.encode(
                contents,
                show_progress_bar=False,
                convert_to_numpy=True
            )
            
            # Add embeddings to chunks
            for i, chunk in enumerate(chunks):
                chunk['embedding'] = embeddings[i].tolist()
            
            logger.info(f"Generated {len(embeddings)} embeddings")
            return chunks
            
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise
    
    def embed_query(self, query: str) -> List[float]:
        """
        Generate embedding for a query string.
        
        Args:
            query: Query text
            
        Returns:
            Query embedding vector
        """
        try:
            embedding = self.model.encode(query, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Failed to embed query: {e}")
            raise
    
    def embed_file(self, file_content: str, file_path: str, language: str = "python") -> List[Dict]:
        """
        Convenience method to chunk and embed a file in one step.
        
        Args:
            file_content: Full file content
            file_path: Path to the file
            language: Programming language
            
        Returns:
            List of chunks with embeddings
        """
        chunks = self.chunk_code(file_content, file_path, language)
        return self.embed_chunks(chunks)
