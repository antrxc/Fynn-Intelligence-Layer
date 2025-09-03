import time
import hashlib
import requests
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Optional, Union, Any
from pydantic import BaseModel

from structuredOutput.summary import SummaryService, SummaryModel
from structuredOutput.recommendations import RecommendationService, RecommendationModel
from structuredOutput.visuals import VisualsService, ChartSpec

class ServiceResult(BaseModel):
    """Container for service execution results with metadata."""
    success: bool = True
    data: Any = None
    execution_time: float = 0
    error_message: Optional[str] = None

class FileProcessor:
    """Handles file content processing and MIME type detection."""
    
    def process_file(self, content: bytes, mime_type: Optional[str] = None) -> tuple:
        """Process file content and return processed content and metadata."""
        # Determine MIME type if not provided
        if not mime_type:
            # Try to detect CSV files
            try:
                # Check first few lines for CSV-like pattern
                sample = content[:1000].decode('utf-8')
                lines = sample.splitlines()
                if len(lines) > 1:
                    # Check if commas are consistent across lines
                    comma_counts = [line.count(',') for line in lines[:5]]
                    if all(count > 0 for count in comma_counts) and max(comma_counts) - min(comma_counts) <= 1:
                        mime_type = 'text/csv'
                        # Convert bytes to string for CSV
                        return content.decode('utf-8'), {"type": mime_type}
            except UnicodeDecodeError:
                # Not a text file
                pass
                
            # Simple MIME type detection based on first few bytes
            if content.startswith(b'%PDF'):
                mime_type = 'application/pdf'
            elif content.startswith(b'PK'):
                mime_type = 'application/zip'  # Could be XLSX, DOCX, etc.
            else:
                # Default to text
                try:
                    # Try to decode as text
                    text_content = content.decode('utf-8', errors='ignore')
                    return text_content, {"type": "text/plain"}
                except:
                    # Default to binary
                    mime_type = 'application/octet-stream'
                
        return content, {"type": mime_type}

class ErrorHandler:
    """Handles errors from services and operations."""
    
    def handle_error(self, service_name: str, exception: Exception) -> ServiceResult:
        """Convert exception to structured error result."""
        error_message = f"{type(exception).__name__}: {str(exception)}"
        print(f"Error in {service_name}: {error_message}")
        
        return ServiceResult(
            success=False,
            error_message=error_message,
            execution_time=0
        )

class IntelligenceOrchestrator:
    """Coordinates concurrent execution of intelligence services."""
    
    def __init__(self):
        self.summary_service = SummaryService()
        self.recommendation_service = RecommendationService()
        self.visuals_service = VisualsService()
        self.file_processor = FileProcessor()
        self.error_handler = ErrorHandler()
        self.cache = {}  # Would use Redis in production
    
    def _generate_cache_key(self, content) -> str:
        """Generate a cache key for content."""
        if isinstance(content, str):
            content_bytes = content.encode('utf-8')
        else:
            content_bytes = content
        
        # Create a hash of the content for the cache key
        return hashlib.md5(content_bytes).hexdigest()
    
    def _download_with_retry(self, url: str, max_retries: int = 3) -> bytes:
        """Download content from URL with retry logic."""
        for attempt in range(max_retries):
            try:
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                return response.content
            except requests.RequestException as e:
                if attempt == max_retries - 1:
                    raise
                print(f"Download attempt {attempt + 1} failed: {str(e)}. Retrying...")
                time.sleep(2 ** attempt)  # Exponential backoff
    
    def analyze(self, file_url: Optional[str] = None, content: Optional[Union[str, bytes]] = None, 
                mime_type: Optional[str] = None) -> Dict[str, ServiceResult]:
        """
        Analyze content from file_url or provided content.
        Returns a dictionary with results from each service.
        """
        # Stage 1: Process file once
        try:
            if file_url:
                file_content = self._download_with_retry(file_url)
                processed_content, metadata = self.file_processor.process_file(file_content, mime_type)
            elif content:
                if isinstance(content, str):
                    processed_content, metadata = content, {"type": "text/plain"}
                else:
                    processed_content, metadata = self.file_processor.process_file(content, mime_type)
            else:
                return {"error": ServiceResult(
                    success=False,
                    error_message="Either file_url or content must be provided"
                )}
            
            # Check cache
            cache_key = self._generate_cache_key(processed_content)
            if cached := self.cache.get(cache_key):
                return cached
                
        except Exception as e:
            error_result = self.error_handler.handle_error("File processing", e)
            return {"error": error_result}
        
        # Stage 2: Run all services concurrently
        results = {}
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(self._run_summary_service, processed_content, metadata.get("type")): "summary",
                executor.submit(self._run_recommendation_service, processed_content, metadata.get("type")): "recommendations", 
                executor.submit(self._run_visuals_service, processed_content, metadata.get("type")): "visuals"
            }
            
            for future in as_completed(futures):
                service_name = futures[future]
                try:
                    results[service_name] = future.result()
                except Exception as e:
                    results[service_name] = self.error_handler.handle_error(service_name, e)
        
        # Cache results
        self.cache[cache_key] = results
        return results
    
    def _run_with_retry(self, service_name: str, fn, content: Union[str, bytes], mime_type: Optional[str], 
                        max_retries: int = 3, base_delay: float = 1.0) -> ServiceResult:
        """Run a service with retry logic for transient errors."""
        start_time = time.time()
        last_error = None
        
        for attempt in range(max_retries):
            try:
                result = fn(content, mime_type=mime_type)
                return ServiceResult(
                    success=True, 
                    data=result,
                    execution_time=time.time() - start_time
                )
            except Exception as e:
                last_error = e
                error_str = str(e)
                
                # Check if it's a transient error that we should retry
                if "overloaded" in error_str or "UNAVAILABLE" in error_str or "rate limit" in error_str:
                    # Exponential backoff with jitter
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
                    print(f"{service_name} service overloaded, retrying in {delay:.2f}s (attempt {attempt+1}/{max_retries})")
                    time.sleep(delay)
                else:
                    # Non-transient error, don't retry
                    break
        
        # If we get here, all retries failed
        return self.error_handler.handle_error(service_name, last_error)
    
    def _run_summary_service(self, content: Union[str, bytes], mime_type: Optional[str]) -> ServiceResult:
        """Run summary service and time its execution."""
        return self._run_with_retry(
            service_name="summary",
            fn=self.summary_service.generate_summary,
            content=content,
            mime_type=mime_type
        )
    
    def _run_recommendation_service(self, content: Union[str, bytes], mime_type: Optional[str]) -> ServiceResult:
        """Run recommendation service and time its execution."""
        return self._run_with_retry(
            service_name="recommendations",
            fn=self.recommendation_service.generate_recommendations,
            content=content,
            mime_type=mime_type
        )
    
    def _run_visuals_service(self, content: Union[str, bytes], mime_type: Optional[str]) -> ServiceResult:
        """Run visuals service and time its execution."""
        return self._run_with_retry(
            service_name="visuals",
            fn=self.visuals_service.recommend_charts,
            content=content,
            mime_type=mime_type
        )