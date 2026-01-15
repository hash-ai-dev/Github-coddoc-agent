"""
Vector Store Module
Manages ChromaDB vector database for code embeddings and semantic search.
"""

import logging
from typing import List, Dict, Optional, Any
from pathlib import Path
import chromadb
from chromadb.config import Settings
from dataclasses import dataclass
from .doc_formatter import DocFormatter

logger = logging.getLogger(__name__)


@dataclass
class CodeChunk:
    """Represents a chunk of code with metadata."""
    id: str
    content: str
    file_path: str
    function_name: Optional[str]
    start_line: int
    end_line: int
    embedding: Optional[List[float]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            'file_path': self.file_path,
            'function_name': self.function_name or '',
            'start_line': self.start_line,
            'end_line': self.end_line
        }


class VectorStore:
    """Manages vector database for code embeddings."""
    
    def __init__(self, persist_directory: str = "backend/data/vector_db"):
        """
        Initialize the vector store.
        
        Args:
            persist_directory: Directory to persist ChromaDB data
        """
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB client with persistent storage
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        logger.info(f"Initialized VectorStore at {self.persist_directory}")
    
    def _get_collection_name(self, repo_url: str) -> str:
        """Generate a safe collection name from repository URL."""
        # Replace special characters with underscores
        safe_name = repo_url.replace('https://', '').replace('http://', '')
        safe_name = safe_name.replace('/', '_').replace('.', '_').replace(':', '_')
        return f"repo_{safe_name}"
    
    def create_collection(self, repo_url: str) -> chromadb.Collection:
        """
        Create or get a collection for a repository.
        
        Args:
            repo_url: Repository URL
            
        Returns:
            ChromaDB collection
        """
        collection_name = self._get_collection_name(repo_url)
        
        try:
            collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"repo_url": repo_url}
            )
            logger.info(f"Created/retrieved collection: {collection_name}")
            return collection
        except Exception as e:
            logger.error(f"Failed to create collection: {e}")
            raise
    
    def add_code_chunks(self, repo_url: str, chunks: List[CodeChunk], commit_hash: str):
        """
        Add code chunks to the vector store.
        
        Args:
            repo_url: Repository URL
            chunks: List of code chunks with embeddings
            commit_hash: Git commit hash for this version
        """
        if not chunks:
            logger.warning("No chunks to add")
            return
        
        collection = self.create_collection(repo_url)
        
        # Prepare data for ChromaDB
        ids = [chunk.id for chunk in chunks]
        documents = [chunk.content for chunk in chunks]
        embeddings = [chunk.embedding for chunk in chunks]
        metadatas = [
            {**chunk.to_dict(), 'commit_hash': commit_hash}
            for chunk in chunks
        ]
        
        try:
            collection.add(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas
            )
            logger.info(f"Added {len(chunks)} chunks to collection")
        except Exception as e:
            logger.error(f"Failed to add chunks: {e}")
            raise
    
    def search_similar(
        self, 
        repo_url: str, 
        query_embedding: List[float], 
        top_k: int = 5,
        file_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar code chunks using vector similarity.
        
        Args:
            repo_url: Repository URL
            query_embedding: Query embedding vector
            top_k: Number of results to return
            file_filter: Optional file path to filter results
            
        Returns:
            List of similar code chunks with metadata
        """
        collection_name = self._get_collection_name(repo_url)
        
        try:
            collection = self.client.get_collection(collection_name)
        except Exception:
            logger.warning(f"Collection not found: {collection_name}")
            return []
        
        # Build where clause for filtering
        where = {}
        if file_filter:
            where['file_path'] = file_filter
        
        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where if where else None
            )
            
            # Format results
            similar_chunks = []
            if results['ids'] and len(results['ids'][0]) > 0:
                for i in range(len(results['ids'][0])):
                    similar_chunks.append({
                        'id': results['ids'][0][i],
                        'content': results['documents'][0][i],
                        'metadata': results['metadatas'][0][i],
                        'distance': results['distances'][0][i] if 'distances' in results else None
                    })
            
            return similar_chunks
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    def get_by_file(self, repo_url: str, file_path: str) -> List[Dict[str, Any]]:
        """
        Get all chunks for a specific file.
        
        Args:
            repo_url: Repository URL
            file_path: File path to retrieve
            
        Returns:
            List of code chunks for the file
        """
        collection_name = self._get_collection_name(repo_url)
        
        try:
            collection = self.client.get_collection(collection_name)
        except Exception:
            logger.warning(f"Collection not found: {collection_name}")
            return []
        
        try:
            results = collection.get(
                where={'file_path': file_path}
            )
            
            chunks = []
            if results['ids']:
                for i in range(len(results['ids'])):
                    chunks.append({
                        'id': results['ids'][i],
                        'content': results['documents'][i],
                        'metadata': results['metadatas'][i]
                    })
            
            return chunks
        except Exception as e:
            logger.error(f"Failed to get chunks by file: {e}")
            return []
    
    def delete_by_file(self, repo_url: str, file_path: str):
        """
        Delete all chunks for a specific file.
        
        Args:
            repo_url: Repository URL
            file_path: File path to delete
        """
        collection_name = self._get_collection_name(repo_url)
        
        try:
            collection = self.client.get_collection(collection_name)
            collection.delete(where={'file_path': file_path})
            logger.info(f"Deleted chunks for file: {file_path}")
        except Exception as e:
            logger.error(f"Failed to delete chunks: {e}")
    
    def update_chunks(self, repo_url: str, chunks: List[CodeChunk], commit_hash: str):
        """
        Update chunks (delete old, add new).
        
        Args:
            repo_url: Repository URL
            chunks: New code chunks
            commit_hash: Git commit hash
        """
        if not chunks:
            return
        
        # Get unique file paths
        file_paths = set(chunk.file_path for chunk in chunks)
        
        # Delete old chunks for these files
        for file_path in file_paths:
            self.delete_by_file(repo_url, file_path)
        
        # Add new chunks
        self.add_code_chunks(repo_url, chunks, commit_hash)
    
    def get_metadata(self, repo_url: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a repository collection.
        
        Args:
            repo_url: Repository URL
            
        Returns:
            Collection metadata or None
        """
        collection_name = self._get_collection_name(repo_url)
        
        try:
            collection = self.client.get_collection(collection_name)
            count = collection.count()
            
            # Get latest commit hash
            results = collection.get(limit=1)
            commit_hash = None
            if results['metadatas'] and len(results['metadatas']) > 0:
                commit_hash = results['metadatas'][0].get('commit_hash')
            
            return {
                'repo_url': repo_url,
                'chunk_count': count,
                'last_commit': commit_hash
            }
        except Exception:
            return None
    
    def delete_collection(self, repo_url: str):
        """
        Delete entire collection for a repository.
        
        Args:
            repo_url: Repository URL
        """
        collection_name = self._get_collection_name(repo_url)
        
        try:
            self.client.delete_collection(collection_name)
            logger.info(f"Deleted collection: {collection_name}")
        except Exception as e:
            logger.error(f"Failed to delete collection: {e}")
    
    def list_collections(self) -> List[Dict[str, Any]]:
        """
        List all repository collections.
        
        Returns:
            List of collection metadata
        """
        try:
            collections = self.client.list_collections()
            result = []
            
            for collection in collections:
                metadata = collection.metadata or {}
                repo_url = metadata.get('repo_url', 'unknown')
                
                result.append({
                    'name': collection.name,
                    'repo_url': repo_url,
                    'chunk_count': collection.count()
                })
            
            return result
        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            return []
            
    def save_documentation(self, repo_url: str, docs: Dict[str, Any]):
        """
        Save the generated documentation to disk.
        
        Args:
            repo_url: Repository URL
            docs: Dictionary containing overview and file documentation
        """
        collection_name = self._get_collection_name(repo_url)
        doc_path = self.persist_directory / f"{collection_name}_docs.json"
        
        # Use DocFormatter for proper JSON encoding and special character handling
        success = DocFormatter.save_to_json(docs, str(doc_path))
        if not success:
            logger.error(f"Failed to save documentation for {repo_url}")

    def load_documentation(self, repo_url: str) -> Optional[Dict[str, Any]]:
        """
        Load cached documentation from disk.
        
        Args:
            repo_url: Repository URL
            
        Returns:
            Documentation dictionary or None
        """
        collection_name = self._get_collection_name(repo_url)
        doc_path = self.persist_directory / f"{collection_name}_docs.json"
        
        if not doc_path.exists():
            return None
            
        # Use DocFormatter for proper JSON decoding
        docs = DocFormatter.load_from_json(str(doc_path))
        return docs if docs else None
