"""
GraphRAG Change Detector Module
Detects repository changes and incrementally updates the GraphRAG knowledge graph.
"""

import logging
import os
from typing import Optional, Callable
from pathlib import Path
from core.change_detector import ChangeDetector, ChangeSet
from graph_rag.ingestion import CodeIngestion
from graph_rag.graph_store import GraphStoreManager

logger = logging.getLogger("graphrag_change_detector")


class GraphRAGChangeDetector:
    """Detects changes and updates GraphRAG incrementally."""
    
    def __init__(self, graph_manager: GraphStoreManager):
        """
        Initialize the GraphRAG change detector.
        
        Args:
            graph_manager: GraphStoreManager instance
        """
        self.graph_manager = graph_manager
        self.ingestion = CodeIngestion(graph_manager)
    
    def get_last_synced_commit(self, repo_url: str) -> Optional[str]:
        """
        Get the last synced commit SHA for a repository from Neo4j.
        
        Args:
            repo_url: Repository URL
            
        Returns:
            Last commit SHA or None if never synced
        """
        try:
            driver = self.graph_manager.get_driver()
            with driver.session() as session:
                result = session.run("""
                    MATCH (r:Repository {repo_url: $repo_url})
                    RETURN r.last_commit_sha as sha
                """, repo_url=repo_url)
                
                record = result.single()
                if record and record['sha']:
                    logger.info(f"Last synced commit for {repo_url}: {record['sha']}")
                    return record['sha']
                
                logger.info(f"No previous sync found for {repo_url}")
                return None
        except Exception as e:
            logger.error(f"Failed to get last synced commit: {e}")
            return None
    
    def update_last_synced_commit(self, repo_url: str, commit_sha: str, repo_name: str):
        """
        Update the last synced commit SHA in Neo4j.
        
        Args:
            repo_url: Repository URL
            commit_sha: Current commit SHA
            repo_name: Repository name
        """
        try:
            driver = self.graph_manager.get_driver()
            with driver.session() as session:
                session.run("""
                    MERGE (r:Repository {repo_url: $repo_url})
                    SET r.repo_name = $repo_name,
                        r.last_commit_sha = $commit_sha,
                        r.last_synced = timestamp()
                """, repo_url=repo_url, repo_name=repo_name, commit_sha=commit_sha)
                
            logger.info(f"Updated last synced commit to {commit_sha}")
        except Exception as e:
            logger.error(f"Failed to update last synced commit: {e}")
    
    def analyze_and_update(
        self, 
        repo_path: str, 
        repo_url: str,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> dict:
        """
        Analyze repository for changes and update GraphRAG incrementally.
        
        Args:
            repo_path: Local path to repository
            repo_url: Repository URL
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dictionary with analysis results
        """
        def progress(msg: str):
            logger.info(msg)
            if progress_callback:
                progress_callback(msg)
        
        try:
            progress("Initializing change detection...")
            
            # Initialize change detector
            change_detector = ChangeDetector(repo_path)
            current_commit = change_detector.get_current_commit()
            
            # Get last synced commit from Neo4j
            last_commit = self.get_last_synced_commit(repo_url)
            
            # Detect changes
            progress("Analyzing repository changes...")
            changeset = change_detector.get_changed_files(
                previous_commit=last_commit,
                current_commit=current_commit
            )
            
            repo_name = repo_url.rstrip('/').split('/')[-1].replace('.git', '')
            
            # Handle changes
            if not changeset.has_changes:
                # Check if database is empty - if so, force full ingestion
                # Note: The ingestion stores repo_url in the repo_name field
                driver = self.graph_manager.get_driver()
                with driver.session() as session:
                    result = session.run(f"""
                        MATCH (n {{repo_name: $repo_url}})
                        RETURN count(n) as count
                    """, repo_url=repo_url)
                    entity_count = result.single()['count']
                
                if entity_count == 0:
                    progress("No changes detected, but database is empty. Performing full ingestion...")
                    logger.info(f"Database is empty for {repo_url}. Forcing full ingestion.")
                    
                    # Treat all files as new
                    changeset = change_detector._get_all_files_as_added(current_commit)
                    
                    if not changeset.has_changes:
                        progress("No code files found in repository.")
                        return {
                            'status': 'no_files',
                            'current_commit': current_commit,
                            'message': 'No parseable code files found in repository'
                        }
                else:
                    progress("No changes detected. Repository is up to date.")
                    return {
                        'status': 'up_to_date',
                        'current_commit': current_commit,
                        'previous_commit': last_commit,
                        'changes': 0
                    }
            
            progress(f"Found {len(changeset.added_files)} new files, "
                    f"{len(changeset.modified_files)} modified files, "
                    f"{len(changeset.deleted_files)} deleted files")
            
            # Clear old data for deleted and modified files
            if changeset.deleted_files or changeset.modified_files:
                progress("Removing outdated graph data...")
                files_to_remove = changeset.deleted_files + changeset.modified_files
                self._remove_files_from_graph(repo_url, files_to_remove)
            
            # Ingest new and modified files
            if changeset.all_changed_files:
                progress(f"Ingesting {len(changeset.all_changed_files)} changed files into knowledge graph...")
                self._ingest_changed_files(
                    repo_path, 
                    repo_url,  # Use repo_url to match database schema
                    changeset.all_changed_files,
                    progress_callback
                )
            
            # Update last synced commit
            self.update_last_synced_commit(repo_url, current_commit, repo_name)
            
            progress("GraphRAG update complete!")
            
            return {
                'status': 'updated',
                'current_commit': current_commit,
                'previous_commit': last_commit,
                'added': len(changeset.added_files),
                'modified': len(changeset.modified_files),
                'deleted': len(changeset.deleted_files),
                'total_changes': len(changeset.added_files) + len(changeset.modified_files) + len(changeset.deleted_files)
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze and update: {e}", exc_info=True)
            progress(f"Error: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _remove_files_from_graph(self, repo_name: str, file_paths: list):
        """
        Remove entities from specific files in the graph.
        
        Args:
            repo_name: Repository name
            file_paths: List of file paths to remove
        """
        try:
            driver = self.graph_manager.get_driver()
            with driver.session() as session:
                for file_path in file_paths:
                    session.run("""
                        MATCH (n {repo_name: $repo_name, file_path: $file_path})
                        DETACH DELETE n
                    """, repo_name=repo_name, file_path=file_path)
                    logger.info(f"Removed graph data for {file_path}")
        except Exception as e:
            logger.error(f"Failed to remove files from graph: {e}")
    
    def _ingest_changed_files(
        self, 
        repo_path: str, 
        repo_name: str, 
        file_paths: list,
        progress_callback: Optional[Callable[[str], None]] = None
    ):
        """
        Ingest only the changed files into the graph.
        
        Args:
            repo_path: Local repository path
            repo_name: Repository name
            file_paths: List of file paths to ingest
            progress_callback: Optional progress callback
        """
        try:
            # Use the existing ingestion logic but filter for specific files
            self.ingestion.ingest_files(
                repo_path, 
                repo_name, 
                file_paths,
                progress_callback
            )
        except Exception as e:
            logger.error(f"Failed to ingest changed files: {e}")
            raise
