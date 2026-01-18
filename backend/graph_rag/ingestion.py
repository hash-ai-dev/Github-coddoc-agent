import os
import logging
from tree_sitter_languages import get_language, get_parser
from graph_rag.graph_store import GraphStoreManager

logger = logging.getLogger("graph_ingestion")

# Language mappings
EXT_TO_LANG = {
    '.py': 'python',
    '.js': 'javascript',
    '.jsx': 'javascript',
    '.ts': 'typescript',
    '.tsx': 'typescript',
    '.java': 'java',
    '.go': 'go',
    '.rs': 'rust',
    '.cpp': 'cpp',
    '.c': 'c',
}

class CodeIngestion:
    def __init__(self, graph_manager: GraphStoreManager, embedder_model=None):
        self.graph_manager = graph_manager
        self.embedder_model = embedder_model
        # Cache parsers
        self.parsers = {}

    def parse_file_simple(self, file_path, repo_name):
        """
        Parse a file using simple AST/regex parsing instead of tree-sitter.
        Returns a list of entity dictionaries for the graph.
        """
        ext = os.path.splitext(file_path)[1].lower()
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                code = f.read()
            
            entities = []
            
            # Python files - use built-in AST
            if ext == '.py':
                entities = self._parse_python(file_path, code, repo_name)
            
            # JavaScript/TypeScript - use regex patterns
            elif ext in ['.js', '.jsx', '.ts', '.tsx']:
                entities = self._parse_javascript(file_path, code, repo_name)
            
            return entities
            
        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
            return []
    
    def _parse_python(self, file_path, code, repo_name):
        """Parse Python file using AST."""
        import ast
        entities = []
        
        try:
            tree = ast.parse(code)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    entities.append({
                        "metadata": {
                            "file_path": file_path,
                            "repo_name": repo_name,
                            "entity_type": "function",
                            "entity_name": node.name,
                            "snippet": f"def {node.name}(...)"
                        }
                    })
                elif isinstance(node, ast.ClassDef):
                    entities.append({
                        "metadata": {
                            "file_path": file_path,
                            "repo_name": repo_name,
                            "entity_type": "class",
                            "entity_name": node.name,
                            "snippet": f"class {node.name}"
                        }
                    })
        except SyntaxError as e:
            logger.warning(f"Syntax error in {file_path}: {e}")
        
        return entities
    
    def _parse_javascript(self, file_path, code, repo_name):
        """Parse JavaScript/TypeScript file using regex."""
        import re
        entities = []
        
        # Match function declarations: function name(...) or const name = (...) =>
        func_pattern = r'(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>)'
        
        # Match class declarations: class Name
        class_pattern = r'class\s+(\w+)'
        
        for match in re.finditer(func_pattern, code):
            name = match.group(1) or match.group(2)
            if name:
                entities.append({
                    "metadata": {
                        "file_path": file_path,
                        "repo_name": repo_name,
                        "entity_type": "function",
                        "entity_name": name,
                        "snippet": match.group(0)[:100]
                    }
                })
        
        for match in re.finditer(class_pattern, code):
            name = match.group(1)
            entities.append({
                "metadata": {
                    "file_path": file_path,
                    "repo_name": repo_name,
                    "entity_type": "class",
                    "entity_name": name,
                    "snippet": match.group(0)
                }
            })
        
        return entities

    def ingest_repo(self, repo_path, repo_url, progress_callback=None):
        """
        Walks the repo, parses files, and builds the Knowledge Graph.
        """
        logger.info(f"Starting ingestion for {repo_url} at {repo_path}")
        
        all_entities = []
        
        # Walk through the repository
        logger.info(f"Walking through {repo_path}...")
        file_count = 0
        
        for root, _, files in os.walk(repo_path):
            # Skip common ignored directories and hidden directories
            if 'node_modules' in root or '__pycache__' in root or '.git' in root or \
               any(part.startswith('.') for part in root.split(os.sep)):
                continue
                
            for file in files:
                # Skip hidden files
                if file.startswith('.'):
                    continue
                    
                file_path = os.path.join(root, file)
                ext = os.path.splitext(file)[1].lower()
                
                # Check if we support this file type
                if ext in ['.py', '.js', '.jsx', '.ts', '.tsx']:
                    file_count += 1
                    logger.info(f"Processing file: {file_path}")
                    entities = self.parse_file_simple(file_path, repo_url)
                    if entities:
                        all_entities.extend(entities)
                    
                    if progress_callback and file_count % 10 == 0:
                        progress_callback(f"Parsed {file_count} files...")

        logger.info(f"Processed {file_count} files. Extracted {len(all_entities)} entities.")

        if not all_entities:
            logger.warning("No code entities found.")
            if progress_callback:
                progress_callback("⚠️ No code entities found in repository")
            return
        
        # Log summary statistics
        entity_types = {}
        for entity in all_entities:
            etype = entity.get('metadata', {}).get('entity_type', 'unknown')
            entity_types[etype] = entity_types.get(etype, 0) + 1
        
        summary = ", ".join([f"{count} {etype}s" for etype, count in entity_types.items()])
        logger.info(f"Entity summary: {summary}")
        if progress_callback:
            progress_callback(f"Found {len(all_entities)} entities: {summary}")
        
        logger.info(f"Extracted {len(all_entities)} entities. Writing to Neo4j...")
        if progress_callback:
            progress_callback("Building Knowledge Graph in Neo4j...")

        try:
            # Write entities directly to Neo4j
            driver = self.graph_manager.get_driver()
            
            with driver.session() as session:
                # Create nodes for each entity
                for doc in all_entities:
                    metadata = doc.metadata
                    
                    # Create a node with properties
                    cypher = """
                    CREATE (n:CodeEntity {
                        entity_name: $name,
                        entity_type: $type,
                        file_path: $file_path,
                        repo_name: $repo_name,
                        snippet: $snippet
                    })
                    """
                    
                    session.run(cypher, 
                        name=metadata.get('entity_name', ''),
                        type=metadata.get('entity_type', ''),
                        file_path=metadata.get('file_path', ''),
                        repo_name=metadata.get('repo_name', ''),
                        snippet=metadata.get('snippet', '')
                    )
            
            logger.info(f"Successfully wrote {len(all_entities)} entities to Neo4j")
            if progress_callback:
                progress_callback(f"✅ Graph built successfully! {len(all_entities)} entities stored in Neo4j")
                
        except Exception as e:
            logger.error(f"Failed to write to Neo4j: {e}", exc_info=True)
            if progress_callback:
                progress_callback(f"❌ Error building graph: {str(e)}")
            raise e

    def ingest_files(self, repo_path, repo_name, file_paths, progress_callback=None):
        """
        Ingest only specific files into the Knowledge Graph.
        Used for incremental updates.
        
        Args:
            repo_path: Base path of the repository
            repo_name: Repository name
            file_paths: List of relative file paths to ingest
            progress_callback: Optional progress callback
        """
        logger.info(f"Starting selective ingestion for {len(file_paths)} files")
        
        all_entities = []
        processed_count = 0
        
        for rel_path in file_paths:
            full_path = os.path.join(repo_path, rel_path)
            
            # Check if file exists and we support it
            if not os.path.exists(full_path):
                logger.warning(f"File not found: {full_path}")
                continue
            
            ext = os.path.splitext(full_path)[1].lower()
            if ext not in ['.py', '.js', '.jsx', '.ts', '.tsx']:
                logger.debug(f"Unsupported file type: {rel_path}")
                continue
            
            processed_count += 1
            logger.info(f"Processing file: {rel_path}")
            entities = self.parse_file_simple(full_path, repo_name)
            
            if entities:
                all_entities.extend(entities)
            
            if progress_callback and processed_count % 5 == 0:
                progress_callback(f"Processed {processed_count}/{len(file_paths)} files...")
        
        logger.info(f"Processed {processed_count} files. Extracted {len(all_entities)} entities.")
        
        if not all_entities:
            logger.warning("No code entities found in changed files.")
            if progress_callback:
                progress_callback("No code entities found in changed files")
            return
        
        # Write to Neo4j
        logger.info(f"Writing {len(all_entities)} entities to Neo4j...")
        if progress_callback:
            progress_callback(f"Updating Knowledge Graph with {len(all_entities)} entities...")
        
        try:
            driver = self.graph_manager.get_driver()
            
            with driver.session() as session:
                for doc in all_entities:
                    metadata = doc['metadata']
                    
                    cypher = """
                    CREATE (n:CodeEntity {
                        entity_name: $name,
                        entity_type: $type,
                        file_path: $file_path,
                        repo_name: $repo_name,
                        snippet: $snippet
                    })
                    """
                    
                    session.run(cypher, 
                        name=metadata.get('entity_name', ''),
                        type=metadata.get('entity_type', ''),
                        file_path=metadata.get('file_path', ''),
                        repo_name=metadata.get('repo_name', ''),
                        snippet=metadata.get('snippet', '')
                    )
            
            logger.info(f"Successfully wrote {len(all_entities)} entities to Neo4j")
            if progress_callback:
                progress_callback(f"✅ Updated {len(all_entities)} entities in Knowledge Graph")
                
        except Exception as e:
            logger.error(f"Failed to write to Neo4j: {e}", exc_info=True)
            if progress_callback:
                progress_callback(f"❌ Error updating graph: {str(e)}")
            raise e

