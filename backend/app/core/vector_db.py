"""
Vector Database Service using ChromaDB
Provides RAG capabilities for the EM Roadmap content
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
import asyncio
from pathlib import Path

import openai
import chromadb
from chromadb.config import Settings
from opentelemetry import trace

from app.core.mcp_protocol import mcp_registry, MCPContext, ContextType


class OpenAIEmbeddingFunction:
    """Real OpenAI embedding function for ChromaDB"""
    
    def __init__(self, api_key: str, model_name: str = "text-embedding-3-small"):
        self.api_key = api_key
        self.model_name = model_name
        self.client = openai.OpenAI(api_key=api_key)

    def name(self) -> str:
        """ChromaDB embedding function identifier."""
        return "openai"

    def get_config(self) -> Dict[str, Any]:
        """Optional config for ChromaDB embedding function compatibility."""
        return {"model_name": self.model_name}
    
    def __call__(self, input: List[str]) -> List[List[float]]:
        """Generate embeddings for input texts"""
        try:
            response = self.client.embeddings.create(
                model=self.model_name,
                input=input
            )
            return [data.embedding for data in response.data]
        except Exception as e:
            logging.error(f"Error generating embeddings: {str(e)}")
            raise


class VectorDBService:
    """Vector database service for RAG operations"""
    
    def __init__(self, collection_name: str = "em_roadmap"):
        self.collection_name = collection_name
        self.tracer = trace.get_tracer(__name__)
        self.logger = logging.getLogger("vector_db")
        
        # Initialize real ChromaDB client
        chroma_path = os.getenv("CHROMA_DB_PATH", "./chroma_db")
        self.client = chromadb.PersistentClient(
            path=chroma_path,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Initialize OpenAI embedding function
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        self.embedding_function = OpenAIEmbeddingFunction(
            api_key=openai_api_key,
            model_name="text-embedding-3-small"
        )
        
        # Get or create collection
        self.collection = self._get_or_create_collection()
        
        self.logger.info(f"VectorDB service initialized with collection: {collection_name}")
        self.logger.info(f"ChromaDB path: {chroma_path}")
    
    def _get_or_create_collection(self):
        """Get or create ChromaDB collection"""
        try:
            collection = self.client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=self.embedding_function,
                metadata={"description": "EM Roadmap content collection"}
            )
            self.logger.info(f"Using collection: {self.collection_name} ({collection.count()} documents)")
            return collection
        except Exception as e:
            self.logger.error(f"Error getting/creating collection: {str(e)}")
            raise
    
    async def index_content(self, content: Dict[str, Any]) -> bool:
        """Index content in vector database"""
        with self.tracer.start_as_current_span("vector_db.index_content") as span:
            span.set_attributes({
                "content.type": content.get("type", "unknown"),
                "content.id": content.get("id", "unknown")
            })
            
            try:
                # Prepare documents for indexing
                documents = []
                metadatas = []
                ids = []
                
                if content.get("type") == "roadmap_section":
                    # Index roadmap section
                    section_data = content.get("data", {})
                    
                    # Main section content
                    if section_data.get("content"):
                        documents.append(section_data["content"])
                        metadatas.append({
                            "type": "section",
                            "section_id": content.get("id"),
                            "title": section_data.get("title", ""),
                            "tags": ",".join(section_data.get("tags", [])),
                            "level": section_data.get("level", 1),
                            "indexed_at": datetime.now(timezone.utc).isoformat()
                        })
                        ids.append(f"section_{content.get('id')}")
                    
                    # Index subsections
                    for subsection in section_data.get("subsections", []):
                        if subsection.get("content"):
                            documents.append(subsection["content"])
                            metadatas.append({
                                "type": "subsection",
                                "section_id": content.get("id"),
                                "subsection_id": subsection.get("id"),
                                "title": subsection.get("title", ""),
                                "tags": ",".join(subsection.get("tags", [])),
                                "level": subsection.get("level", 2),
                                "indexed_at": datetime.now(timezone.utc).isoformat()
                            })
                            ids.append(f"subsection_{subsection.get('id')}")
                
                elif content.get("type") == "learning_path":
                    # Index learning path
                    path_data = content.get("data", {})
                    
                    if path_data.get("description"):
                        documents.append(path_data["description"])
                        metadatas.append({
                            "type": "learning_path",
                            "path_id": content.get("id"),
                            "title": path_data.get("title", ""),
                            "difficulty": path_data.get("difficulty", "beginner"),
                            "duration": path_data.get("duration", ""),
                            "indexed_at": datetime.now(timezone.utc).isoformat()
                        })
                        ids.append(f"path_{content.get('id')}")
                
                # Add to ChromaDB
                if documents:
                    self.collection.add(
                        documents=documents,
                        metadatas=metadatas,
                        ids=ids
                    )
                    
                    span.set_attributes({
                        "documents_indexed": len(documents),
                        "indexing_success": True
                    })
                    
                    self.logger.info(f"Successfully indexed {len(documents)} documents")
                    return True
                else:
                    self.logger.warning("No documents to index")
                    return False
                    
            except Exception as e:
                self.logger.error(f"Error indexing content: {str(e)}")
                span.record_exception(e)
                span.set_attributes({
                    "indexing_success": False,
                    "error": str(e)
                })
                return False
    
    async def search_similar_content(
        self, 
        query: str, 
        n_results: int = 5,
        content_type: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar content"""
        with self.tracer.start_as_current_span("vector_db.search") as span:
            span.set_attributes({
                "query_length": len(query),
                "n_results": n_results,
                "content_type": content_type or "all"
            })
            
            try:
                # Build where clause for filtering
                where_clause = {}
                if content_type:
                    where_clause["type"] = content_type
                if filters:
                    where_clause.update(filters)
                
                # Query ChromaDB
                results = self.collection.query(
                    query_texts=[query],
                    n_results=n_results,
                    where=where_clause if where_clause else None
                )
                
                # Format results
                formatted_results = []
                if results["ids"] and results["ids"][0]:
                    for i, doc_id in enumerate(results["ids"][0]):
                        formatted_results.append({
                            "id": doc_id,
                            "content": results["documents"][0][i] if results["documents"] and results["documents"][0] else "",
                            "metadata": results["metadatas"][0][i] if results["metadatas"] and results["metadatas"][0] else {},
                            "distance": results["distances"][0][i] if results["distances"] and results["distances"][0] else 0.0
                        })
                
                span.set_attributes({
                    "results_count": len(formatted_results),
                    "search_success": True
                })
                
                self.logger.info(f"Found {len(formatted_results)} similar documents")
                return formatted_results
                
            except Exception as e:
                self.logger.error(f"Error searching vector database: {str(e)}")
                span.record_exception(e)
                span.set_attributes({
                    "search_success": False,
                    "error": str(e)
                })
                return []
    
    async def index_em_roadmap_content(self, content_dir: str) -> int:
        """Index all EM roadmap content from directory"""
        self.logger.info(f"Starting to index EM roadmap content from: {content_dir}")
        
        indexed_count = 0
        content_path = Path(content_dir)
        
        if not content_path.exists():
            self.logger.error(f"Content directory does not exist: {content_dir}")
            return 0
        
        try:
            # Index all JSON files
            for json_file in content_path.glob("*.json"):
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        content = json.load(f)
                    
                    success = await self.index_content(content)
                    if success:
                        indexed_count += 1
                        self.logger.info(f"Indexed: {json_file.name}")
                    
                except Exception as e:
                    self.logger.error(f"Error indexing file {json_file}: {str(e)}")
            
            self.logger.info(f"Successfully indexed {indexed_count} content files")
            return indexed_count
            
        except Exception as e:
            self.logger.error(f"Error indexing EM roadmap content: {str(e)}")
            return 0
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics"""
        try:
            count = self.collection.count()
            return {
                "collection_name": self.collection_name,
                "document_count": count,
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "embedding_model": "text-embedding-3-small",
                "database_type": "ChromaDB"
            }
        except Exception as e:
            self.logger.error(f"Error getting collection stats: {str(e)}")
            return {"error": str(e)}
    
    async def delete_by_metadata(self, metadata_filter: Dict[str, Any]) -> bool:
        """Delete documents by metadata filter"""
        try:
            # Get documents matching filter
            results = self.collection.get(
                where=metadata_filter,
                include=["metadatas", "documents"]
            )
            
            if results["ids"]:
                # Delete matching documents
                self.collection.delete(ids=results["ids"])
                self.logger.info(f"Deleted {len(results['ids'])} documents")
                return True
            else:
                self.logger.info("No documents found matching filter")
                return True
                
        except Exception as e:
            self.logger.error(f"Error deleting documents: {str(e)}")
            return False
    
    async def update_document(
        self, 
        doc_id: str, 
        new_content: str, 
        new_metadata: Dict[str, Any]
    ) -> bool:
        """Update an existing document"""
        try:
            # Delete existing document
            self.collection.delete(ids=[doc_id])
            
            # Add updated document
            self.collection.add(
                documents=[new_content],
                metadatas=[new_metadata],
                ids=[doc_id]
            )
            
            self.logger.info(f"Updated document: {doc_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating document: {str(e)}")
            return False


# Lazy-initialized global instance to avoid import-time crashes
# when OPENAI_API_KEY or ChromaDB is not available
_vector_db_service = None


def _get_vector_db_service() -> VectorDBService:
    """Get or create the global VectorDBService instance"""
    global _vector_db_service
    if _vector_db_service is None:
        _vector_db_service = VectorDBService()
    return _vector_db_service


class _VectorDBProxy:
    """Proxy that lazily initializes VectorDBService on first attribute access"""
    def __getattr__(self, name):
        return getattr(_get_vector_db_service(), name)


vector_db_service = _VectorDBProxy()
