import os
import logging
import tempfile
import shutil
from github import Github, GithubException
from git import Repo, GitCommandError

logger = logging.getLogger("github_client")

class GitHubClient:
    """
    Handles GitHub repository operations including cloning, pulling, and change detection.
    """
    def __init__(self, token=None):
        self.token = token
        self.github = Github(token) if token else None
        
    def clone_or_update_repo(self, repo_url, local_path, branch="main"):
        """
        Clone a repository if it doesn't exist locally, otherwise pull latest changes.
        
        Args:
            repo_url: GitHub repository URL (https://github.com/user/repo)
            local_path: Local directory path to clone/update
            branch: Branch name to checkout (default: main)
            
        Returns:
            tuple: (success: bool, commit_sha: str, message: str)
        """
        try:
            # Ensure parent directory exists
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            if os.path.exists(local_path):
                # Repository exists, pull latest changes
                logger.info(f"Updating existing repository at {local_path}")
                repo = Repo(local_path)
                
                # Fetch and pull
                origin = repo.remotes.origin
                origin.fetch()
                
                # Get current commit before pull
                old_sha = repo.head.commit.hexsha
                
                # Pull latest changes
                origin.pull(branch)
                
                # Get new commit after pull
                new_sha = repo.head.commit.hexsha
                
                if old_sha == new_sha:
                    return True, new_sha, "Repository is up to date"
                else:
                    return True, new_sha, f"Updated from {old_sha[:7]} to {new_sha[:7]}"
            else:
                # Clone repository
                logger.info(f"Cloning repository {repo_url} to {local_path}")
                
                # Add token to URL if provided
                if self.token:
                    # Convert https://github.com/user/repo to https://token@github.com/user/repo
                    clone_url = repo_url.replace("https://", f"https://{self.token}@")
                else:
                    clone_url = repo_url
                
                repo = Repo.clone_from(clone_url, local_path, branch=branch)
                commit_sha = repo.head.commit.hexsha
                
                return True, commit_sha, f"Repository cloned successfully (commit: {commit_sha[:7]})"
                
        except GitCommandError as e:
            logger.error(f"Git error: {e}")
            return False, None, f"Git error: {str(e)}"
        except Exception as e:
            logger.error(f"Failed to clone/update repository: {e}")
            return False, None, f"Error: {str(e)}"
    
    def get_latest_commit_sha(self, repo_url, branch="main"):
        """
        Get the latest commit SHA from a remote repository without cloning.
        
        Args:
            repo_url: GitHub repository URL
            branch: Branch name
            
        Returns:
            str: Commit SHA or None if failed
        """
        try:
            if not self.github:
                logger.warning("GitHub API client not initialized (no token provided)")
                return None
            
            # Extract owner/repo from URL
            # https://github.com/owner/repo -> owner/repo
            parts = repo_url.rstrip('/').split('/')
            owner, repo_name = parts[-2], parts[-1]
            
            repo = self.github.get_repo(f"{owner}/{repo_name}")
            branch_obj = repo.get_branch(branch)
            
            return branch_obj.commit.sha
            
        except GithubException as e:
            logger.error(f"GitHub API error: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to get latest commit: {e}")
            return None
    
    def get_changed_files(self, repo_path, old_sha, new_sha):
        """
        Get list of files that changed between two commits.
        
        Args:
            repo_path: Local repository path
            old_sha: Old commit SHA
            new_sha: New commit SHA
            
        Returns:
            list: List of changed file paths
        """
        try:
            repo = Repo(repo_path)
            
            # Get diff between commits
            old_commit = repo.commit(old_sha)
            new_commit = repo.commit(new_sha)
            
            diff = old_commit.diff(new_commit)
            
            changed_files = []
            for change in diff:
                # change.a_path is the file path
                if change.a_path:
                    changed_files.append(change.a_path)
                if change.b_path and change.b_path != change.a_path:
                    changed_files.append(change.b_path)
            
            return list(set(changed_files))  # Remove duplicates
            
        except Exception as e:
            logger.error(f"Failed to get changed files: {e}")
            return []
    
    def validate_token(self):
        """
        Validate the GitHub token by making a simple API call.
        
        Returns:
            tuple: (valid: bool, username: str or None)
        """
        try:
            if not self.github:
                return False, None
            
            user = self.github.get_user()
            return True, user.login
            
        except GithubException as e:
            logger.error(f"Token validation failed: {e}")
            return False, None
