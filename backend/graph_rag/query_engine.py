import logging
import requests
from graph_rag.graph_store import GraphStoreManager
from graph_rag.prompts import BUSINESS_SYSTEM_PROMPT

logger = logging.getLogger("graph_query")

class GraphQueryEngine:
    def __init__(self, graph_manager: GraphStoreManager, hf_token, model_name="Qwen/Qwen2.5-Coder-7B-Instruct"):
        self.graph_manager = graph_manager
        self.hf_token = hf_token
        self.model_name = model_name
        self.index = None
        
        # Use Hugging Face Router API (OpenAI-compatible)
        self.api_url = "https://router.huggingface.co/v1/chat/completions"

    def get_index(self):
        """Placeholder - we query Neo4j directly now."""
        return True

    def _call_llm(self, prompt):
        """Direct HuggingFace API call using Router API."""
        headers = {
            "Authorization": f"Bearer {self.hf_token}",
            "Content-Type": "application/json"
        }
        
        # Chat completions format
        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            "max_tokens": 1000,
            "temperature": 0.7
        }
        
        try:
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=60)
            
            if response.status_code != 200:
                logger.error(f"API Error {response.status_code}: {response.text}")
                return f"Error from LLM (Status {response.status_code}): {response.text}"
                
            result = response.json()
            
            # Parse OpenAI-like response
            if 'choices' in result and len(result['choices']) > 0:
                content = result['choices'][0].get('message', {}).get('content', '')
                if content:
                    return content
            
            # Fallback
            return str(result)
            
        except Exception as e:
            logger.error(f"LLM API call failed: {e}")
            return f"Error calling LLM: {str(e)}"

    def query(self, query_text):
        """
        Executes a GraphRAG query using the knowledge graph.
        """
        try:
            # Get graph context
            index = self.get_index()
            if not index:
                return "System Error: Graph Index not loaded."
            
            # Retrieve relevant graph nodes/relationships
            # For simplicity, we'll query the graph store directly
            driver = self.graph_manager.get_driver()
            
            # Simple Cypher query to get relevant entities
            cypher_query = """
            MATCH (n)
            WHERE n.entity_name IS NOT NULL
            RETURN n.entity_name as name, n.entity_type as type, n.file_path as file
            LIMIT 20
            """
            
            context_items = []
            with driver.session() as session:
                result = session.run(cypher_query)
                for record in result:
                    context_items.append(f"{record['type']}: {record['name']} in {record['file']}")
            
            # Build context-aware prompt
            context = "\n".join(context_items) if context_items else "No graph data available yet."
            
            full_prompt = f"""{BUSINESS_SYSTEM_PROMPT}

**Available Code Entities:**
{context}

**User Question:** {query_text}

**Instructions:** Provide a business-friendly explanation based on the code structure shown above."""
            
            # Call LLM
            answer = self._call_llm(full_prompt)
            return answer
            
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            return f"Error executing query: {str(e)}"
