import logging
import os
from graph_rag.graph_store import GraphStoreManager
from graph_rag.ingestion import CodeIngestion
from graph_rag.query_engine import GraphQueryEngine

logger = logging.getLogger("graph_service")

class GraphService:
    def __init__(self):
        self.graph_manager = None
        self.query_engine = None
        self.ingestion = None
        self.is_connected = False

    def connect(self, uri, user, password, hf_token, model_name):
        """Initializes components."""
        try:
            self.graph_manager = GraphStoreManager(uri, user, password)
            self.graph_manager.connect()
            
            # Check for isolated GraphRAG credentials
            isolated_key = os.getenv("GRAPHRAG_HF_KEY")
            if isolated_key:
                logger.info("Using isolated GRAPHRAG_HF_KEY from environment instead of main tool credentials.")
                token_to_use = isolated_key
            else:
                logger.info("Using shared HuggingFace credentials from main tool.")
                token_to_use = hf_token
            
            self.ingestion = CodeIngestion(self.graph_manager)
            self.query_engine = GraphQueryEngine(self.graph_manager, token_to_use, model_name)
            
            self.is_connected = True
            logger.info("GraphService connected successfully.")
            return True, "Connected to Code Intelligence Graph."
        except Exception as e:
            logger.error(f"GraphService connection failed: {e}")
            return False, str(e)

    def update_credentials(self, hf_token, model_name=None):
        """Update HuggingFace credentials for query engine without reconnecting to Neo4j."""
        if not self.is_connected:
            return False, "Not connected to Neo4j."
        
        try:
            if model_name:
                self.query_engine.model_name = model_name
            self.query_engine.hf_token = hf_token
            logger.info("Updated GraphRAG credentials successfully.")
            return True, "Credentials updated."
        except Exception as e:
            logger.error(f"Failed to update credentials: {e}")
            return False, str(e)

    def ingest(self, repo_url, repo_path, progress_callback=None):
        if not self.is_connected:
            return False, "Not connected to Neo4j."
            
        try:
            repo_name = repo_url.rstrip('/').split('/')[-1]
            if progress_callback:
                progress_callback("Clearing existing graph data...")
            self.graph_manager.clear_graph_for_repo(repo_name)
            if progress_callback:
                progress_callback("Parsing code files with Tree-sitter...")
            self.ingestion.ingest_repo(repo_path, repo_name, progress_callback)
            return True, "Ingestion Complete"
        except Exception as e:
            return False, str(e)

    def query(self, question):
        if not self.is_connected:
            return "Error: Not connected to Neo4j."
            
        try:
            return self.query_engine.query(question)
        except Exception as e:
            return f"Error executing query: {str(e)}"
    
    def analyze_changes(self, repo_path, repo_url, progress_callback=None):
        """
        Analyze repository for changes and update GraphRAG incrementally.
        
        Args:
            repo_path: Local path to repository
            repo_url: Repository URL
            progress_callback: Optional progress callback
            
        Returns:
            Dictionary with analysis results
        """
        if not self.is_connected:
            return {"status": "error", "error": "Not connected to Neo4j."}
        
        try:
            from graph_rag.graphrag_change_detector import GraphRAGChangeDetector
            
            change_detector = GraphRAGChangeDetector(self.graph_manager)
            result = change_detector.analyze_and_update(
                repo_path, 
                repo_url, 
                progress_callback
            )
            
            return result
        except Exception as e:
            logger.error(f"Change analysis failed: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

