"""
Confluence Uploader Module
Handles authentication and uploading documentation to Confluence.
"""

import logging
from typing import Dict, Optional
from atlassian import Confluence
from .doc_formatter import DocFormatter

logger = logging.getLogger(__name__)


class ConfluenceUploader:
    """Uploads documentation to Confluence."""
    
    def __init__(self, url: str, api_token: str, space_key: str, username: Optional[str] = None):
        """
        Initialize the Confluence uploader.
        
        Args:
            url: Confluence instance URL (e.g., https://your-domain.atlassian.net)
            api_token: Confluence API token
            space_key: Space key where documentation will be uploaded
            username: Confluence username/email (for Cloud, use email)
        """
        # Sanitize URL: Remove trailing slashes and /wiki/spaces if present
        self.url = url.rstrip('/')
        if '/wiki/spaces' in self.url:
            self.url = self.url.split('/wiki/spaces')[0]
        if '/wiki' in self.url and not self.url.endswith('/wiki'):
            self.url = self.url.split('/wiki')[0]
            
        self.space_key = space_key
        
        # Initialize Confluence client
        # For Confluence Cloud, username should be email and api_token is the API token
        # If no username is provided, we fallback to using the token as username (which might fail on Cloud)
        self.confluence = Confluence(
            url=self.url,
            username=username if username else api_token, 
            password=api_token,
            cloud=True
        )
        
        logger.info(f"Initialized Confluence uploader for: {self.url} (Space: {space_key})")
    
    def create_or_update_page(
        self,
        title: str,
        content: str,
        parent_title: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Create a new page or update existing one in Confluence.
        
        Args:
            title: Page title
            content: Page content (HTML or Confluence storage format)
            parent_title: Optional parent page title
            
        Returns:
            Dictionary with page information (id, url)
        """
        try:
            # Convert markdown to Confluence format
            formatted_content = DocFormatter.markdown_to_confluence(content)
            
            # Check if page already exists
            existing_page = self.confluence.get_page_by_title(
                space=self.space_key,
                title=title
            )
            
            if existing_page:
                # Update existing page
                logger.info(f"Updating existing page: {title}")
                page_id = existing_page['id']
                
                result = self.confluence.update_page(
                    page_id=page_id,
                    title=title,
                    body=formatted_content,
                    type='page',
                    representation='storage'
                )
                
                page_url = f"{self.url}/wiki/spaces/{self.space_key}/pages/{page_id}"
                
            else:
                # Create new page
                logger.info(f"Creating new page: {title}")
                
                # Get parent page ID if specified
                parent_id = None
                if parent_title:
                    parent_page = self.confluence.get_page_by_title(
                        space=self.space_key,
                        title=parent_title
                    )
                    if parent_page:
                        parent_id = parent_page['id']
                
                result = self.confluence.create_page(
                    space=self.space_key,
                    title=title,
                    body=formatted_content,
                    parent_id=parent_id,
                    type='page',
                    representation='storage'
                )
                
                page_id = result['id']
                page_url = f"{self.url}/wiki/spaces/{self.space_key}/pages/{page_id}"
            
            logger.info(f"Successfully created/updated page: {page_url}")
            
            return {
                'id': page_id,
                'url': page_url,
                'title': title
            }
            
        except Exception as e:
            logger.error(f"Failed to create/update Confluence page: {e}")
            raise
    
    def create_documentation_structure(
        self,
        repo_name: str,
        overview: str,
        file_docs: Dict[str, str]
    ) -> Dict[str, str]:
        """
        Create a complete documentation structure in Confluence.
        
        Args:
            repo_name: Repository name (used as parent page title)
            overview: Overview documentation content
            file_docs: Dictionary mapping file names to their documentation
            
        Returns:
            Dictionary with main page information
        """
        try:
            # Create main documentation page
            main_title = f"{repo_name} - Documentation"
            main_content = f"""
<h1>{repo_name} Documentation</h1>
<p>Auto-generated documentation for {repo_name}</p>

<h2>Overview</h2>
{overview}

<h2>File Documentation</h2>
<p>Detailed documentation for individual files:</p>
<ul>
"""
            
            # Add links to file documentation pages
            for file_name in file_docs.keys():
                file_page_title = f"{repo_name} - {file_name}"
                main_content += f"<li><a href='#'>{file_name}</a></li>\n"
            
            main_content += "</ul>"
            
            # Create main page
            main_page = self.create_or_update_page(
                title=main_title,
                content=main_content
            )
            
            # Create individual file documentation pages
            for file_name, file_doc in file_docs.items():
                file_page_title = f"{repo_name} - {file_name}"
                
                file_content = f"""
<h1>{file_name}</h1>
{file_doc}
<p><a href='{main_page['url']}'>Back to Main Documentation</a></p>
"""
                
                self.create_or_update_page(
                    title=file_page_title,
                    content=file_content,
                    parent_title=main_title
                )
            
            logger.info(f"Successfully created documentation structure for {repo_name}")
            return main_page
            
        except Exception as e:
            logger.error(f"Failed to create documentation structure: {e}")
            raise
    
    def test_connection(self) -> bool:
        """
        Test the Confluence connection.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            # Try to get space information
            space = self.confluence.get_space(self.space_key)
            space_name = space.get('name', self.space_key) if isinstance(space, dict) else self.space_key
            logger.info(f"Successfully connected to Confluence space: {space_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Confluence: {e}")
            return False
