import json
import logging
import math
from typing import List, Dict, Any, Optional, Tuple
import google.generativeai as genai
from ..config import settings
from ..models import Item as ItemModel, ItemEmbedding
import asyncio
import time

log = logging.getLogger("uvicorn")

class GeminiEmbeddingService:
    def __init__(self):
        if settings.google_ai_api_key:
            genai.configure(api_key=settings.google_ai_api_key)
            self.is_configured = True
            log.info(f"Gemini Embedding service initialized with model: {settings.embedding_model}")
        else:
            self.is_configured = False
            log.warning("Gemini Embedding service not configured - missing GOOGLE_AI_API_KEY")

    def _prepare_item_text(self, item: ItemModel) -> str:
        """Prepare item data as text for embedding optimized for tags and captions."""
        parts = []
        
        # Tags are most important - repeat them for emphasis
        if item.tags:
            # Add tags multiple times to increase their weight
            tags_lower = [tag.lower() for tag in item.tags]
            parts.append(' '.join(tags_lower))  # Primary tags
            parts.append(' '.join(tags_lower))  # Repeat for emphasis
            
        if item.notes:
            parts.append(item.notes)
            
        if item.creator:
            parts.append(f"creator: {item.creator}")

        return ' '.join(parts) if parts else ""

    def _normalize_vector(self, vector: List[float]) -> List[float]:
        """Normalize a vector for better cosine similarity."""
        magnitude = math.sqrt(sum(x * x for x in vector))
        if magnitude == 0:
            return vector
        return [x / magnitude for x in vector]

    async def generate_item_embedding(self, item: ItemModel) -> Optional[ItemEmbedding]:
        """Generate embedding for a single item."""
        if not self.is_configured:
            log.error("Embedding service not configured")
            return None

        text = self._prepare_item_text(item)
        if not text:
            log.warning(f"Item {item.id} has no text content for embedding")
            return None

        try:
            # Generate embedding with the correct API
            result = genai.embed_content(
                model=settings.embedding_model,
                content=text,
                task_type="semantic_similarity"
            )
            
            embedding_vector = result['embedding']
            
            # Always normalize for better cosine similarity
            embedding_vector = self._normalize_vector(embedding_vector)
            
            # Create or update ItemEmbedding
            embedding_obj, created = await ItemEmbedding.get_or_create(
                item_id=item.id,
                defaults={
                    'embedding': embedding_vector,
                    'model_version': settings.embedding_model,
                    'dimension': settings.embedding_dimension
                }
            )
            
            if not created:
                # Update existing embedding
                embedding_obj.embedding = embedding_vector
                embedding_obj.model_version = settings.embedding_model
                embedding_obj.dimension = settings.embedding_dimension
                await embedding_obj.save()
            
            log.info(f"Generated embedding for item {item.id}")
            return embedding_obj
            
        except Exception as e:
            log.error(f"Error generating embedding for item {item.id}: {str(e)}")
            return None

    async def generate_query_embedding(self, query: str) -> Optional[List[float]]:
        """Generate RETRIEVAL_QUERY embedding for a search query."""
        if not self.is_configured:
            log.error("Embedding service not configured")
            return None

        if not query:
            return None

        try:
            # Generate embedding for consistency
            result = genai.embed_content(
                model=settings.embedding_model,
                content=query,
                task_type="semantic_similarity"
            )
            
            embedding_vector = result['embedding']
            
            # Always normalize for better cosine similarity
            embedding_vector = self._normalize_vector(embedding_vector)
            
            return embedding_vector
            
        except Exception as e:
            log.error(f"Error generating query embedding: {str(e)}")
            return None

    async def bulk_generate_item_embeddings(self, items: List[ItemModel], batch_size: int = 20) -> int:
        """Generate embeddings for multiple items in batches."""
        if not self.is_configured:
            log.error("Embedding service not configured")
            return 0

        successful_count = 0
        
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            log.info(f"Processing embedding batch {i//batch_size + 1} ({len(batch)} items)")
            
            for item in batch:
                try:
                    result = await self.generate_item_embedding(item)
                    if result:
                        successful_count += 1
                    
                    # Rate limit handling - wait between requests
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    log.error(f"Error in batch embedding generation for item {item.id}: {str(e)}")
                    # Wait longer on error (potential rate limit)
                    await asyncio.sleep(1)
        
        log.info(f"Successfully generated {successful_count} embeddings out of {len(items)} items")
        return successful_count

    def calculate_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Calculate cosine similarity between two embeddings."""
        if len(embedding1) != len(embedding2):
            log.error(f"Embedding dimension mismatch: {len(embedding1)} vs {len(embedding2)}")
            return 0.0
        
        # Calculate dot product
        dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
        
        # If vectors are already normalized, dot product is cosine similarity
        # Otherwise, we'd need to divide by magnitudes
        # Since we normalize in generate methods, we can return dot product directly
        return dot_product

    async def search_items_by_embedding(
        self, 
        query_embedding: List[float], 
        user_items: List[ItemModel],
        similarity_threshold: float = settings.similarity_threshold,
        offset: int = 0,
        limit: int = 20
    ) -> List[Tuple[ItemModel, float]]:
        """Search items using vector similarity."""
        scored_items = []
        
        for item in user_items:
            try:
                embedding_obj = await ItemEmbedding.get_or_none(item_id=item.id)
                if not embedding_obj:
                    continue

                similarity = self.calculate_similarity(query_embedding, embedding_obj.embedding)
                log.info(f"Item {item.id} similarity score: {similarity:.4f}")
                
                if similarity >= similarity_threshold:
                    scored_items.append((item, similarity))
                    
            except Exception as e:
                log.error(f"Error calculating similarity for item {item.id}: {str(e)}")
                continue
        
        # Sort by similarity (highest first)
        scored_items.sort(key=lambda x: x[1], reverse=True)
        
        # Apply pagination
        return scored_items[offset:offset + limit]

# Global instance
gemini_embedding_service = GeminiEmbeddingService()