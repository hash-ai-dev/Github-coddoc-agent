import logging
from neo4j import GraphDatabase

logger = logging.getLogger("graph_store")

class GraphStoreManager:
    """
    Manages the connection to the Neo4j Knowledge Graph.
    Isolates all direct DB interactions.
    """
    def __init__(self, uri, username, password):
        self.uri = uri
        self.username = username
        self.password = password
        self.driver = None

    def connect(self):
        """Establishes connection to Neo4j."""
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.username, self.password))
            self.driver.verify_connectivity()
            logger.info("Successfully connected to Neo4j Graph Store.")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise e

    def close(self):
        if self.driver:
            self.driver.close()

    def get_driver(self):
        if not self.driver:
            raise Exception("Driver not connected. Call connect() first.")
        return self.driver

    def clear_graph_for_repo(self, repo_name):
        """Clears nodes related to a specific repo to allow re-ingestion."""
        query = """
        MATCH (n) 
        WHERE n.repo_name = $repo_name 
        DETACH DELETE n
        """
        if self.driver:
            with self.driver.session() as session:
                session.run(query, repo_name=repo_name)
            logger.info(f"Cleared graph data for repo: {repo_name}")
