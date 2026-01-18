# Isolated Code Intelligence: System Architecture & Guide

This document explains the inner workings, capabilities, limits, and technology stack of the isolated Code Intelligence system integrated into this agent.

## 1. How It Works

The Code Intelligence system is a **hybrid RAG (Retrieval-Augmented Generation)** architecture that combines semantic search with structural knowledge.

### Multi-Layer Architecture
1.  **GraphRAG (Structural Knowledge)**:
    *   **Parsing**: The system uses **Tree-sitter** and language-specific AST (Abstract Syntax Tree) parsers. For specialized text patterns and as a fallback for high-speed analysis, it utilizes **Regular Expressions (Regex)** to identify signatures and structures.
    *   **Entity Extraction**: It identifies code entities such as `Functions`, `Classes`, and `Modules` using a combination of formal parsers and regex pattern matching, along with their metadata (file path, line numbers, code snippets).
    *   **Knowledge Graph**: Extracted entities are stored as nodes in a **Neo4j** database. This allows the agent to understand "Who calls this function?" and "Where is this class defined?" across different files.
2.  **Vector RAG (Semantic Search)**:
    *   **Chunking**: Code and generated documentation are broken into smaller, meaningful chunks.
    *   **Embeddings**: These chunks are converted into numerical vectors using **Sentence-Transformers**.
    *   **Vector Store**: Vectors are stored in **ChromaDB**, enabling "semantic search" where the agent can find relevant code even if the exact keywords don't match.
3.  **Workflow Orchestration (LangGraph)**:
    *   The entire process (Cloning → Analysis → Doc Generation → Embedding) is managed by a state machine built on **LangGraph**. This ensures a reliable, step-by-step execution and easy recovery from errors.
4.  **Incremental Analysis**:
    *   Instead of re-analyzing the whole repository every time, the system uses a **Change Detector**. It compares the current Git commit with the last processed commit to identify only the modified files, making updates significantly faster.

---

## 2. Capabilities

*   **Deep Codebase Q&A**: Ask complex questions like "How does the authentication flow work?" or "Where are the API endpoints defined?".
*   **Automatic Documentation**: Generates high-level repository overviews and detailed markdown documentation for individual files.
*   **Context-Aware Chat**: The agent uses retrieved snippets from both the Graph (relationships) and Vector (semantics) stores to provide accurate, context-rich answers.
*   **Confluence Integration**: Automatically pushes generated documentation to Atlassian Confluence, keeping your external docs in sync with your code.
*   **Entity Tracking**: Navigates call hierarchies and dependencies to explain how different parts of the system interact.

---

## 3. Max Limits & Constraints

To maintain performance and reliability, the following limits are in place:

*   **File Analysis Limit**: In a single pass, the system prioritizes and documents the **top 20 "important" files** (based on size, complexity, and entry-point patterns like `main.py` or `index.ts`).
*   **Language Support**: Optimized for **Python, JavaScript, TypeScript, Java, Go, Rust, C++, and C**.
*   **Incremental Window**: The system tracks changes via Git commits. If the `.git` history is lost or corrupted, a full re-analysis is required.
*   **Model Context**: While using high-performance models like `Qwen-2.5-Coder`, extremely large files (e.g., >5000 lines) may be truncated during the documentation generation phase.
*   **Storage**: Neo4j and ChromaDB are hosted locally or on specified instances. Query performance may degrade as the graph grows to hundreds of thousands of nodes (huge monorepos).

---

## 4. Technology Stack

*   **Orchestration**: `LangGraph`, `LangChain`
*   **AI Models**:
    *   **LLM**: `Qwen/Qwen2.5-Coder-32B` (or 7B) via `LiteLLM` / `HuggingFace`
    *   **Embeddings**: `Sentence-Transformers` (HuggingFace)
*   **Databases**:
    *   **Graph Store**: `Neo4j`
    *   **Vector Store**: `ChromaDB`
*   **Parsing & Git**:
    *   `Tree-sitter` (Multi-language AST parsing)
    *   `Regex` (re/regex) (Text processing, fallback parsing, and cleanup)
    *   `GitPython` (Commit tracking and cloning)
    *   `PyGithub` (GitHub API integration)
*   **Backend**: `FastAPI` (Python)
*   **Documentation Storage**: `Atlassian Python API` (Confluence)
