"""
Documentation Generator Module
Uses Qwen model via Hugging Face Inference API to generate documentation.
"""

import os
import logging
from typing import Dict, List, Optional
import requests
import json
from .doc_formatter import DocFormatter

logger = logging.getLogger(__name__)


class DocGenerator:
    """Generates documentation using Qwen model via Hugging Face."""
    
    # API Configuration - New Router API
    API_URL = "https://router.huggingface.co/v1/chat/completions"

    def __init__(self, api_key: str, model_name: str = "Qwen/Qwen2.5-Coder-32B-Instruct"):
        """
        Initialize the documentation generator.
        
        Args:
            api_key: Hugging Face API key
            model_name: Model identifier on Hugging Face
        """
        self.api_key = api_key
        self.model_name = model_name
        self.api_url = self.API_URL  # Use the chat completions endpoint
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        self.status_callback = None

    def set_callback(self, callback):
        """Set callback for status updates and previews."""
        self.status_callback = callback
    
    def generate_overview(self, analysis: Dict) -> str:
        """
        Generate a high-level overview of the repository.
        
        Args:
            analysis: Repository analysis dictionary
            
        Returns:
            Generated overview documentation
        """
        # Build context from analysis
        context = self._build_overview_context(analysis)
        
        prompt = f"""You are a technical documentation expert. Based on the following repository analysis, generate a comprehensive overview documentation.

Repository Analysis:
{context}

Generate a well-structured overview that includes:
1. Project Purpose and Description
2. Key Technologies and Languages Used
3. Project Structure Overview
4. Main Components and Their Roles
5. Getting Started Guide (if applicable)

FORMATTING REQUIREMENTS - FOLLOW THESE STRICTLY:
- Use proper Markdown syntax throughout
- Start with a single # (H1) header for the main title
- Use ## (H2) for major sections, ### (H3) for subsections
- Add a blank line before and after each header
- Add a blank line before and after code blocks
- Use ``` for code blocks with language specification (e.g., ```python)
- Use single backticks ` for inline code, function names, and file names
- Use **bold** for emphasis on important terms
- Use - or * for unordered lists, ensure consistent spacing
- Write in single paragraphs without hard line wrapping
- Use standard ASCII punctuation (avoid smart quotes)
- Do NOT use raw # symbols in text - only for headers
- Ensure all code examples are properly formatted in code blocks

Use clear, professional language suitable for technical documentation."""

        result = self._call_model(prompt)
        # Sanitize markdown for consistent formatting
        result = DocFormatter.sanitize_markdown(result)
        if self.status_callback:
            self.status_callback(result, type="preview")
        return result
    
    def generate_file_documentation(self, file_info: Dict) -> Optional[str]:
        """
        Generate documentation for a specific file.
        
        Args:
            file_info: File information dictionary with content
            
        Returns:
            Generated file documentation or None if skipped
        """
        file_path = file_info.get('path', 'Unknown')
        content = file_info.get('content', '')
        
        if not content:
            return None
        
        # Truncate very long files
        max_chars = 8000
        if len(content) > max_chars:
            content = content[:max_chars] + "\n... (truncated)"
        
        prompt = f"""You are a technical documentation expert. Analyze the following code file and generate comprehensive documentation.

File: {file_path}

Code:
```
{content}
```

If the file is empty, trivial, auto-generated, or does not require documentation, strictly return "NO_DOCS_NEEDED" as the only output.

Generate documentation that includes:
1. File Purpose and Overview
2. Key Functions/Classes and Their Descriptions
3. Important Dependencies
4. Usage Examples (if applicable)
5. Notable Implementation Details

FORMATTING REQUIREMENTS - FOLLOW THESE STRICTLY:
- Use proper Markdown syntax throughout
- Start with a single # (H1) header with the file name
- Use ## (H2) for major sections like "Overview", "Functions", "Classes"
- Use ### (H3) for individual function/class names
- Add a blank line before and after each header
- Add a blank line before and after code blocks
- Use ``` for code blocks with language specification (e.g., ```python, ```javascript)
- Use single backticks ` for inline code, function names, variable names, and parameters
- Use **bold** for important terms and concepts
- Format function signatures in code blocks, not as plain text
- Use - or * for lists with consistent spacing
- Write in single paragraphs without hard line wrapping
- Use standard ASCII punctuation (avoid smart quotes)
- Do NOT use raw # symbols in descriptions - only for headers
- Ensure proper spacing around all markdown elements

Use clear, professional language."""

        result = self._call_model(prompt)
        
        if "NO_DOCS_NEEDED" in result:
            return None
            
        # Sanitize markdown for consistent formatting
        result = DocFormatter.sanitize_markdown(result)
        if self.status_callback:
             self.status_callback(f"\n\n---\n\n# Documentation for {file_path}\n\n{result}", type="preview")
        return result
    
    def generate_api_documentation(self, files: List[Dict]) -> str:
        """
        Generate API documentation from multiple files.
        
        Args:
            files: List of file information dictionaries
            
        Returns:
            Generated API documentation
        """
        # Extract API-relevant files (those with functions/classes)
        api_context = self._build_api_context(files)
        
        prompt = f"""You are a technical documentation expert. Based on the following code analysis, generate comprehensive API documentation.

Code Analysis:
{api_context}

Generate API documentation that includes:
1. Available APIs/Endpoints (if applicable)
2. Function/Method Signatures
3. Parameters and Return Values
4. Usage Examples
5. Error Handling

FORMATTING REQUIREMENTS - FOLLOW THESE STRICTLY:
- Use proper Markdown syntax throughout
- Start with a single # (H1) header for "API Documentation"
- Use ## (H2) for endpoint categories or major API sections
- Use ### (H3) for individual endpoints or methods
- Add a blank line before and after each header
- Format API endpoints in code blocks: ```http or as inline code
- Use tables for parameters (| Parameter | Type | Description |)
- Use ``` for request/response examples with appropriate language tags
- Use single backticks ` for parameter names, types, and inline code
- Use **bold** for HTTP methods (GET, POST, PUT, DELETE)
- Format JSON responses in proper code blocks with ```json
- Use - or * for lists with consistent spacing
- Write in single paragraphs without hard line wrapping
- Use standard ASCII punctuation (avoid smart quotes)
- Do NOT use raw # symbols in text - only for headers
- Ensure proper spacing around all markdown elements

Use clear, professional language suitable for API documentation."""

        result = self._call_model(prompt)
        # Sanitize markdown for consistent formatting
        return DocFormatter.sanitize_markdown(result)
    
    def _build_overview_context(self, analysis: Dict) -> str:
        """Build context string for overview generation."""
        context_parts = []
        
        # README content
        if analysis.get('readme'):
            context_parts.append(f"README Content:\n{analysis['readme'][:2000]}")  # Limit README size
        
        # Languages
        if analysis.get('languages'):
            langs = ', '.join([f"{lang} ({count} files)" for lang, count in analysis['languages'].items()])
            context_parts.append(f"\nLanguages: {langs}")
        
        # Statistics
        context_parts.append(f"\nTotal Files: {analysis.get('total_files', 0)}")
        context_parts.append(f"Total Lines of Code: {analysis.get('total_lines', 0)}")
        
        # Directory structure (simplified)
        if analysis.get('directories'):
            dirs = '\n'.join([f"  - {d}" for d in analysis['directories'][:10]])
            context_parts.append(f"\nKey Directories:\n{dirs}")
        
        # Important files
        important_files = [f['name'] for f in analysis.get('files', [])[:15]]
        if important_files:
            files_list = '\n'.join([f"  - {f}" for f in important_files])
            context_parts.append(f"\nKey Files:\n{files_list}")
        
        return '\n'.join(context_parts)
    
    def _build_api_context(self, files: List[Dict]) -> str:
        """Build context string for API documentation."""
        context_parts = []
        
        for file_info in files[:5]:  # Limit to 5 files to avoid token limits
            if file_info.get('content'):
                content = file_info['content'][:3000]  # Truncate each file
                context_parts.append(f"\nFile: {file_info['path']}\n```\n{content}\n```")
        
        return '\n'.join(context_parts)
    
    def _call_model(self, prompt: str, max_retries: int = 3) -> str:
        """
        Call the Hugging Face Inference API.
        
        Args:
            prompt: The prompt to send to the model
            max_retries: Maximum number of retry attempts
            
        Returns:
            Generated text from the model
        """
        # New chat completions format
        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 2000,
            "temperature": 0.7,
            "top_p": 0.95
        }
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Calling Hugging Face API (attempt {attempt + 1}/{max_retries})")
                if self.status_callback:
                    self.status_callback(f"Connecting to Hugging Face model... (Attempt {attempt + 1})", type="log")
                
                response = requests.post(
                    self.api_url,
                    headers=self.headers,
                    json=payload,
                    timeout=180  # Increased timeout for large models (3 minutes)
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # Handle chat completions response format
                    # Response structure: {"choices": [{"message": {"content": "..."}}]}
                    if isinstance(result, dict) and 'choices' in result:
                        choices = result.get('choices', [])
                        if choices and len(choices) > 0:
                            message = choices[0].get('message', {})
                            generated_text = message.get('content', '')
                        else:
                            generated_text = ''
                    else:
                        # Fallback for unexpected format
                        generated_text = str(result)
                    
                    logger.info("Successfully generated documentation")
                    if self.status_callback:
                        self.status_callback("Received response from Hugging Face.", type="log")
                        
                    return generated_text
                
                elif response.status_code == 503:
                    # Model is loading, wait and retry
                    logger.warning(f"Model is loading, retrying in 10 seconds...")
                    import time
                    time.sleep(10)
                    continue
                
                else:
                    error_msg = f"API request failed with status {response.status_code}: {response.text}"
                    logger.error(error_msg)
                    
                    if attempt == max_retries - 1:
                        return f"# Documentation Generation Failed\n\nError: {error_msg}"
                    
            except requests.exceptions.Timeout:
                logger.error(f"Request timed out (attempt {attempt + 1}/{max_retries})")
                if self.status_callback:
                    self.status_callback(f"Request timed out. Model may be loading. Retrying...", type="log")
                if attempt == max_retries - 1:
                    return "# Documentation Generation Failed\n\nError: Request timed out after 3 attempts. The model may be loading or overloaded. Please try again in a few minutes."
                # Wait before retry
                import time
                time.sleep(15)
                    
            except Exception as e:
                logger.error(f"Error calling model: {e}")
                if attempt == max_retries - 1:
                    return f"# Documentation Generation Failed\n\nError: {str(e)}"
        
        return "# Documentation Generation Failed\n\nError: Maximum retries exceeded"
    
    def format_for_confluence(self, markdown_content: str) -> str:
        """
        Convert Markdown to Confluence Storage Format.
        
        Args:
            markdown_content: Markdown formatted documentation
            
        Returns:
            Confluence-compatible HTML/storage format
        """
        # Use the comprehensive DocFormatter converter
        return DocFormatter.markdown_to_confluence(markdown_content)
