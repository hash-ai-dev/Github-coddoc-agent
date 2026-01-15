"""
LangGraph Workflow Module
Orchestrates the documentation generation workflow using LangGraph.
"""

import logging
import os
from typing import Dict, TypedDict, Annotated, Optional
from langgraph.graph import StateGraph, END
import operator

from .repo_analyzer import RepoAnalyzer
from .doc_generator import DocGenerator
from .confluence_uploader import ConfluenceUploader
from .vector_store import VectorStore, CodeChunk
from .embedder import CodeEmbedder
from .change_detector import ChangeDetector, ChangeSet

logger = logging.getLogger(__name__)


class WorkflowState(TypedDict):
    """State object passed between workflow nodes."""
    repo_url: str
    github_token: str
    hf_api_key: str
    model_name: str
    confluence_url: str
    confluence_token: str
    confluence_space: str
    
    # Progress tracking
    status: str
    progress: int
    current_file: str
    
    # Data
    repo_path: str
    analysis: Dict
    important_files: list
    overview_doc: str
    file_docs: Dict[str, str]
    confluence_page: Dict
    
    # RAG-specific fields
    use_rag: bool  # Whether to use RAG features
    last_commit: Optional[str]  # Last analyzed commit hash
    current_commit: Optional[str]  # Current commit hash
    changes: Optional[ChangeSet]  # Detected changes
    is_incremental: bool  # Whether this is an incremental update
    
    # Error handling
    error: str


class DocumentationWorkflow:
    """LangGraph workflow for automated documentation generation."""
    
    def __init__(self, progress_callback=None, status_callback=None, vector_store: VectorStore = None):
        """
        Initialize the workflow.
        
        Args:
            progress_callback: Optional callback function for progress updates
                              Signature: callback(status: str, progress: int, file: str)
            status_callback: Optional callback for status/preview updates
                            Signature: callback(message: str, type: str)
            vector_store: Optional VectorStore instance for RAG features
        """
        self.status_callback = status_callback
        self.progress_callback = progress_callback
        self.vector_store = vector_store
        self.embedder = CodeEmbedder() if vector_store else None
        self.workflow = self._build_workflow()
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow."""
        
        # Define the workflow graph
        workflow = StateGraph(WorkflowState)
        
        # Add nodes
        workflow.add_node("check_cache", self._check_cache)
        workflow.add_node("detect_changes", self._detect_changes)
        workflow.add_node("clone_repo", self._clone_repository)
        workflow.add_node("analyze_code", self._analyze_code)
        workflow.add_node("generate_overview", self._generate_overview)
        workflow.add_node("generate_file_docs", self._generate_file_docs)
        workflow.add_node("create_embeddings", self._create_embeddings)
        
        # Define edges (workflow flow with RAG support)
        workflow.set_entry_point("check_cache")
        
        # Cache check branches
        workflow.add_conditional_edges(
            "check_cache",
            self._should_use_cache,
            {
                "detect_changes": "detect_changes",  # Has cache, check for changes
                "clone_repo": "clone_repo"  # No cache, do full analysis
            }
        )
        
        # Change detection branches
        workflow.add_conditional_edges(
            "detect_changes",
            self._has_changes,
            {
                "clone_repo": "clone_repo",  # Has changes, re-analyze
                END: END  # No changes, return cached docs
            }
        )
        
        # Standard workflow path
        workflow.add_edge("clone_repo", "analyze_code")
        workflow.add_edge("analyze_code", "generate_overview")
        workflow.add_edge("generate_overview", "generate_file_docs")
        
        # RAG: Create embeddings after doc generation
        workflow.add_conditional_edges(
            "generate_file_docs",
            self._should_create_embeddings,
            {
                "create_embeddings": "create_embeddings",
                END: END
            }
        )
        workflow.add_edge("create_embeddings", END)
        
        return workflow.compile()
    
    def _update_progress(self, state: WorkflowState, status: str, progress: int, current_file: str = ""):
        """Update progress and call callback if provided."""
        state['status'] = status
        state['progress'] = progress
        state['current_file'] = current_file
        
        if self.progress_callback:
            self.progress_callback(status, progress, current_file)
        
        logger.info(f"Progress: {progress}% - {status} - {current_file}")
    
    def _clone_repository(self, state: WorkflowState) -> WorkflowState:
        """Node: Clone the GitHub repository."""
        try:
            self._update_progress(state, "Cloning repository...", 10)
            
            analyzer = RepoAnalyzer(github_token=state.get('github_token'))
            repo_path = analyzer.clone_repository(state['repo_url'])
            
            state['repo_path'] = repo_path
            
            # Get commit hash immediately after cloning
            commit_hash = analyzer.get_current_commit()
            if commit_hash:
                state['current_commit'] = commit_hash
                logger.info(f"Captured commit hash after clone: {commit_hash}")
            else:
                logger.warning("Could not get commit hash after cloning")
            
            self._update_progress(state, "Repository cloned successfully", 20)
            return state
            
        except Exception as e:
            logger.error(f"Failed to clone repository: {e}")
            state['error'] = f"Clone failed: {str(e)}"
            return state
    
    def _analyze_code(self, state: WorkflowState) -> WorkflowState:
        """Node: Analyze the repository structure and code."""
        # Check if previous step failed
        if state.get('error'):
            return state
            
        try:
            logger.info("DEBUG: _analyze_code starting - UPDATED CODE VERSION")
            self._update_progress(state, "Analyzing repository structure...", 25)
            
            # Re-instantiate analyzer with existing repo path
            repo_path = state.get('repo_path')
            if not repo_path:
                raise ValueError("Repository path not found in state")
                
            analyzer = RepoAnalyzer(github_token=state.get('github_token'))
            analyzer.repo_path = repo_path
            
            analysis = analyzer.analyze_structure()
            important_files = analyzer.get_important_files(analysis)
            
            state['analysis'] = analysis
            state['important_files'] = important_files
            
            # Set current_commit for embeddings - get it directly from analyzer
            current_commit = analyzer.get_current_commit()
            if current_commit:
                state['current_commit'] = current_commit
                logger.info(f"Set current_commit in state: {current_commit}")
            else:
                logger.warning("Failed to get current commit hash")
            
            self._update_progress(
                state,
                f"Analyzed {analysis['total_files']} files",
                35
            )
            return state
            
        except Exception as e:
            logger.error(f"Failed to analyze code: {e}")
            state['error'] = f"Analysis failed: {str(e)}"
            return state
    
    def _generate_overview(self, state: WorkflowState) -> WorkflowState:
        """Node: Generate repository overview documentation."""
        # Check if previous step failed
        if state.get('error'):
            return state
            
        try:
            # Skip if incremental and we already have a doc
            if state.get('is_incremental') and state.get('overview_doc'):
                logger.info("Incremental update: Using cached overview documentation")
                self._update_progress(state, "Using cached overview documentation", 50)
                return state

            self._update_progress(state, "Generating overview documentation...", 40)
            
            doc_gen = DocGenerator(
                api_key=state['hf_api_key'],
                model_name=state.get('model_name', 'Qwen/Qwen2.5-Coder-32B-Instruct')
            )
            if self.status_callback:
                doc_gen.set_callback(self.status_callback)
            
            overview = doc_gen.generate_overview(state['analysis'])
            state['overview_doc'] = overview
            
            self._update_progress(state, "Overview documentation generated", 50)
            return state
            
        except Exception as e:
            logger.error(f"Failed to generate overview: {e}")
            state['error'] = f"Overview generation failed: {str(e)}"
            return state
    
    def _generate_file_docs(self, state: WorkflowState) -> WorkflowState:
        """Node: Generate documentation for individual files."""
        # Check if previous step failed
        if state.get('error'):
            return state
            
        important_files = state.get('important_files', [])
        total_files = len(important_files)
        
        try:
            self._update_progress(state, "Generating file documentation...", 60)
            
            if total_files == 0:
                state['file_docs'] = {}
                self._update_progress(state, "No important files to document", 80)
                return state
            
            doc_gen = DocGenerator(
                api_key=state['hf_api_key'],
                model_name=state.get('model_name', 'Qwen/Qwen2.5-Coder-32B-Instruct')
            )
            if self.status_callback:
                doc_gen.set_callback(self.status_callback)
            
            file_docs = state.get('file_docs', {})
            
            # Determine which files to process
            files_to_process = []
            if state.get('is_incremental') and state.get('changes'):
                changed_paths = set(state['changes'].all_changed_files)
                for file_info in important_files:
                    if file_info.get('path') in changed_paths:
                        files_to_process.append(file_info)
                logger.info(f"Incremental update: Processing {len(files_to_process)} changed files")
            else:
                files_to_process = important_files[:10]
                logger.info(f"Full analysis: Processing {len(files_to_process)} files")

            for idx, file_info in enumerate(files_to_process):
                file_name = file_info.get('name', 'Unknown')
                file_path = file_info.get('path', file_name)
                
                # Update progress
                progress = 60 + int((idx / len(files_to_process)) * 20)
                self._update_progress(
                    state,
                    f"Generating documentation for {file_name}...",
                    progress,
                    file_name
                )
                
                # Generate documentation
                file_doc = doc_gen.generate_file_documentation(file_info)
                if file_doc:
                    file_docs[file_path] = file_doc
                else:
                    logger.info(f"Skipped documentation for {file_name} (no content or not needed)")
            
            # Remove deleted files from docs
            if state.get('is_incremental') and state.get('changes'):
                for deleted_file in state['changes'].deleted_files:
                    if deleted_file in file_docs:
                        del file_docs[deleted_file]
                        logger.info(f"Removed documentation for deleted file: {deleted_file}")

            state['file_docs'] = file_docs
            self._update_progress(state, "File documentation generated", 80)
            return state
            
        except Exception as e:
            logger.error(f"Failed to generate file docs: {e}")
            state['error'] = f"File documentation failed: {str(e)}"
            return state
    
    # ===== RAG Workflow Nodes =====
    
    def _check_cache(self, state: WorkflowState) -> WorkflowState:
        """Check if repository is cached in vector store."""
        if not self.vector_store or not state.get('use_rag', True):
            # RAG disabled, skip cache
            state['last_commit'] = None
            state['is_incremental'] = False
            return state
        
        try:
            repo_url = state['repo_url']
            metadata = self.vector_store.get_metadata(repo_url)
            
            if metadata and metadata.get('last_commit'):
                logger.info(f"Found cached data for {repo_url}")
                state['last_commit'] = metadata['last_commit']
                
                # Load cached documentation
                cached_docs = self.vector_store.load_documentation(repo_url)
                if cached_docs:
                    state['overview_doc'] = cached_docs.get('overview_doc', '')
                    state['file_docs'] = cached_docs.get('file_docs', {})
                    logger.info(f"Loaded cached documentation strings for {repo_url}")
                
                self._update_progress(state, "Found cached repository data", 5)
            else:
                logger.info(f"No cache found for {repo_url}")
                state['last_commit'] = None
                state['is_incremental'] = False
            
            return state
        except Exception as e:
            logger.error(f"Cache check failed: {e}")
            state['last_commit'] = None
            state['is_incremental'] = False
            return state
    
    def _detect_changes(self, state: WorkflowState) -> WorkflowState:
        """Detect changes since last analysis."""
        if not state.get('last_commit'):
            state['is_incremental'] = False
            return state
        
        try:
            # Clone repository temporarily to check changes
            analyzer = RepoAnalyzer(github_token=state.get('github_token', ''))
            repo_path = analyzer.clone_repository(state['repo_url'])
            state['repo_path'] = repo_path
            
            # Detect changes
            detector = ChangeDetector(repo_path)
            current_commit = detector.get_current_commit()
            changes = detector.get_changed_files(state['last_commit'], current_commit)
            
            state['current_commit'] = current_commit
            state['changes'] = changes
            state['is_incremental'] = changes.has_changes
            
            if changes.has_changes:
                logger.info(f"Detected {len(changes.all_changed_files)} changed files")
                self._update_progress(state, f"Detected {len(changes.all_changed_files)} changes", 10)
            else:
                logger.info("No changes detected, using cached documentation")
                self._update_progress(state, "No changes detected", 100)
                # TODO: Load cached docs from vector store
            
            return state
        except Exception as e:
            logger.error(f"Change detection failed: {e}")
            state['is_incremental'] = False
            return state
    
    def _create_embeddings(self, state: WorkflowState) -> WorkflowState:
        """Create and store embeddings for generated documentation."""
        repo_path = state.get('repo_path')
        
        # Debug logging
        logger.info(f"DEBUG _create_embeddings: repo_path={repo_path}, current_commit={state.get('current_commit')}")
        logger.info(f"DEBUG _create_embeddings: state keys={list(state.keys())}")
        
        try:
            if not self.vector_store or not self.embedder:
                return state
            
            repo_url = state['repo_url']
            current_commit = state.get('current_commit') or state.get('analysis', {}).get('commit_hash')
            
            if not repo_path or not current_commit:
                logger.warning("Missing repo_path or commit_hash, skipping embeddings")
                return state
            
            self._update_progress(state, "Creating code embeddings...", 85)
            
            # Get files to embed
            files_to_embed = []
            if state.get('is_incremental') and state.get('changes'):
                # Only embed changed files
                files_to_embed = state['changes'].all_changed_files
            else:
                # Embed all documented files
                files_to_embed = list(state.get('file_docs', {}).keys())
            
            # Create embeddings for each file
            all_chunks = []
            for file_path in files_to_embed:
                try:
                    # Read file content
                    full_path = os.path.join(repo_path, file_path)
                    if os.path.exists(full_path):
                        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        
                        # Create chunks with embeddings
                        chunks = self.embedder.embed_file(content, file_path)
                        
                        # Convert to CodeChunk objects
                        for chunk_dict in chunks:
                            code_chunk = CodeChunk(
                                id=chunk_dict['id'],
                                content=chunk_dict['content'],
                                file_path=chunk_dict['file_path'],
                                function_name=chunk_dict.get('function_name'),
                                start_line=chunk_dict['start_line'],
                                end_line=chunk_dict['end_line'],
                                embedding=chunk_dict['embedding']
                            )
                            all_chunks.append(code_chunk)
                except Exception as e:
                    logger.warning(f"Failed to embed {file_path}: {e}")
            
            # Store embeddings
            if all_chunks:
                if state.get('is_incremental'):
                    self.vector_store.update_chunks(repo_url, all_chunks, current_commit)
                else:
                    self.vector_store.add_code_chunks(repo_url, all_chunks, current_commit)
                
                logger.info(f"Stored {len(all_chunks)} code chunks in vector store")
                self._update_progress(state, f"Stored {len(all_chunks)} embeddings", 90)
            
            # Save documentation strings to cache
            doc_data = {
                'overview_doc': state.get('overview_doc', ''),
                'file_docs': state.get('file_docs', {})
            }
            self.vector_store.save_documentation(repo_url, doc_data)
            logger.info(f"Persisted documentation strings for {repo_url}")
            
            return state
            
        except Exception as e:
            logger.error(f"Failed to create embeddings: {e}")
            return state
        finally:
            # Cleanup repository manually with retry for Windows file locking
            import shutil
            import time
            if repo_path and os.path.exists(repo_path):
                max_attempts = 3
                for attempt in range(max_attempts):
                    try:
                        shutil.rmtree(repo_path)
                        logger.info(f"Cleaned up temporary directory: {repo_path}")
                        break
                    except PermissionError as e:
                        if attempt < max_attempts - 1:
                            # logger.warning(f"Cleanup attempt {attempt + 1} failed, retrying in 1 second...")
                            time.sleep(1)
                        else:
                            logger.warning(f"Could not cleanup temporary directory (Windows file lock): {repo_path}. This is harmless and will be cleaned up on next reboot.")
                    except Exception as e:
                        logger.error(f"Failed to cleanup temporary directory: {e}")
                        break
    
    # ===== Conditional Edge Functions =====
    
    def _should_use_cache(self, state: WorkflowState) -> str:
        """Determine if we should check for changes or do full analysis."""
        if state.get('last_commit'):
            return "detect_changes"
        return "clone_repo"
    
    def _has_changes(self, state: WorkflowState) -> str:
        """Determine if there are changes to process."""
        if state.get('changes') and state['changes'].has_changes:
            return "clone_repo"
        return END
    
    def _should_create_embeddings(self, state: WorkflowState) -> str:
        """Determine if we should create embeddings."""
        if self.vector_store and state.get('use_rag', True):
            return "create_embeddings"
        return END
    
    # ===== Workflow Execution =====
    
    def _upload_to_confluence(self, state: WorkflowState) -> WorkflowState:
        """Node: Upload documentation to Confluence."""
        try:
            self._update_progress(state, "Uploading to Confluence...", 85)
            
            # Extract repo name from URL
            repo_url = state['repo_url']
            repo_name = repo_url.rstrip('/').split('/')[-1].replace('.git', '')
            
            uploader = ConfluenceUploader(
                url=state['confluence_url'],
                api_token=state['confluence_token'],
                space_key=state['confluence_space']
            )
            
            # Create documentation structure
            main_page = uploader.create_documentation_structure(
                repo_name=repo_name,
                overview=state['overview_doc'],
                file_docs=state.get('file_docs', {})
            )
            
            state['confluence_page'] = main_page
            
            self._update_progress(state, "Documentation uploaded successfully", 100)
            return state
            
        except Exception as e:
            logger.error(f"Failed to upload to Confluence: {e}")
            state['error'] = f"Confluence upload failed: {str(e)}"
            return state
        finally:
            # Cleanup repository
            analyzer = state.get('_analyzer')
            if analyzer:
                analyzer.cleanup()
    
    def run(self, config: Dict) -> WorkflowState:
        """
        Run the complete documentation workflow.
        
        Args:
            config: Configuration dictionary with required keys:
                - repo_url: GitHub repository URL
                - github_token: GitHub PAT (optional for public repos)
                - hf_api_key: Hugging Face API key
                - model_name: Model name (optional)
                - confluence_url: Confluence instance URL
                - confluence_token: Confluence API token
                - confluence_space: Confluence space key
                
        Returns:
            Final workflow state
        """
        # Initialize state
        initial_state = WorkflowState(
            repo_url=config['repo_url'],
            github_token=config.get('github_token', ''),
            hf_api_key=config['hf_api_key'],
            model_name=config.get('model_name', 'Qwen/Qwen2.5-Coder-32B-Instruct'),
            confluence_url=config['confluence_url'],
            confluence_token=config['confluence_token'],
            confluence_space=config['confluence_space'],
            status='Initializing...',
            progress=0,
            current_file='',
            repo_path='',
            analysis={},
            important_files=[],
            overview_doc='',
            file_docs={},
            confluence_page={},
            # RAG fields
            use_rag=config.get('use_rag', True),
            last_commit=None,
            current_commit=None,
            changes=None,
            is_incremental=False,
            error=''
        )
        
        try:
            # Run the workflow
            final_state = self.workflow.invoke(initial_state)
            return final_state
            
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            initial_state['error'] = str(e)
            initial_state['status'] = 'Failed'
            return initial_state
