import sys
import json
import time
import os
import argparse
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging to write to stderr so stdout is kept clean for JSON IPC
logging.basicConfig(stream=sys.stderr, level=logging.INFO)
logger = logging.getLogger("agent")

def send_message(type, payload):
    """Send a JSON message to Electron via stdout."""
    message = json.dumps({"type": type, "payload": payload})
    print(message, flush=True)

REPOS_FILE = "repos.json"
REPOS = []

def load_repos():
    global REPOS
    if os.path.exists(REPOS_FILE):
        try:
            with open(REPOS_FILE, 'r') as f:
                REPOS = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load repos: {e}")

def save_repos():
    try:
        with open(REPOS_FILE, 'w') as f:
            json.dump(REPOS, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save repos: {e}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="interactive", help="Run mode")
    args = parser.parse_args()

    send_message("system", {"status": "starting", "message": f"Python Agent initializing... (Env: {sys.executable})"})
    
    load_repos()
    
    # Initialize RAG components
    from core.vector_store import VectorStore
    from core.embedder import CodeEmbedder # Import Embedder
    from core.chat_engine import ChatEngine # Import ChatEngine

    vector_store = VectorStore()
    
    # Try to initialize embedder (might fail if model download fails)
    chat_engine = None
    try:
        embedder = CodeEmbedder()
        logger.info("Initialized CodeEmbedder and VectorStore")
        
        # We need keys to init ChatEngine, but we might not have them yet (loaded from env or passed later)
        # We'll init ChatEngine lazily or re-init when needed
        
    except Exception as e:
        logger.error(f"Failed to init RAG components: {e}")
        send_message("error", {"message": f"RAG Init Failed: {str(e)}"})

    # ... (startup checks) ...
    send_message("system", {"status": "ready", "message": "Agent Ready"})

    # Main Loop
    try:
        while True:
            line = sys.stdin.readline()
            if not line:
                break
            
            line = line.strip()
            if not line:
                continue

            try:
                command = json.loads(line)
                logger.info(f"Received command: {command}")
                
                cmd_type = command.get("type")
                
                if cmd_type == "ping":
                    send_message("pong", {"timestamp": time.time()})
                
                elif cmd_type == "ask_question":
                    # Handle Chat Request
                    data = command.get("data", {})
                    query = data.get("query", "")
                    history = data.get("history", []) # Get history
                    repo_url = data.get("repoUrl", "")
                    ui_settings = data.get("settings", {})
                    
                    if not query or not repo_url:
                        send_message("chat_response", {"answer": "Missing query or repository URL."})
                        continue

                    try:
                        # Get credentials
                        api_key = ui_settings.get('huggingfaceApiKey') or os.getenv('HUGGINGFACE_API_KEY', '')
                        model_name = ui_settings.get('modelName') or os.getenv('MODEL_NAME', 'Qwen/Qwen2.5-Coder-7B-Instruct')
                        
                        if not api_key:
                            send_message("chat_response", {"answer": "Hugging Face API Key is missing. Please check your settings."})
                            continue
                            
                        # Re-init chat engine with current creds if needed
                        if not chat_engine or chat_engine.api_key != api_key or chat_engine.model_name != model_name:
                            # Ensure we have embedder
                            if 'embedder' not in locals():
                                embedder = CodeEmbedder()
                            
                            chat_engine = ChatEngine(vector_store, embedder, api_key, model_name)
                        
                        # Ask with history
                        answer = chat_engine.ask(query, repo_url, history)
                        send_message("chat_response", {"answer": answer})
                        
                    except Exception as e:
                        logger.error(f"Chat Error: {e}")
                        send_message("chat_response", {"answer": f"Error: {str(e)}"})
                
                elif cmd_type == "list_repos":
                    # ... rest of existing handlers ...
                    # Return current list of repos
                    send_message("repos_list", {"repos": REPOS})

                elif cmd_type == "start_analysis":
                    # Real Analysis Task using LangGraph Workflow
                    data = command.get("data", {})
                    repo_url = data.get("repoUrl", "")
                    
                    # Add to history if not exists
                    existing = next((r for r in REPOS if r["url"] == repo_url), None)
                    if not existing:
                        new_repo = {
                            "id": str(time.time()),
                            "url": repo_url,
                            "status": "Analyzing...",
                            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
                        }
                        REPOS.append(new_repo)
                        save_repos()
                        send_message("repos_list", {"repos": REPOS})
                    
                    send_message("log", {"level": "info", "message": f"Starting real AI analysis for {repo_url}"})
                    
                    try:
                        # Import workflow
                        from core.workflow import DocumentationWorkflow
                        
                        # Progress callback
                        def progress_callback(status, progress, current_file):
                            send_message("progress", {"file": current_file or status, "percent": progress})
                            send_message("log", {"level": "info", "message": status})
                            
                        # Status/Preview callback
                        def status_callback(message, type="log"):
                            if type == "preview":
                                send_message("preview", {"content": message})
                            else:
                                send_message("log", {"level": "info", "message": message})
                        
                        # Load settings, prioritizing data from frontend
                        ui_settings = data.get('settings', {})
                        
                        config = {
                            'repo_url': repo_url,
                            'github_token': ui_settings.get('githubToken') or os.getenv('GITHUB_TOKEN', ''),
                            'hf_api_key': ui_settings.get('huggingfaceApiKey') or os.getenv('HUGGINGFACE_API_KEY', ''),
                            'model_name': ui_settings.get('modelName') or os.getenv('MODEL_NAME', 'Qwen/Qwen2.5-Coder-7B-Instruct'),
                            'confluence_url': ui_settings.get('confluenceUrl') or os.getenv('CONFLUENCE_URL', ''),
                            'confluence_email': ui_settings.get('confluenceEmail') or os.getenv('CONFLUENCE_EMAIL', ''),
                            'confluence_token': ui_settings.get('confluenceApiToken') or os.getenv('CONFLUENCE_API_TOKEN', ''),
                            'confluence_space': ui_settings.get('confluenceSpaceKey') or os.getenv('CONFLUENCE_SPACE_KEY', '')
                        }
                        
                        if ui_settings:
                            send_message("log", {"level": "info", "message": "Using credentials from App Settings"})
                        else:
                            send_message("log", {"level": "info", "message": "Using credentials from .env file"})
                        
                        # Validate required settings
                        if not config['hf_api_key']:
                            raise ValueError("Hugging Face API Key not configured. Please set it in Settings.")
                        
                        if not config['confluence_url'] or not config['confluence_token'] or not config['confluence_space']:
                            raise ValueError("Confluence credentials not configured. Please set them in Settings.")
                        
                        # Run workflow
                        workflow = DocumentationWorkflow(
                            progress_callback=progress_callback, 
                            status_callback=status_callback,
                            vector_store=vector_store
                        )
                        final_state = workflow.run(config)
                        
                        # Check for errors
                        if final_state.get('error'):
                            raise Exception(final_state['error'])
                        
                        # Send complete documentation to frontend for review
                        documentation = {
                            'repo_url': repo_url,
                            'repo_name': repo_url.rstrip('/').split('/')[-1].replace('.git', ''),
                            'overview': final_state.get('overview_doc', ''),
                            'file_docs': final_state.get('file_docs', {}),
                            'analysis': final_state.get('analysis', {})
                        }
                        
                        send_message("documentation_complete", {
                            "message": "Documentation generated successfully. Ready for review.",
                            "documentation": documentation
                        })
                        
                        # Update repo status to "Ready for Review"
                        for r in REPOS:
                            if r["url"] == repo_url:
                                r["status"] = "Ready for Review"
                                r["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
                        
                        save_repos()
                        send_message("repos_list", {"repos": REPOS})
                        
                    except Exception as e:
                        logger.error(f"Analysis failed: {e}")
                        send_message("error", {"message": f"Analysis failed: {str(e)}"})
                        
                        # Update repo status to failed
                        for r in REPOS:
                            if r["url"] == repo_url:
                                r["status"] = "Failed"
                                r["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
                        save_repos()
                        send_message("repos_list", {"repos": REPOS})
                
                elif cmd_type == "upload_to_confluence":
                    # Manual Confluence upload after user review
                    data = command.get("data", {})
                    repo_url = data.get("repoUrl", "")
                    repo_name = data.get("repoName", "")
                    overview = data.get("overview", "")
                    file_docs = data.get("fileDocs", {})
                    
                    send_message("log", {"level": "info", "message": f"Uploading documentation to Confluence..."})
                    
                    try:
                        from core.confluence_uploader import ConfluenceUploader
                        
                        # Load Confluence settings
                        ui_settings = data.get('settings', {})
                        confluence_url = ui_settings.get('confluenceUrl') or os.getenv('CONFLUENCE_URL', '')
                        confluence_email = ui_settings.get('confluenceEmail') or os.getenv('CONFLUENCE_EMAIL', '')
                        confluence_token = ui_settings.get('confluenceApiToken') or os.getenv('CONFLUENCE_API_TOKEN', '')
                        confluence_space = ui_settings.get('confluenceSpaceKey') or os.getenv('CONFLUENCE_SPACE_KEY', '')
                        
                        if not confluence_url or not confluence_token or not confluence_space:
                            raise ValueError("Confluence credentials not configured. Please set them in Settings.")
                        
                        uploader = ConfluenceUploader(
                            url=confluence_url,
                            api_token=confluence_token,
                            space_key=confluence_space,
                            username=confluence_email
                        )
                        
                        main_page = uploader.create_documentation_structure(
                            repo_name=repo_name,
                            overview=overview,
                            file_docs=file_docs
                        )
                        
                        # Update repo status
                        for r in REPOS:
                            if r["url"] == repo_url:
                                r["status"] = "Documented"
                                r["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
                                r["confluence_url"] = main_page.get('url', '')
                        
                        save_repos()
                        send_message("repos_list", {"repos": REPOS})
                        
                        send_message("upload_success", {
                            "message": "Documentation uploaded successfully!",
                            "confluence_url": main_page.get('url', '')
                        })
                        
                    except Exception as e:
                        logger.error(f"Confluence upload failed: {e}")
                        send_message("error", {"message": f"Confluence upload failed: {str(e)}"})
                
                elif cmd_type == "list_caches":
                    # Get list of cached repositories from vector store
                    try:
                        collections = vector_store.list_collections()
                        send_message("caches_list", {"caches": collections})
                    except Exception as e:
                        logger.error(f"Failed to list caches: {e}")
                        send_message("error", {"message": f"Failed to list caches: {str(e)}"})
                
                elif cmd_type == "clear_cache":
                    # Delete a specific repository collection from vector store
                    data = command.get("data", {})
                    repo_url = data.get("repoUrl", "")
                    
                    if not repo_url:
                        send_message("error", {"message": "Repository URL required to clear cache"})
                        continue
                        
                    try:
                        vector_store.delete_collection(repo_url)
                        # Also delete the documentation JSON
                        collection_name = vector_store._get_collection_name(repo_url)
                        doc_path = vector_store.persist_directory / f"{collection_name}_docs.json"
                        if doc_path.exists():
                            doc_path.unlink()
                            
                        logger.info(f"Cleared cache for {repo_url}")
                        
                        # Refresh list
                        collections = vector_store.list_collections()
                        send_message("caches_list", {"caches": collections})
                        send_message("cache_cleared", {"repoUrl": repo_url, "message": "Cache cleared successfully"})
                    except Exception as e:
                        logger.error(f"Failed to clear cache: {e}")
                        send_message("error", {"message": f"Failed to clear cache: {str(e)}"})
                
                elif cmd_type == "graphrag_connect":
                    # Connect to Neo4j for GraphRAG
                    data = command.get("data", {})
                    uri = data.get("uri") or data.get("neo4jUri")
                    username = data.get("username") or data.get("neo4jUser", "neo4j")
                    password = data.get("password") or data.get("neo4jPassword")
                    settings = data.get("settings", {})
                    
                    # Use shared HuggingFace credentials from main settings (can be overridden during ingestion)
                    hf_api_key = settings.get('huggingfaceApiKey') or os.getenv('HUGGINGFACE_API_KEY', '')
                    model_name = settings.get('modelName') or os.getenv('MODEL_NAME', 'Qwen/Qwen2.5-Coder-7B-Instruct')
                    
                    # Override deprecated 32B model if it comes from settings
                    if 'Qwen2.5-Coder-32B' in model_name or 'Qwen2.5-32B' in model_name:
                        logger.warning(f"Deprecated model {model_name} detected. Switching to Qwen/Qwen2.5-Coder-7B-Instruct")
                        model_name = 'Qwen/Qwen2.5-Coder-7B-Instruct'
                    
                    if not hf_api_key:
                        send_message("error", {"message": "HuggingFace API Key is required. Please set it in Settings."})
                        continue
                    
                    try:
                        from graph_rag.service import GraphService
                        
                        # Initialize service singleton if needed
                        logger.info("Initializing GraphService...")
                        if 'graph_service' not in locals():
                            graph_service = GraphService()
                        
                        success, msg = graph_service.connect(uri, username, password, hf_api_key, model_name)
                        
                        if success:
                            send_message("graphrag_status", {"status": "connected", "message": msg})
                            
                            # Auto-sync all known repositories
                            logger.info("[GraphRAG] Auto-syncing known repositories...")
                            try:
                                driver = graph_service.graph_manager.get_driver()
                                with driver.session() as session:
                                    result = session.run("""
                                        MATCH (r:Repository)
                                        RETURN r.repo_url as repo_url, r.local_path as local_path
                                    """)
                                    
                                    repos = [(record['repo_url'], record['local_path']) 
                                            for record in result if record['local_path']]
                                
                                if repos:
                                    send_message("graphrag_progress", {"message": f"Auto-syncing {len(repos)} known repositories..."})
                                    logger.info(f"[GraphRAG] Found {len(repos)} repositories to sync")
                                    
                                    for repo_url, local_path in repos:
                                        if os.path.exists(local_path):
                                            logger.info(f"[GraphRAG] Auto-syncing {repo_url}")
                                            
                                            def progress_cb(msg):
                                                send_message("graphrag_progress", {"message": msg})
                                            
                                            result = graph_service.analyze_changes(local_path, repo_url, progress_callback=progress_cb)
                                            
                                            if result.get('status') == 'updated':
                                                changes = result.get('total_changes', 0)
                                                send_message("graphrag_progress", {"message": f"✅ {repo_url}: Updated {changes} files"})
                                            elif result.get('status') == 'up_to_date':
                                                send_message("graphrag_progress", {"message": f"✅ {repo_url}: Up to date"})
                                        else:
                                            logger.warning(f"[GraphRAG] Local path not found: {local_path}")
                                    
                                    send_message("graphrag_status", {"status": "synced", "message": "All repositories synchronized"})
                                else:
                                    logger.info("[GraphRAG] No repositories found to sync")
                                    
                            except Exception as e:
                                logger.error(f"[GraphRAG] Auto-sync failed: {e}", exc_info=True)
                                # Don't fail connection if auto-sync fails
                        else:
                            send_message("error", {"message": msg})
                    except Exception as e:
                        logger.error(f"GraphRAG connection failed: {e}", exc_info=True)
                        send_message("error", {"message": f"Connection failed: {str(e)}"})

                elif cmd_type == "graphrag_clear":
                    # Clear all GraphRAG data from Neo4j
                    if 'graph_service' not in locals():
                        send_message("error", {"message": "Graph Service not connected."})
                        continue
                    
                    try:
                        logger.info("[GraphRAG] Clearing all data from Neo4j...")
                        send_message("graphrag_progress", {"message": "Clearing all GraphRAG data..."})
                        
                        driver = graph_service.graph_manager.get_driver()
                        with driver.session() as session:
                            # Delete all nodes and relationships
                            session.run("MATCH (n) DETACH DELETE n")
                        
                        logger.info("[GraphRAG] All data cleared successfully")
                        send_message("graphrag_status", {
                            "status": "cleared",
                            "message": "All GraphRAG data has been cleared. Ready for fresh ingestion."
                        })
                    except Exception as e:
                        logger.error(f"[GraphRAG] Clear failed: {e}", exc_info=True)
                        send_message("error", {"message": f"Failed to clear data: {str(e)}"})

                elif cmd_type == "graphrag_ingest":
                    # Start Ingestion
                    data = command.get("data", {})
                    repo_url = data.get("repoUrl")
                    # Assuming repo is cloned locally at a specific path, or we resolve it
                    # For this agent, we might need the direct path.
                    # Simplified: We expect the frontend to pass the local path or we resolve it via our internal map
                    # Since REPOS list has the URL, we might need to find where it's stored.
                    # The existing 'start_analysis' doesn't explicitly save the path in REPOS json, 
                    # but usually these agents clone to a temp dir.
                    # For safety, let's assume the user passes the 'path' or we use a known one.
                    # Existing agent usage implies 'repoUrl' is the key. 
                    # Ingest local repository
                    data = command.get("data", {})
                    repo_url = data.get("repoUrl")
                    repo_path = data.get("repoPath")
                    
                    if not repo_path or not repo_url:
                        send_message("error", {"message": "Repository path and URL are required"})
                        continue
                    
                    if 'graph_service' not in locals():
                        send_message("error", {"message": "Graph Service not connected."})
                        continue

                    def progress_cb(msg):
                        send_message("graphrag_progress", {"message": msg})
                    
                    try:
                        graph_service.ingest(repo_path, repo_url, progress_callback=progress_cb)
                        send_message("graphrag_status", {"status": "ingested", "message": "Repository ingested successfully"})
                    except Exception as e:
                        logger.error(f"Ingestion failed: {e}")
                        send_message("error", {"message": f"Ingestion failed: {str(e)}"})

                elif cmd_type == "graphrag_ingest_github":
                    # Ingest from GitHub repository
                    data = command.get("data", {})
                    repo_url = data.get("repoUrl")
                    github_token = data.get("githubToken")
                    branch = data.get("branch", "main")
                    
                    # Get isolated HF key from form if provided
                    form_hf_key = data.get("hfApiKey", "")
                    
                    if not repo_url:
                        send_message("error", {"message": "Repository URL is required"})
                        continue
                    
                    if 'graph_service' not in locals():
                        send_message("error", {"message": "Graph Service not connected."})
                        continue

                    def progress_cb(msg):
                        logger.info(f"[GraphRAG Ingestion] {msg}")
                        send_message("graphrag_progress", {"message": msg})
                    
                    try:
                        from graph_rag.github_client import GitHubClient
                        
                        logger.info(f"[GraphRAG] Starting GitHub ingestion for {repo_url}")
                        progress_cb("Initializing GitHub client...")
                        
                        # Initialize GitHub client
                        gh_client = GitHubClient(token=github_token)
                        
                        # Validate token if provided
                        if github_token:
                            logger.info("[GraphRAG] Validating GitHub token...")
                            valid, username = gh_client.validate_token()
                            if not valid:
                                logger.error("[GraphRAG] Invalid GitHub token")
                                send_message("error", {"message": "Invalid GitHub token"})
                                continue
                            progress_cb(f"Authenticated as {username}")
                            logger.info(f"[GraphRAG] Authenticated as {username}")
                        
                        # Determine local path
                        repo_name = repo_url.rstrip('/').split('/')[-1].replace('.git', '')
                        local_path = os.path.join("backend", "data", "repos", repo_name)
                        logger.info(f"[GraphRAG] Local path: {local_path}")
                        
                        progress_cb(f"Cloning/updating repository to {local_path}...")
                        
                        # Clone or update repository
                        logger.info(f"[GraphRAG] Calling clone_or_update_repo...")
                        success, commit_sha, message = gh_client.clone_or_update_repo(
                            repo_url, local_path, branch
                        )
                        
                        logger.info(f"[GraphRAG] Clone result: success={success}, sha={commit_sha}, msg={message}")
                        
                        if not success:
                            logger.error(f"[GraphRAG] Clone/update failed: {message}")
                            send_message("error", {"message": message})
                            continue
                        
                        progress_cb(message)
                        
                        # Update credentials if form provided an isolated key
                        if form_hf_key:
                            logger.info("[GraphRAG] Using isolated HuggingFace key from ingestion form")
                            progress_cb("Using isolated HuggingFace credentials...")
                            graph_service.update_credentials(form_hf_key)
                        else:
                            logger.info("[GraphRAG] Using shared HuggingFace credentials from settings")
                        
                        # Analyze changes and update incrementally
                        logger.info(f"[GraphRAG] Analyzing changes in {local_path}")
                        progress_cb("Analyzing repository for changes...")
                        
                        result = graph_service.analyze_changes(local_path, repo_url, progress_callback=progress_cb)
                        
                        if result.get('status') == 'error':
                            logger.error(f"[GraphRAG] Change analysis failed: {result.get('error')}")
                            send_message("error", {"message": f"Change analysis failed: {result.get('error')}"})
                            continue
                        
                        logger.info(f"[GraphRAG] Analysis complete: {result}")
                        
                        # Prepare success message based on result
                        if result.get('status') == 'up_to_date':
                            message = f"Repository is up to date (commit: {commit_sha[:7]})"
                        else:
                            changes = result.get('total_changes', 0)
                            message = f"Updated {changes} changed files (commit: {commit_sha[:7]})"
                        
                        # Store repository metadata in Neo4j
                        logger.info("[GraphRAG] Storing repository metadata...")
                        driver = graph_service.graph_manager.get_driver()
                        with driver.session() as session:
                            session.run("""
                                MERGE (r:Repository {repo_url: $repo_url})
                                SET r.repo_name = $repo_name,
                                    r.last_commit_sha = $commit_sha,
                                    r.last_synced = timestamp(),
                                    r.branch = $branch,
                                    r.local_path = $local_path
                            """, repo_url=repo_url, repo_name=repo_name, 
                               commit_sha=commit_sha, branch=branch, local_path=local_path)
                        
                        logger.info("[GraphRAG] Repository metadata stored")
                        send_message("graphrag_status", {
                            "status": "ingested", 
                            "message": message
                        })
                        
                    except Exception as e:
                        logger.error(f"[GraphRAG] GitHub ingestion failed: {e}", exc_info=True)
                        send_message("error", {"message": f"GitHub ingestion failed: {str(e)}"})

                elif cmd_type == "graphrag_query":
                    data = command.get("data", {})
                    question = data.get("query")
                    
                    if 'graph_service' not in locals():
                         send_message("error", {"message": "Graph Service not connected."})
                         continue

                    answer = graph_service.query(question)
                    send_message("graphrag_response", {"answer": answer})

                else:
                    send_message("error", {"message": f"Unknown command: {cmd_type}"})

            except json.JSONDecodeError:
                logger.error("Failed to decode JSON")
            except Exception as e:
                logger.error(f"Error processing command: {e}")
                send_message("error", {"message": str(e)})

    except KeyboardInterrupt:
        logger.info("Agent stopping...")

if __name__ == "__main__":
    main()
