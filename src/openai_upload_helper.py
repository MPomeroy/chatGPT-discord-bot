import aiohttp
from openai import AsyncOpenAI
from typing import Optional, Tuple, List, Dict, Any
import os
import io
import re
from src.log import logger

class OpenAIUploadHelper:
    """Helper class for managing file uploads to OpenAI Files API"""
    
    def __init__(self, client: AsyncOpenAI):
        self.client = client
    
    async def download_file_from_url(self, url: str) -> Optional[Tuple[bytes, str]]:
        """Download file from URL and return bytes and filename"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to download file from {url}: HTTP {response.status}")
                        return None
                    
                    file_bytes = await response.read()
                    
                    # Extract filename from URL or Content-Disposition header
                    filename = None
                    content_disposition = response.headers.get('Content-Disposition')
                    if content_disposition:
                        # Try to extract filename from Content-Disposition header
                        match = re.search(r'filename="?(.+?)"?(?:;|$)', content_disposition)
                        if match:
                            filename = match.group(1)
                    
                    if not filename:
                        # Extract from URL
                        from urllib.parse import urlparse, unquote
                        parsed = urlparse(url)
                        filename = unquote(os.path.basename(parsed.path))
                    
                    if not filename:
                        filename = "file"
                    
                    logger.info(f"Successfully downloaded {len(file_bytes)} bytes from {url} as {filename}")
                    return (file_bytes, filename)
                    
        except Exception as e:
            logger.warning(f"Failed to download file from {url}: {e}")
            return None
    
    async def upload_file_to_openai(self, file_bytes: bytes, filename: str) -> Optional[str]:
        """Upload file to OpenAI and return file_id, automatically tracking it"""
        try:
            # Create file-like object from bytes
            file_obj = io.BytesIO(file_bytes)
            file_obj.name = filename
            
            # Upload to OpenAI
            file_response = await self.client.files.create(
                file=file_obj,
                purpose="user_data"
            )
            
            file_id = file_response.id
            logger.info(f"Successfully uploaded {filename} to OpenAI as {file_id}")
            return file_id
            
        except Exception as e:
            logger.warning(f"Failed to upload {filename} to OpenAI: {e}")
            return None
    
    async def process_urls(self, urls: List[str]) -> tuple[List[Dict[str, Any]], int, int]:
        """Process multiple URLs: download, upload, and return formatted content items.
        
        Returns:
            tuple: (list of content items, successful uploads count, failed uploads count)
        """
        content_items = []
        successful_uploads = 0
        failed_uploads = 0
        
        for url in urls:
            # Download file from URL
            download_result = await self.download_file_from_url(url)
            if download_result is None:
                failed_uploads += 1
                logger.warning(f"Skipping file that failed to download: {url}")
                continue
            
            file_bytes, filename = download_result
            
            # Upload to OpenAI Files API (automatically tracked)
            file_id = await self.upload_file_to_openai(file_bytes, filename)
            if file_id is None:
                failed_uploads += 1
                logger.warning(f"Skipping file that failed to upload: {filename}")
                continue
            
            # Add to content items using Files API format
            content_items.append({
                "type": "input_file",
                "file_id": file_id
            })
            
            successful_uploads += 1
        
        return content_items, successful_uploads, failed_uploads

