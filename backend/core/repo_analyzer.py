"""
Repository Analyzer Module
Handles GitHub repository cloning, code parsing, and structure extraction.
"""

import os
import shutil
import tempfile
from typing import Dict, List, Optional
from pathlib import Path
import logging

from git import Repo, GitCommandError

logger = logging.getLogger(__name__)


class RepoAnalyzer:
    """Analyzes GitHub repositories and extracts code structure."""
    
    def __init__(self, github_token: Optional[str] = None):
        """
        Initialize the repository analyzer.
        
        Args:
            github_token: GitHub Personal Access Token for private repos
        """
        self.github_token = github_token
        self.temp_dir = None
        self.repo_path = None
        
    def clone_repository(self, repo_url: str) -> str:
        """
        Clone a GitHub repository to a temporary directory.
        
        Args:
            repo_url: GitHub repository URL
            
        Returns:
            Path to the cloned repository
            
        Raises:
            GitCommandError: If cloning fails
        """
        try:
            # Create temporary directory
            self.temp_dir = tempfile.mkdtemp(prefix="docagent_")
            
            # Modify URL to include token for private repos
            if self.github_token and 'github.com' in repo_url:
                # Convert https://github.com/user/repo to https://token@github.com/user/repo
                repo_url = repo_url.replace('https://github.com', f'https://{self.github_token}@github.com')
            
            logger.info(f"Cloning repository to {self.temp_dir}")
            
            # Clone the repository
            repo = Repo.clone_from(repo_url, self.temp_dir, depth=1)  # Shallow clone for speed
            self.repo_path = self.temp_dir
            
            logger.info(f"Successfully cloned repository")
            return self.repo_path
            
            logger.info(f"Successfully cloned repository")
            return self.repo_path
            
        except GitCommandError as e:
            # If failed with token, try without token (fallback for public repos)
            if self.github_token and 'github.com' in repo_url and '@github.com' in repo_url:
                logger.warning(f"Clone with token failed ({e}). Retrying without token...")
                try:
                    # Reset URL to original without token
                    # Regex or simple replacement could work, but safest is to remove the auth part
                    clean_url = repo_url.split('@')[-1]
                    clean_url = f"https://{clean_url}"
                    
                    if os.path.exists(self.temp_dir):
                        shutil.rmtree(self.temp_dir)
                    self.temp_dir = tempfile.mkdtemp(prefix="docagent_")
                    
                    Repo.clone_from(clean_url, self.temp_dir, depth=1)
                    self.repo_path = self.temp_dir
                    logger.info("Successfully cloned repository (without token)")
                    return self.repo_path
                except GitCommandError as e2:
                    logger.error(f"Retry without token also failed: {e2}")
                    self.cleanup()
                    raise e # Raise original error or e2? raising e is probably better context if it was private
            
            logger.error(f"Failed to clone repository: {e}")
            self.cleanup()
            raise
    
    def analyze_structure(self) -> Dict[str, any]:
        """
        Analyze the repository structure and extract relevant information.
        
        Returns:
            Dictionary containing repository analysis
        """
        if not self.repo_path:
            raise ValueError("Repository not cloned. Call clone_repository first.")
        
        analysis = {
            'files': [],
            'directories': [],
            'languages': {},
            'total_files': 0,
            'total_lines': 0,
            'readme': None,
            'structure': {}
        }
        
        # Find README
        readme_files = ['README.md', 'README.txt', 'README.rst', 'README']
        for readme in readme_files:
            readme_path = Path(self.repo_path) / readme
            if readme_path.exists():
                try:
                    analysis['readme'] = readme_path.read_text(encoding='utf-8', errors='ignore')
                    break
                except Exception as e:
                    logger.warning(f"Failed to read README: {e}")
        
        # Analyze files
        for root, dirs, files in os.walk(self.repo_path):
            # Skip hidden directories and common ignore patterns
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', 'venv', 'env', '__pycache__', 'dist', 'build']]
            
            rel_root = os.path.relpath(root, self.repo_path)
            if rel_root != '.':
                analysis['directories'].append(rel_root)
            
            for file in files:
                if file.startswith('.'):
                    continue
                
                file_path = Path(root) / file
                rel_path = os.path.relpath(file_path, self.repo_path)
                
                # Get file extension
                ext = file_path.suffix.lower()
                
                # Count language files
                lang_map = {
                    '.py': 'Python',
                    '.js': 'JavaScript',
                    '.ts': 'TypeScript',
                    '.tsx': 'TypeScript',
                    '.jsx': 'JavaScript',
                    '.java': 'Java',
                    '.cpp': 'C++',
                    '.c': 'C',
                    '.go': 'Go',
                    '.rs': 'Rust',
                    '.rb': 'Ruby',
                    '.php': 'PHP',
                    '.cs': 'C#',
                    '.swift': 'Swift',
                    '.kt': 'Kotlin'
                }
                
                if ext in lang_map:
                    lang = lang_map[ext]
                    analysis['languages'][lang] = analysis['languages'].get(lang, 0) + 1
                
                # Read file content for analysis
                try:
                    content = file_path.read_text(encoding='utf-8', errors='ignore')
                    lines = len(content.splitlines())
                    
                    file_info = {
                        'path': rel_path,
                        'name': file,
                        'extension': ext,
                        'lines': lines,
                        'size': file_path.stat().st_size,
                        'content': content if ext in lang_map else None  # Only store code files
                    }
                    
                    analysis['files'].append(file_info)
                    analysis['total_files'] += 1
                    analysis['total_lines'] += lines
                    
                except Exception as e:
                    logger.warning(f"Failed to read file {rel_path}: {e}")
        
        # Build directory structure tree
        analysis['structure'] = self._build_tree_structure()
        
        # Add current commit hash for RAG tracking
        analysis['commit_hash'] = self.get_current_commit()
        
        return analysis
    
    def get_current_commit(self) -> Optional[str]:
        """
        Get the current commit hash of the repository.
        
        Returns:
            Commit hash or None if not available
        """
        try:
            if self.repo_path:
                logger.info(f"DEBUG: Attempting to get commit from repo_path: {self.repo_path}")
                repo = Repo(self.repo_path)
                commit_hash = repo.head.commit.hexsha
                logger.info(f"DEBUG: Successfully got commit hash: {commit_hash}")
                return commit_hash
            else:
                logger.warning("DEBUG: repo_path is None or empty")
        except Exception as e:
            logger.error(f"Failed to get commit hash from {self.repo_path}: {type(e).__name__}: {str(e)}")
        return None
    
    def _build_tree_structure(self) -> Dict:
        """Build a tree structure of the repository."""
        tree = {}
        
        for root, dirs, files in os.walk(self.repo_path):
            # Skip hidden and ignored directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', 'venv', 'env', '__pycache__']]
            
            rel_root = os.path.relpath(root, self.repo_path)
            parts = rel_root.split(os.sep) if rel_root != '.' else []
            
            current = tree
            for part in parts:
                if part not in current:
                    current[part] = {}
                current = current[part]
            
            # Add files to current directory
            current['__files__'] = [f for f in files if not f.startswith('.')]
        
        return tree
    
    def get_important_files(self, analysis: Dict) -> List[Dict]:
        """
        Extract the most important files for documentation.
        
        Args:
            analysis: Repository analysis dictionary
            
        Returns:
            List of important files with their content
        """
        important = []
        
        # Priority files
        priority_patterns = [
            'main.', 'index.', 'app.', '__init__.py', 'setup.py',
            'package.json', 'requirements.txt', 'Cargo.toml', 'go.mod'
        ]
        
        for file_info in analysis['files']:
            # Include README
            if 'readme' in file_info['name'].lower():
                important.append(file_info)
                continue
            
            # Include priority files
            if any(pattern in file_info['name'].lower() for pattern in priority_patterns):
                important.append(file_info)
                continue
            
            # Include files with significant code (>50 lines)
            if file_info.get('content') and file_info['lines'] > 50:
                important.append(file_info)
        
        # Sort by lines of code (descending)
        important.sort(key=lambda x: x.get('lines', 0), reverse=True)
        
        # Limit to top 20 files to avoid overwhelming the LLM
        return important[:20]
    
    def cleanup(self):
        """Clean up temporary directory."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
                logger.info(f"Cleaned up temporary directory: {self.temp_dir}")
            except Exception as e:
                logger.error(f"Failed to cleanup temporary directory: {e}")
            finally:
                self.temp_dir = None
                self.repo_path = None
    
    def __del__(self):
        """Ensure cleanup on deletion."""
        self.cleanup()
