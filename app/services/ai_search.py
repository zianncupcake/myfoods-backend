import json
import logging
from typing import List, Dict, Any, Optional
import google.generativeai as genai
from ..config import settings
from ..models import Item as ItemModel

log = logging.getLogger("uvicorn")

class GeminiSearchService:
    def __init__(self):
        if settings.google_ai_api_key:
            genai.configure(api_key=settings.google_ai_api_key)
            self.model = genai.GenerativeModel(settings.gemini_model)
            self.is_configured = True
            log.info(f"Gemini AI search service initialized with model: {settings.gemini_model}")
        else:
            self.is_configured = False
            log.warning("Gemini AI search service not configured - missing GOOGLE_AI_API_KEY")

    async def search_items(self, query: str, items: List[ItemModel], offset: int = 0, limit: int = 20) -> List[ItemModel]:
        """
        Search through items using Gemini AI for semantic understanding with batch processing.
        
        Args:
            query: The search query from the user
            items: List of items to search through
            offset: Starting position for pagination
            limit: Number of results per batch (default 20)
            
        Returns:
            List of filtered items sorted by relevance (paginated)
        """
        if not self.is_configured:
            log.error("Gemini AI search service not properly configured")
            return []

        if not items:
            return []

        try:
            # Process items in batches for better scalability
            batch_size = 20  # Process 20 items at a time with AI
            all_filtered_ids = []
            
            # Process items in chunks
            for i in range(0, len(items), batch_size):
                batch_items = items[i:i + batch_size]
                
                # Prepare batch data for AI analysis
                items_data = []
                for item in batch_items:
                    item_text = self._prepare_item_text(item)
                    items_data.append({
                        "id": item.id,
                        "text": item_text
                    })

                # Create the prompt for this batch
                prompt = self._create_search_prompt(query, items_data, batch_size)
                
                # Generate response from Gemini for this batch
                response = self.model.generate_content(prompt)
                
                # Parse the AI response to get item IDs from this batch
                batch_ids = self._parse_ai_response(response.text)
                all_filtered_ids.extend(batch_ids)
            
            # Match all filtered results with original items
            filtered_items = self._match_results_with_items(all_filtered_ids, items)
            
            # Apply pagination to the filtered results
            return filtered_items[offset:offset + limit]
            
        except Exception as e:
            log.error(f"Error in Gemini AI search: {str(e)}")
            # Fallback to simple text matching with pagination
            return self._fallback_search(query, items, offset, limit)

    def _prepare_item_text(self, item: ItemModel) -> str:
        """Prepare item data as searchable text."""
        parts = []
        
        if item.notes:
            parts.append(f"Notes: {item.notes}")
        
        if item.tags:
            parts.append(f"Tags: {', '.join(item.tags)}")
            
            
        if item.creator:
            parts.append(f"Creator: {item.creator}")
            
        if item.source_url:
            parts.append(f"URL: {item.source_url}")
            
        return " | ".join(parts) if parts else "No content"

    def _create_search_prompt(self, query: str, items_data: List[Dict], batch_size: int) -> str:
        """Create the prompt for Gemini AI for batch processing."""
        items_text = "\n".join([f"ID: {item['id']} - {item['text']}" for item in items_data])
        
        prompt = f"""
I am providing you with:
1. A user's search request: "{query}"
2. A batch of the user's structured data items with IDs and their content (notes, tags, creator, URLs)

Your task is to:
- Filter out the relevant items from this batch based on the search request
- Match items by analyzing their notes, tags
- Sort the filtered items by relevance (most relevant first)
- Return ONLY the filtered and sorted items from this batch

USER'S ITEMS (BATCH):
{items_text}

IMPORTANT:
- Only return items that are actually relevant to the search query
- Consider semantic meaning, not just keyword matching
- This is a batch of up to {batch_size} items
- Only return IDs from this specific batch

RESPONSE FORMAT (return ONLY this JSON array of item IDs, nothing else):
[item_id1, item_id2, item_id3]
"""
        return prompt

    def _parse_ai_response(self, response_text: str) -> List[int]:
        """Parse the AI response and extract item IDs."""
        try:
            # Clean the response text
            cleaned_text = response_text.strip()
            
            # Remove markdown code blocks if present
            if cleaned_text.startswith("```"):
                lines = cleaned_text.split("\n")
                cleaned_text = "\n".join(lines[1:-1])
            
            # Parse JSON array
            item_ids = json.loads(cleaned_text)
            return item_ids if isinstance(item_ids, list) else []
            
        except json.JSONDecodeError as e:
            log.error(f"Failed to parse AI response as JSON: {e}")
            log.debug(f"AI response was: {response_text}")
            return []
        except Exception as e:
            log.error(f"Error parsing AI response: {e}")
            return []

    def _match_results_with_items(self, item_ids: List[int], items: List[ItemModel]) -> List[ItemModel]:
        """Match AI results with original items and return filtered items."""
        items_dict = {item.id: item for item in items}
        results = []
        
        # The order from AI is already sorted by relevance
        for item_id in item_ids:
            if item_id in items_dict:
                results.append(items_dict[item_id])
        
        return results

    def _fallback_search(self, query: str, items: List[ItemModel], offset: int, limit: int) -> List[ItemModel]:
        """Fallback search using simple text matching when AI fails with pagination."""
        log.info("Using fallback text search")
        query_lower = query.lower()
        scored_items = []
        
        for item in items:
            score = 0.0
            item_text = self._prepare_item_text(item).lower()
            
            # Simple scoring based on keyword matches
            query_words = query_lower.split()
            for word in query_words:
                if word in item_text:
                    score += 0.2
            
            if score > 0:
                scored_items.append((item, min(score, 1.0)))
        
        # Sort by relevance and apply pagination
        scored_items.sort(key=lambda x: x[1], reverse=True)
        filtered_items = [item for item, _ in scored_items]
        return filtered_items[offset:offset + limit]

# Global instance
gemini_search = GeminiSearchService()