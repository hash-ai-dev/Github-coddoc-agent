"""
Change Detector Module
Detects changes between repository versions using Git.
"""

import logging
from typing import List, Dict, Optional, Set
from pathlib import Path
from git import Repo, GitCommandError
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ChangeSet:
    """Represents changes between two commits."""
    added_files: List[str]
    modified_files: List[str]
    deleted_files: List[str]
    current_commit: str
    previous_commit: Optional[str]
    
    @property
    def has_changes(self) -> bool:
        """Check if there are any changes."""
        return bool(self.added_files or self.modified_files or self.deleted_files)
    
    @property
    def all_changed_files(self) -> List[str]:
        """Get all changed files (added + modified)."""
        return self.added_files + self.modified_files


class ChangeDetector:
    """Detects changes in a Git repository."""
    
    def __init__(self, repo_path: str):
        """
        Initialize the change detector.
        
        Args:
            repo_path: Path to the Git repository
        """
        self.repo_path = Path(repo_path)
        
        try:
            self.repo = Repo(repo_path)
            logger.info(f"Initialized ChangeDetector for {repo_path}")
        except Exception as e:
            logger.error(f"Failed to initialize Git repo: {e}")
            raise
    
    def get_current_commit(self) -> str:
        """
        Get the current commit hash.
        
        Returns:
            Current commit SHA
        """
        try:
            return self.repo.head.commit.hexsha
        except Exception as e:
            logger.error(f"Failed to get current commit: {e}")
            raise
    
    def get_changed_files(
        self, 
        previous_commit: Optional[str] = None,
        current_commit: Optional[str] = None
    ) -> ChangeSet:
        """
        Get changed files between two commits.
        
        Args:
            previous_commit: Previous commit hash (None for initial analysis)
            current_commit: Current commit hash (None for HEAD)
            
        Returns:
            ChangeSet with added, modified, and deleted files
        """
        if current_commit is None:
            current_commit = self.get_current_commit()
        
        # If no previous commit, treat all files as added
        if previous_commit is None:
            logger.info("No previous commit, treating all files as new")
            return self._get_all_files_as_added(current_commit)
        
        try:
            # Get commits
            prev_commit_obj = self.repo.commit(previous_commit)
            curr_commit_obj = self.repo.commit(current_commit)
            
            # Get diff between commits
            diffs = prev_commit_obj.diff(curr_commit_obj)
            
            added_files = []
            modified_files = []
            deleted_files = []
            
            for diff in diffs:
                # Filter for code files only
                if not self._is_code_file(diff.b_path if diff.b_path else diff.a_path):
                    continue
                
                if diff.new_file:
                    added_files.append(diff.b_path)
                elif diff.deleted_file:
                    deleted_files.append(diff.a_path)
                elif diff.renamed_file:
                    # Treat rename as delete + add
                    deleted_files.append(diff.a_path)
                    added_files.append(diff.b_path)
                else:
                    # Modified file
                    modified_files.append(diff.b_path)
            
            logger.info(f"Changes: {len(added_files)} added, {len(modified_files)} modified, {len(deleted_files)} deleted")
            
            return ChangeSet(
                added_files=added_files,
                modified_files=modified_files,
                deleted_files=deleted_files,
                current_commit=current_commit,
                previous_commit=previous_commit
            )
            
        except GitCommandError as e:
            logger.error(f"Git command failed: {e}")
            # Fallback: treat as initial analysis
            return self._get_all_files_as_added(current_commit)
        except Exception as e:
            logger.error(f"Failed to get changed files: {e}")
            raise
    
    def _get_all_files_as_added(self, commit_hash: str) -> ChangeSet:
        """
        Get all code files in the repository as added files.
        
        Args:
            commit_hash: Current commit hash
            
        Returns:
            ChangeSet with all files as added
        """
        all_files = []
        
        try:
            # Walk through repository
            for item in self.repo.tree().traverse():
                if item.type == 'blob':  # It's a file
                    if self._is_code_file(item.path):
                        all_files.append(item.path)
            
            logger.info(f"Found {len(all_files)} code files in repository")
            
            return ChangeSet(
                added_files=all_files,
                modified_files=[],
                deleted_files=[],
                current_commit=commit_hash,
                previous_commit=None
            )
        except Exception as e:
            logger.error(f"Failed to get all files: {e}")
            raise
    
    def _is_code_file(self, file_path: str) -> bool:
        """
        Check if a file is a code file we want to document.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if it's a code file
        """
        # Code file extensions
        code_extensions = {
            '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.h',
            '.cs', '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.scala',
            '.r', '.m', '.sh', '.sql', '.html', '.css', '.vue', '.dart'
        }
        
        # Exclude patterns
        exclude_patterns = {
            'node_modules/', '__pycache__/', '.git/', 'dist/', 'build/',
            'venv/', 'env/', '.pytest_cache/', 'coverage/', '.next/',
            'target/', 'bin/', 'obj/'
        }
        
        # Check if file is in excluded directory
        for pattern in exclude_patterns:
            if pattern in file_path:
                return False
        
        # Check extension
        file_ext = Path(file_path).suffix.lower()
        return file_ext in code_extensions
    
    def get_file_content(self, file_path: str, commit_hash: Optional[str] = None) -> Optional[str]:
        """
        Get file content at a specific commit.
        
        Args:
            file_path: Path to the file
            commit_hash: Commit hash (None for current)
            
        Returns:
            File content or None if not found
        """
        try:
            if commit_hash is None:
                # Get from working directory
                full_path = self.repo_path / file_path
                if full_path.exists():
                    return full_path.read_text(encoding='utf-8', errors='ignore')
                return None
            else:
                # Get from specific commit
                commit = self.repo.commit(commit_hash)
                blob = commit.tree / file_path
                return blob.data_stream.read().decode('utf-8', errors='ignore')
        except Exception as e:
            logger.warning(f"Failed to get file content for {file_path}: {e}")
            return None
    
    def get_file_diff(
        self, 
        file_path: str, 
        old_commit: str, 
        new_commit: str
    ) -> Optional[str]:
        """
        Get diff for a specific file between two commits.
        
        Args:
            file_path: Path to the file
            old_commit: Old commit hash
            new_commit: New commit hash
            
        Returns:
            Diff string or None
        """
        try:
            old_commit_obj = self.repo.commit(old_commit)
            new_commit_obj = self.repo.commit(new_commit)
            
            diffs = old_commit_obj.diff(new_commit_obj, paths=file_path, create_patch=True)
            
            if diffs:
                return diffs[0].diff.decode('utf-8', errors='ignore')
            return None
        except Exception as e:
            logger.error(f"Failed to get file diff: {e}")
            return None
