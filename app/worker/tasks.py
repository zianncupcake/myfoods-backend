import httpx 
import time
import logging
import json
from typing import Dict, Optional
import asyncio 

import jmespath 
from parsel import Selector
from httpx import AsyncClient, Response, TimeoutException, HTTPStatusError, RequestError 

from .celery_app import celery 

# from urllib.parse import quote
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# SCRAPFLY = ScrapflyClient("scp-live-50e9b6a24f5f4772a1ccb584f02a7656")

# BASE_CONFIG = {
#     "asp": True, 
#     "proxy_pool": "public_residential_pool",
# }
# INSTAGRAM_DOCUMENT_ID = "8845758582119845"

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

# async def parse_ig(url: str) -> Dict:
#     """Scrape single Instagram post data"""
    # if "http" in url_or_shortcode:
    #     shortcode = url_or_shortcode.split("/p/")[-1].split("/")[0]
    # else:
    #     shortcode = url_or_shortcode
    # log.info(f"scraping instagram post: {shortcode}")

    # variables = quote(json.dumps({
    #     'shortcode':"DI09IhVPF0C",'fetch_tagged_user_count':None,
    #     'hoisted_comment_id':None,'hoisted_reply_id':None
    # }, separators=(',', ':')))

    # log.info(f"VARIABLESSSSS {variables}")
    # body = f"variables={variables}&doc_id={INSTAGRAM_DOCUMENT_ID}"
    # url = "https://www.instagram.com/graphql/query"

    # result = httpx.post(
    #     url=url,
    #     headers={"content-type": "application/x-www-form-urlencoded"},
    #     data=body
    # )

    # log.info(f"RESULT CONTENT {result.content}")
    # data = json.loads(result.content)
    # return data["data"]["xdt_shortcode_media"]
    
    # result = SCRAPFLY.scrape(
    #     ScrapeConfig(
    #         url=url,
    #         method="POST",
    #         body=body,
    #         headers={"content-type": "application/x-www-form-urlencoded"},
    #         **BASE_CONFIG
    #     )
    # )
    
    # data = json.loads(result.content)
    # return data["data"]["xdt_shortcode_media"]    

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

            # log.info("Retrieving HTML content...")
            # html_content = await page.content()
            # log.info("HTML content retrieved.")
            # with open('hi.html', "w", encoding="utf-8") as f:
            #         f.write(html_content)
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
        
        return html_content

def parse_tiktok(response: Response) -> Optional[Dict]:
    """
    Parses hidden post data from TikTok HTML response using XPath and JMESPath.
    Returns extracted data dict or None if parsing fails.
    """
    log.debug(f"Attempting to parse response for URL: {response.url}")
    # if response.status_code != 200:
    #     log.error(f"Request failed with status {response.status_code} for {response.url}. Cannot parse.")
    #     return None
    
    # content_encoding = response.headers.get('content-encoding')
    # log.info(f"Response Content-Encoding header: {content_encoding}")

    try:
        selector = Selector(response.text)
        data_script = selector.xpath("//script[@id='__UNIVERSAL_DATA_FOR_REHYDRATION__']/text()").get()
        # if not data_script:
        #     log.error(f"Could not find script tag '__UNIVERSAL_DATA_FOR_REHYDRATION__' in HTML for {response.url}")
        #     return None

        json_data = json.loads(data_script)
        post_data = json_data.get("__DEFAULT_SCOPE__", {}).get("webapp.video-detail", {}).get("itemInfo", {}).get("itemStruct")

        # if not post_data:
        #     log.error(f"Could not find STUFF IN POST DATA")
        #     return None

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
        log.info(f"[Task ID: {task_id}] Attempting to scrape URL (async): {source_url}")
        async with await get_httpx_client() as client:
            if "tiktok" in source_url:
                response = await client.get(source_url)
                response.raise_for_status()
                data = parse_tiktok(response)

            else:
                data = await parse_ig(source_url)


            if data:
                log.info(f"[Task ID: {task_id}] PARSED DATA RECEIVED:")
                status = "SUCCESS"
                try:
                    log.info("success")
                except Exception as log_e:
                    log.error(f"Error logging full scraped_post_info: {log_e}")
                    log.info(f"Raw full scraped_post_info: {data}") # Fallback log
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
    return final_result

