"""
Test script for DocFormatter
Tests special character handling in documentation formatting.
"""

from backend.core.doc_formatter import DocFormatter

# Test markdown with special characters
test_markdown = """
# Project Overview Documentation

## 1. Project Purpose and Description

This project is a full-stack web application designed to integrate various functionalities including file management and interaction with a Large Language Model (LLM). The application provides a user-friendly interface for uploading, managing, and retrieving files while also offering capabilities to interact with an LLM through a defined API. This setup is ideal for developers seeking to build applications that require both robust backend services and a modern frontend interface.

## 2. Key Technologies and Languages Used

### Programming Languages

- Python (backend)
- JavaScript/TypeScript (frontend)
- SQL (database)

### Code Examples

Here's a function with special characters:

```python
def __init__(self, name: str):
    '''Initialize with name'''
    self.name = name
    print(f"Hello '{name}'")
    # This is a comment with # hash
```

### Special Characters Test

- Single quotes: 'hello'
- Double quotes: "world"
- Hash symbols: #tag #python #code
- Backticks: `code` and ``double``
- Asterisks: *italic* and **bold**
- Underscores: _emphasis_ and __strong__
"""

print("Testing DocFormatter...")
print("=" * 80)

# Test 1: Sanitize markdown
print("\n1. Testing sanitize_markdown():")
sanitized = DocFormatter.sanitize_markdown(test_markdown)
print(sanitized[:500])
print(f"\nLength: {len(sanitized)} characters")

# Test 2: JSON save/load
print("\n2. Testing JSON save/load:")
test_data = {
    "overview_doc": test_markdown,
    "file_docs": {
        "test.py": "# Test file\n\nThis has 'quotes' and \"double quotes\" and #hashes"
    }
}

import tempfile
import os

with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
    temp_path = f.name

try:
    # Save
    success = DocFormatter.save_to_json(test_data, temp_path)
    print(f"Save successful: {success}")
    
    # Load
    loaded_data = DocFormatter.load_from_json(temp_path)
    print(f"Load successful: {loaded_data is not None}")
    
    # Verify content preserved
    if loaded_data:
        original_overview = test_data["overview_doc"]
        loaded_overview = loaded_data.get("overview_doc", "")
        print(f"Content preserved: {original_overview == loaded_overview}")
        
        # Check special characters
        print("Contains single quotes:", "'" in loaded_overview)
        print("Contains double quotes:", '"' in loaded_overview)
        print(f"Contains hashes: {'#' in loaded_overview}")
        
finally:
    # Cleanup
    if os.path.exists(temp_path):
        os.remove(temp_path)

# Test 3: Confluence conversion
print("\n3. Testing markdown_to_confluence():")
confluence_html = DocFormatter.markdown_to_confluence(test_markdown)
print(confluence_html[:500])
print(f"\nContains <h1>: {'<h1>' in confluence_html}")
print(f"Contains <code>: {'<code>' in confluence_html}")
print(f"Contains CDATA: {'CDATA' in confluence_html}")

print("\n" + "=" * 80)
print("All tests completed!")
