import httpx 
import logging
import json
import re
import gc
from typing import Dict, Optional
import asyncio 

import jmespath 
from parsel import Selector
from httpx import AsyncClient, Response, TimeoutException, HTTPStatusError, RequestError 

from .celery_app import celery 

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from ..services.r2_uploader import upload_image_from_url_to_r2 

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

def extract_username_slicing(text):
    start_marker = "comments - "
    end_marker = " on "

    start_index = text.find(start_marker)
    if start_index == -1:
        return None 

    start_index += len(start_marker)

    end_index = text.find(end_marker, start_index) 
    if end_index == -1:
        return None 

    return text[start_index:end_index]

def extract_caption_slicing(text):
    colon_index = text.find(': "')
    if colon_index == -1:
        start_quote_index = text.find('"')
        if start_quote_index == -1:
            return None 
        start_index = start_quote_index + 1
    else:
        start_index = colon_index + len(': "')

    end_quote_index = text.rfind('"')

    if end_quote_index == -1 or end_quote_index <= start_index:
        return None 

    return text[start_index:end_quote_index]

async def parse_ig(url: str) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--start-maximized"])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        page = await context.new_page()
        html_content = ""

        try:
            log.info(f"Navigating to: {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            log.info("Page loaded.")

            await page.wait_for_timeout(3000) 

            close_button_selector = 'div[role="button"]:has(svg[aria-label="Close"])'
            log.info(f"Looking for close button with selector: {close_button_selector}")
            
            await page.wait_for_selector(close_button_selector, state="visible", timeout=10000) 
            log.info("Selector is now visible according to wait_for_selector.")
            try:
                # close the x of the pop up (theres 2 and somehow its the 2nd one)
                close_button = page.locator('div[role="button"]:has(svg[aria-label="Close"])').nth(1) 

                if await close_button.is_visible(timeout=5000): 
                    log.info("Close button found and visible. Attempting to click...")
                    await close_button.click(timeout=5000) 
                    log.info("Clicked the close button.")
                    await page.wait_for_timeout(2000) 
                else:
                    log.info("Close button found but not visible (or timed out waiting for visibility).")
            except PlaywrightTimeoutError:
                log.info("Close button not found or not visible within the specified timeout.")
            except Exception as e:
                log.info(f"An error occurred while trying to click the close button: {e}")

            wait_duration_ms = 5000 
            await page.wait_for_timeout(wait_duration_ms)

            desc = await page.locator('meta[property="og:description"]').first.get_attribute("content")
            imageUrl = await page.locator('meta[property="og:image"]').first.get_attribute("content")
            if desc:
                creator = extract_username_slicing(desc)
                slicedDesc = extract_caption_slicing(desc)

            return {
                "desc": slicedDesc,
                "creator": creator,
                "imageUrl": imageUrl
            }

        except PlaywrightTimeoutError as e:
            log.info(f"A Playwright timeout occurred: {e}")
            try:
                html_content = await page.content() 
                log.info("Retrieved partial HTML content on timeout.")
            except Exception as e_html:
                log.info(f"Could not retrieve HTML on timeout: {e_html}")
        except Exception as e:
            log.info(f"An unexpected error occurred: {e}")
            try:
                if page:
                    html_content = await page.content()
                    log.info("Retrieved partial HTML content on error.")
            except Exception as e_html:
                log.info(f"Could not retrieve HTML on error: {e_html}")
        finally:
            await browser.close()
            gc.collect()
        
        return html_content

async def parse_youtube(url: str) -> Dict:
    """Optimized YouTube scraping with minimal memory usage"""
    result = {"desc": None, "creator": None, "imageUrl": None}
    
    async with async_playwright() as p:
        browser = None
        try:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-gpu',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor',
                    '--disable-extensions',
                    '--disable-images',
                    '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-renderer-backgrounding',
                    '--disable-features=TranslateUI',
                    '--disable-ipc-flooding-protection',
                    '--js-flags=--max-old-space-size=256',
                    '--max_old_space_size=256',
                    '--memory-pressure-off',
                ]
            )
            
            context = await browser.new_context(
                viewport={'width': 800, 'height': 600},
                user_agent="Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36",
                locale='en-US',
                timezone_id='America/New_York',
                bypass_csp=True,
                ignore_https_errors=True,
                java_script_enabled=True,
                has_touch=True,
                is_mobile=True,
            )
            
            page = await context.new_page()
            
            # Block unnecessary resources to save memory
            await page.route("**/*.{png,jpg,jpeg,gif,webp,svg,mp4,webm,ogg,mp3,wav,flac,aac,woff,woff2,ttf,otf}", 
                           lambda route: route.abort())
            await page.route("**/ads/**", lambda route: route.abort())
            await page.route("**/analytics/**", lambda route: route.abort())
            
            log.info(f"Navigating to YouTube URL: {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            
            # Wait for page to load fully
            await page.wait_for_timeout(5000)
            
            # Get HTML content directly (Method 2)
            html_content = await page.content()
            
            # Extract title from meta or page title
            title_match = re.search(r'<meta property="og:title" content="([^"]+)"', html_content)
            if title_match:
                result["desc"] = title_match.group(1)
            else:
                title_match = re.search(r'<title>([^<]+)</title>', html_content)
                if title_match:
                    result["desc"] = title_match.group(1)
            
            # Extract creator from anchor tag with /shorts first
            anchor_match = re.search(r'<a[^>]*href="[^"]*/@([^"/]+)/shorts"[^>]*>', html_content)
            if anchor_match:
                result["creator"] = anchor_match.group(1)
            else:
                # Fallback to JSON patterns
                creator_match = re.search(r'"canonicalBaseUrl":"/@([^"]+)"', html_content)
                if not creator_match:
                    creator_match = re.search(r'"ownerChannelName":"([^"]+)"', html_content)
                if creator_match:
                    result["creator"] = creator_match.group(1)
            
            # Extract image URL
            image_match = re.search(r'(https://i\.ytimg\.com/vi/[^"\'<>]+)', html_content)
            if image_match:
                result["imageUrl"] = image_match.group(1)
            
            log.info(f"YouTube data extracted: title={bool(result['desc'])}, creator={bool(result['creator'])}, image={bool(result['imageUrl'])}")
            
        except PlaywrightTimeoutError as e:
            log.error(f"Playwright timeout while parsing YouTube: {e}")
        except Exception as e:
            log.error(f"Error parsing YouTube: {e}")
        finally:
            # Safe cleanup - check if browser exists and is connected
            if browser:
                try:
                    await browser.close()
                except Exception as e:
                    log.debug(f"Browser already closed: {e}")
            
            # Force garbage collection to free memory
            gc.collect()
    
    return result

async def parse_tiktok_with_playwright(url: str) -> Optional[Dict]:
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,  
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
            ]
        )
        
        context = await browser.new_context(
            viewport={'width': 375, 'height': 812},
            user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
            locale='en-US',
            timezone_id='America/New_York'
        )
        
        page = await context.new_page()
        data = None

        try:
            log.info(f"Navigating to TikTok URL: {url}")
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(3000)

            html_content = await page.content()
            data = parse_tiktok_html(html_content)
            
            if data:
                log.info("Successfully parsed TikTok data")
            else:
                log.warning("Failed to parse TikTok data")
                
        except PlaywrightTimeoutError as e:
            log.error(f"Playwright timeout while loading TikTok page: {e}")
        except Exception as e:
            log.error(f"Error processing TikTok URL with Playwright: {e}", exc_info=True)
        finally:
            await browser.close()
            gc.collect()
            
        return data

def parse_tiktok_html(html_content: str) -> Optional[Dict]:
    log.info("Attempting to parse TikTok content")

    try:
        selector = Selector(html_content)
        data_script = selector.xpath("//script[@id='__UNIVERSAL_DATA_FOR_REHYDRATION__']/text()").get()
        
        if not data_script:
            log.error("No __UNIVERSAL_DATA_FOR_REHYDRATION__ script found")
            return None

        json_data = json.loads(data_script)
        
        # Try video path first
        post_data = json_data.get("__DEFAULT_SCOPE__", {}).get("webapp.video-detail", {}).get("itemInfo", {}).get("itemStruct")
        
        # If video path is empty, try image path
        if not post_data:
            log.info("Video path empty, trying image/slide path")
            post_data = json_data.get("__DEFAULT_SCOPE__", {}).get("webapp.reflow.video.detail", {}).get("itemInfo", {}).get("itemStruct")
        
        if not post_data:
            log.error("No valid post data found in either path")
            return None

        parsed_post_data = jmespath.search(
            """{
            desc: desc,
            creator: author.uniqueId,
            imageUrl: video.cover,
            diversificationLabels: diversificationLabels,
            suggestedWords: suggestedWords
            }""",
            post_data
        )
        return parsed_post_data
        
    except json.JSONDecodeError as e:
        log.error(f"Failed to decode JSON from script tag: {e}")
        return None
    except Exception as e:
        log.error(f"Unexpected error during parsing: {e}")
        return None


async def _async_logic_for_task(source_url: str, task_id: str):
    log.info(f"[Task ID: {task_id}] Entering _async_logic_for_task")
    status = "FAILURE"
    data = None
    error_message = None

    try:
        log.info(f"[Task ID: {task_id}] Attempting to scrape URL (async): {source_url}")
        
        if "tiktok" in source_url:
            data = await parse_tiktok_with_playwright(source_url)
        elif "youtube.com" in source_url or "youtu.be" in source_url:
            data = await parse_youtube(source_url)
        elif "instagram.com" in source_url:
            data = await parse_ig(source_url)
        else:
            log.warning(f"[Task ID: {task_id}] Unknown platform for URL: {source_url}")
            data = None

        if data:
            log.info(f"[Task ID: {task_id}] PARSED DATA RECEIVED:")
            
            # --- Integrate R2 Image Upload ---
            image_url = data.get("imageUrl")
            if image_url:
                r2_object_prefix = f"images/{task_id}" 
                
                log.info(f"[Task ID: {task_id}] Attempting to upload image from {image_url} to R2.")
                try:
                    image_upload_info = await upload_image_from_url_to_r2(
                        image_url,
                        desired_object_key_prefix=r2_object_prefix
                    )
                    log.info(f"[Task ID: {task_id}] Image upload to R2 successful: {image_upload_info}")
                    data["r2ImageUrl"] = image_upload_info.get("public_url")
                    status = "SUCCESS"
                except Exception as r2_e:
                    log.error(f"[Task ID: {task_id}] R2 image upload failed: {r2_e}", exc_info=True)
                    error_message = f"Image upload failed: {str(r2_e)[:100]}"
                    data["r2_image_error"] = error_message
            else:
                log.info(f"[Task ID: {task_id}] No imageUrl found in parsed data.")

            try:
                log.info("success")
            except Exception as log_e:
                log.error(f"Error logging full scraped_post_info: {log_e}")
                log.info(f"Raw full scraped_post_info: {data}")
        else:
            error_message = "No data found"
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
    
    # Force garbage collection after task completion
    gc.collect()
    
    return final_result

