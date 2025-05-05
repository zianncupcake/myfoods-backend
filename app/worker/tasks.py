import httpx 
import time
import logging
import json
from typing import List, Dict, Optional
import asyncio 

import jmespath 
from parsel import Selector
from httpx import AsyncClient, Response, TimeoutException, HTTPStatusError, RequestError 

from .celery_app import celery 

log = logging.getLogger(__name__)

async def get_httpx_client() -> AsyncClient:
    """Creates and returns a configured httpx AsyncClient with browser-like headers."""
    return AsyncClient(
        http2=True, 
        headers={ 
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
        },
        follow_redirects=True,
        timeout=20.0
    )

def parse_post(response: Response) -> Optional[Dict]:
    """
    Parses hidden post data from TikTok HTML response using XPath and JMESPath.
    Returns extracted data dict or None if parsing fails.
    """
    log.debug(f"Attempting to parse response for URL: {response.url}")
    if response.status_code != 200:
        log.error(f"Request failed with status {response.status_code} for {response.url}. Cannot parse.")
        return None
    
    content_encoding = response.headers.get('content-encoding')
    log.info(f"Response Content-Encoding header: {content_encoding}")

    try:
        selector = Selector(response.text)
        data_script = selector.xpath("//script[@id='__UNIVERSAL_DATA_FOR_REHYDRATION__']/text()").get()
        if not data_script:
            log.error(f"Could not find script tag '__UNIVERSAL_DATA_FOR_REHYDRATION__' in HTML for {response.url}")
            return None

        json_data = json.loads(data_script)
        post_data = json_data["__DEFAULT_SCOPE__"]["webapp.video-detail"]["itemInfo"]["itemStruct"]

        # --- ADDED LOGGING for the full post_data structure ---
        log.info(f"--- FULL post_data STRUCTURE BEFORE JMESPATH for {response.url} ---")
        try:
            log.info(json.dumps(post_data, indent=2)) # Pretty print the full structure
        except Exception as log_e:
            log.error(f"Error logging full post_data structure: {log_e}")
            log.info(f"Raw full post_data structure: {post_data}")
        log.info(f"--- END FULL post_data STRUCTURE ---")
        # --- END ADDED LOGGING ---

        parsed_post_data = jmespath.search(
            """{
            desc: desc,
            diversificationLabels: diversificationLabels,
            suggestedWords: suggestedWords,
            stickerTexts: stickersOnItem[].stickerText[] | []
            }""",
            post_data
        )
        log.debug(f"Successfully parsed post data for {response.url}")
        return parsed_post_data
    except json.JSONDecodeError as e:
        log.error(f"Failed to decode JSON from script tag for {response.url}: {e}")
        return None
    except KeyError as e:
        log.error(f"Missing expected key in JSON structure for {response.url}: {e}")
        return None
    except Exception as e:
        log.error(f"Unexpected error during parsing for {response.url}: {e}", exc_info=True)
        return None

async def _async_logic_for_task(source_url: str, task_id: str):
    log.info(f"[Task ID: {task_id}] Entering _async_logic_for_task")
    status = "FAILURE"
    data = None
    error_message = None

    try:
        log.info(f"[Task ID: {task_id}] Attempting to scrape TikTok URL (async): {source_url}")
        async with await get_httpx_client() as client:
            response = await client.get(source_url)
            response.raise_for_status()
            data = parse_post(response)

            if data:
                log.info(f"[Task ID: {task_id}] PARSED DATA RECEIVED:")
                status = "SUCCESS"
                try:
                    # Use json.dumps for potentially large/complex dicts
                    log.info(json.dumps(data, indent=2))
                except Exception as log_e:
                    log.error(f"Error logging full scraped_post_info: {log_e}")
                    log.info(f"Raw full scraped_post_info: {data}") # Fallback log
            else:
                log.warning(f"[Task ID: {task_id}] Parsing returned None (check logs above for parsing errors).")

    except HTTPStatusError as e:
        log.error(f"[Task ID: {task_id}] HTTP error {e.response.status_code} during async scrape: {e.response.text[:200]}")
        error_message = f"Scrape HTTP Error: {e.response.status_code}"
        if e.response.status_code >= 500:
             raise 
    except TimeoutException:
        log.error(f"[Task ID: {task_id}] Timeout during async scrape for {source_url}")
        error_message = "Scrape Timeout"
        raise 
    except RequestError as e:
        log.error(f"[Task ID: {task_id}] Request error during async scrape for {source_url}: {e}")
        error_message = "Scrape Request Error"
        raise 
    except Exception as e:
        log.error(f"[Task ID: {task_id}] Unhandled exception in async logic for {source_url}: {e}", exc_info=True)
        error_message = f"Unhandled Async Exception: {str(e)[:100]}"

    return {
        "data": data,
        "status": status,
        "error": error_message 
    }

@celery.task(bind=True, max_retries=2, default_retry_delay=90) 
def process_url_task(self, source_url: str): 
    """
    Synchronous Celery task wrapper that executes the core asynchronous logic
    using asyncio.run(). This pattern works well with Celery's default worker pool.
    """
    task_id = self.request.id
    log.info(f"[Task ID: {task_id}] Starting SYNC wrapper for URL: {source_url}")

    final_result = {} 
    try:
        log.info(f"[Task ID: {task_id}] Calling asyncio.run(_async_logic_for_task)...")
        final_result = asyncio.run(_async_logic_for_task(source_url, task_id))
        log.info(f"[Task ID: {task_id}] asyncio.run() completed.")

    except Exception as e:
        log.error(f"[Task ID: {task_id}] Exception during asyncio.run() for {source_url}: {e}", exc_info=True)
        final_result = {
            "data": None,
            "status": "FAILURE",
            "error": f"Sync Wrapper Exception: {str(e)[:100]}"
        }
    log.info(f"[Task ID: {task_id}] SYNC wrapper finished for URL: {source_url}")
    return final_result

