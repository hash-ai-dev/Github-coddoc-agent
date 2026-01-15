"""
Documentation Formatter Module
Handles proper formatting and sanitization of generated documentation.
"""

import re
import html
import json
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class DocFormatter:
    """Formats and sanitizes documentation content."""
    
    @staticmethod
    def sanitize_markdown(content: str) -> str:
        """
        Sanitize and standardize markdown content.
        
        Args:
            content: Raw markdown content
            
        Returns:
            Sanitized markdown content
        """
        if not content:
            return ""
        
        # Normalize line endings
        content = content.replace('\r\n', '\n').replace('\r', '\n')
        
        # Remove excessive blank lines (more than 2 consecutive)
        content = re.sub(r'\n{3,}', '\n\n', content)
        
        # Ensure proper spacing around headers
        content = re.sub(r'([^\n])\n(#{1,6}\s)', r'\1\n\n\2', content)
        content = re.sub(r'(#{1,6}[^\n]+)\n([^\n#])', r'\1\n\n\2', content)
        
        # Ensure code blocks have proper spacing
        content = re.sub(r'([^\n])\n(```)', r'\1\n\n\2', content)
        content = re.sub(r'(```)\n([^\n`])', r'\1\n\n\2', content)
        
        # Fix inline code formatting (ensure backticks are balanced)
        content = DocFormatter._fix_inline_code(content)
        
        # Standardize list formatting
        content = DocFormatter._standardize_lists(content)
        
        # Remove trailing whitespace from lines
        lines = content.split('\n')
        lines = [line.rstrip() for line in lines]
        content = '\n'.join(lines)
        
        # Ensure content ends with a single newline
        content = content.rstrip() + '\n'
        
        return content
    
    @staticmethod
    def _fix_inline_code(content: str) -> str:
        """Fix unbalanced inline code backticks."""
        lines = content.split('\n')
        fixed_lines = []
        
        for line in lines:
            # Skip code block delimiters
            if line.strip().startswith('```'):
                fixed_lines.append(line)
                continue
            
            # Count backticks
            backtick_count = line.count('`')
            
            # If odd number of backticks, it might be unbalanced
            if backtick_count % 2 != 0:
                # Try to fix by escaping standalone backticks
                # This is a simple heuristic - you may need more sophisticated logic
                logger.warning(f"Unbalanced backticks detected in line: {line[:50]}...")
            
            fixed_lines.append(line)
        
        return '\n'.join(fixed_lines)
    
    @staticmethod
    def _standardize_lists(content: str) -> str:
        """Standardize list formatting."""
        lines = content.split('\n')
        fixed_lines = []
        
        for i, line in enumerate(lines):
            # Ensure proper spacing before lists
            if re.match(r'^\s*[-*+]\s', line) or re.match(r'^\s*\d+\.\s', line):
                if i > 0 and fixed_lines and fixed_lines[-1].strip() and not re.match(r'^\s*[-*+\d]', fixed_lines[-1]):
                    fixed_lines.append('')
            
            fixed_lines.append(line)
        
        return '\n'.join(fixed_lines)
    
    @staticmethod
    def escape_for_json(content: str) -> str:
        """
        Properly escape content for JSON storage.
        
        Args:
            content: Content to escape
            
        Returns:
            JSON-safe content
        """
        if not content:
            return ""
        
        # Python's json.dumps handles most escaping, but we can pre-process
        # to ensure special characters are preserved
        
        # Normalize unicode characters
        content = content.encode('utf-8', errors='ignore').decode('utf-8')
        
        return content
    
    @staticmethod
    def markdown_to_confluence(content: str) -> str:
        """
        Convert Markdown to Confluence Storage Format.
        
        Args:
            content: Markdown content
            
        Returns:
            Confluence storage format (XHTML-based)
        """
        if not content:
            return ""
        
        # Escape HTML special characters first
        # But preserve markdown syntax temporarily
        
        # Convert headers
        content = re.sub(r'^######\s+(.+)$', r'<h6>\1</h6>', content, flags=re.MULTILINE)
        content = re.sub(r'^#####\s+(.+)$', r'<h5>\1</h5>', content, flags=re.MULTILINE)
        content = re.sub(r'^####\s+(.+)$', r'<h4>\1</h4>', content, flags=re.MULTILINE)
        content = re.sub(r'^###\s+(.+)$', r'<h3>\1</h3>', content, flags=re.MULTILINE)
        content = re.sub(r'^##\s+(.+)$', r'<h2>\1</h2>', content, flags=re.MULTILINE)
        content = re.sub(r'^#\s+(.+)$', r'<h1>\1</h1>', content, flags=re.MULTILINE)
        
        # Convert code blocks with language specification
        def replace_code_block(match):
            lang = match.group(1) or 'none'
            code_content = html.escape(match.group(2))
            return f'<ac:structured-macro ac:name="code"><ac:parameter ac:name="language">{lang}</ac:parameter><ac:plain-text-body><![CDATA[{code_content}]]></ac:plain-text-body></ac:structured-macro>'
        
        content = re.sub(r'```(\w+)?\n(.*?)```', replace_code_block, content, flags=re.DOTALL)
        
        # Convert inline code
        content = re.sub(r'`([^`]+)`', r'<code>\1</code>', content)
        
        # Convert bold
        content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content)
        content = re.sub(r'__(.+?)__', r'<strong>\1</strong>', content)
        
        # Convert italic
        content = re.sub(r'\*(.+?)\*', r'<em>\1</em>', content)
        content = re.sub(r'_(.+?)_', r'<em>\1</em>', content)
        
        # Convert links
        content = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<a href="\2">\1</a>', content)
        
        # Convert unordered lists
        content = re.sub(r'^\s*[-*+]\s+(.+)$', r'<li>\1</li>', content, flags=re.MULTILINE)
        
        # Convert ordered lists
        content = re.sub(r'^\s*\d+\.\s+(.+)$', r'<li>\1</li>', content, flags=re.MULTILINE)
        
        # Wrap consecutive list items in ul/ol tags
        content = re.sub(r'(<li>.*?</li>\n)+', lambda m: '<ul>\n' + m.group(0) + '</ul>\n', content, flags=re.DOTALL)
        
        # Convert paragraphs (lines not already in tags)
        lines = content.split('\n')
        formatted_lines = []
        for line in lines:
            line = line.strip()
            if line and not re.match(r'<[^>]+>', line):
                formatted_lines.append(f'<p>{line}</p>')
            else:
                formatted_lines.append(line)
        
        content = '\n'.join(formatted_lines)
        
        return content
    
    @staticmethod
    def format_for_display(content: str, format_type: str = 'markdown') -> str:
        """
        Format documentation for display.
        
        Args:
            content: Raw documentation content
            format_type: Output format ('markdown', 'confluence', 'html')
            
        Returns:
            Formatted content
        """
        # First sanitize the markdown
        content = DocFormatter.sanitize_markdown(content)
        
        if format_type == 'confluence':
            return DocFormatter.markdown_to_confluence(content)
        elif format_type == 'html':
            # Basic HTML conversion (you could use a library like markdown2 for better results)
            return DocFormatter.markdown_to_confluence(content)
        else:
            return content
    
    @staticmethod
    def save_to_json(data: Dict[str, Any], filepath: str) -> bool:
        """
        Save documentation data to JSON with proper formatting.
        
        Args:
            data: Documentation data dictionary
            filepath: Path to save JSON file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure all string values are properly escaped
            processed_data = {}
            for key, value in data.items():
                if isinstance(value, str):
                    processed_data[key] = DocFormatter.escape_for_json(value)
                elif isinstance(value, dict):
                    processed_data[key] = {
                        k: DocFormatter.escape_for_json(v) if isinstance(v, str) else v
                        for k, v in value.items()
                    }
                else:
                    processed_data[key] = value
            
            # Save with proper encoding and formatting
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(processed_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Successfully saved documentation to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save documentation to JSON: {e}")
            return False
    
    @staticmethod
    def load_from_json(filepath: str) -> Dict[str, Any]:
        """
        Load documentation data from JSON.
        
        Args:
            filepath: Path to JSON file
            
        Returns:
            Documentation data dictionary
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            logger.info(f"Successfully loaded documentation from {filepath}")
            return data
            
        except Exception as e:
            logger.error(f"Failed to load documentation from JSON: {e}")
            return {}
