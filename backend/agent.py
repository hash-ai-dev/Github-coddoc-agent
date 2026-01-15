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

    send_message("system", {"status": "starting", "message": "Python Agent initializing... (DEBUG: v3-persistence)"})
    
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
                        model_name = ui_settings.get('modelName') or os.getenv('MODEL_NAME', 'Qwen/Qwen2.5-Coder-32B-Instruct')
                        
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
                            'model_name': ui_settings.get('modelName') or os.getenv('MODEL_NAME', 'Qwen/Qwen2.5-Coder-32B-Instruct'),
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
