"""
Chat Engine Module
Handles RAG-based question answering using VectorStore and Hugging Face API.
"""

import logging
from typing import List, Dict, Optional
import requests
from .vector_store import VectorStore
from .embedder import CodeEmbedder

logger = logging.getLogger(__name__)

class ChatEngine:
    """RAG-based Chat Engine."""
    
    API_URL = "https://router.huggingface.co/v1/chat/completions"

    def __init__(self, vector_store: VectorStore, embedder: CodeEmbedder, api_key: str, model_name: str):
        """
        Initialize Chat Engine.
        
        Args:
            vector_store: Initialized VectorStore instance
            embedder: Initialized CodeEmbedder instance
            api_key: Hugging Face API Key
            model_name: Hugging Face Model Name
        """
        self.vector_store = vector_store
        self.embedder = embedder
        self.api_key = api_key
        self.model_name = model_name
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def ask(self, query: str, repo_url: str, history: List[Dict[str, str]] = None) -> str:
        """
        Answer a question about a repository using RAG with history context.
        """
        if history is None:
            history = []
            
        try:
            logger.info(f"Processing chat query: '{query}' for repo: '{repo_url}' with {len(history)} history items")
            
            # 1. Embed query
            query_embedding = self.embedder.embed_query(query)
            logger.info("Query embedding generated.")
            
            # 2. Retrieve relevant context
            chunks = self.vector_store.search_similar(
                repo_url=repo_url,
                query_embedding=query_embedding,
                top_k=5
            )
            
            logger.info(f"Retrieved {len(chunks)} context chunks from vector store.")
            
            if not chunks:
                logger.warning("No chunks found. Returning default message.")
                return "I couldn't find any relevant code in the repository to answer your question. Make sure the repository has been analyzed and indexed."
            
            # 3. Construct Context
            context_str = ""
            for i, chunk in enumerate(chunks):
                file_path = chunk['metadata'].get('file_path', 'unknown')
                content = chunk['content']
                context_str += f"\n[Context {i+1}] File: {file_path}\nCode:\n```\n{content}\n```\n"
            
            # 4. Construct Prompt
            
            # Format history string
            history_str = ""
            if history:
                history_str = "Conversation History:\n"
                for msg in history:
                    role = "User" if msg.get("role") == "user" else "Assistant"
                    content = msg.get("content", "").replace("\n", " ")
                    history_str += f"{role}: {content}\n"
                history_str += "\n"
            
            prompt = f"""You are an expert software developer and code analyst. 
Answer the user's question based strictly on the provided code snippets from the repository.

{history_str}User Question: {query}

Relevant Code Context:
{context_str}

Instructions:
- Answer clearly and concisely.
- Cite the file names when referring to specific logic.
- If the answer is not in the context, admit that you don't know based on the available information.
- Provide code examples if helpful, using the context provided.
"""
            
            # 5. Call LLM
            logger.info(f"Querying LLM for: {query}")
            response = self._call_model(prompt)
            return response

        except Exception as e:
            logger.error(f"Chat failed: {e}")
            return f"Error occurred while processing your request: {str(e)}"

    def _call_model(self, prompt: str) -> str:
        """Call Hugging Face Inference API."""
        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 1000,
            "temperature": 0.5
        }
        
        try:
            logger.info(f"Sending request to HF API model: {self.model_name}")
            response = requests.post(
                self.API_URL,
                headers=self.headers,
                json=payload,
                timeout=60
            )
            
            logger.info(f"HF API Response Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                if isinstance(result, dict) and 'choices' in result:
                    choices = result.get('choices', [])
                    if choices:
                        content = choices[0].get('message', {}).get('content', '')
                        logger.info("Successfully received answer from LLM.")
                        return content
            
            error_msg = f"API Error {response.status_code}: {response.text}"
            logger.error(error_msg)
            return "I'm having trouble connecting to the AI model right now. Please try again."
            
        except Exception as e:
            logger.error(f"Model call failed: {e}")
            return "Failed to communicate with the AI model."
