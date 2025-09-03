import os
import hashlib
import json
import time
from typing import Optional, List, Dict, Any, Union
from functools import lru_cache

# Try to import the Google Generative AI library
try:
    import google.generativeai as genai
    from google.generativeai.types import HarmCategory, HarmBlockThreshold
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

# Cache directory
CACHE_DIR = os.path.join(os.path.dirname(__file__), '..', '.cache')
os.makedirs(CACHE_DIR, exist_ok=True)

def get_client():
    """Get a client for the Google Generative AI API."""
    if not GENAI_AVAILABLE:
        raise RuntimeError(
            "The Google Generative AI library is not installed. "
            "Please install it with `pip install google-generativeai`."
        )

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        # Try to load from .env file
        try:
            from dotenv import load_dotenv
            load_dotenv()
            api_key = os.environ.get("GEMINI_API_KEY")
        except ImportError:
            pass

    if not api_key:
        raise RuntimeError(
            "The GEMINI_API_KEY environment variable is not set. "
            "Please set it to your Google Generative AI API key."
        )

    genai.configure(api_key=api_key)
    return genai

def _get_cache_key(model: str, contents: List, config: Dict[str, Any]) -> str:
    """Generate a cache key for the request."""
    # Convert contents to string and limit length to avoid extremely long keys
    content_str = str([str(c)[:1000] for c in contents])
    key_parts = [model, content_str, str(config)]
    key_string = json.dumps(key_parts, sort_keys=True)
    return hashlib.md5(key_string.encode()).hexdigest()

def _get_cached_response(cache_key: str) -> Optional[Dict[str, Any]]:
    """Try to get a cached response."""
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as f:
                return json.load(f)
        except Exception:
            return None
    return None

def _save_to_cache(cache_key: str, response_data: Dict[str, Any]) -> None:
    """Save response to cache."""
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")
    try:
        with open(cache_file, 'w') as f:
            json.dump(response_data, f)
    except Exception:
        pass  # Silently fail if caching doesn't work

def generate_content(model: str, contents: List, config: Optional[Dict[str, Any]] = None, 
                     use_cache: bool = True, max_retries: int = 3, cache_key: str = None):
    """Generate content using the Google Generative AI API with caching and retries."""
    config = config or {}
    
    # Only use cache for non-local processing
    if use_cache:
        # Use provided cache_key if available, otherwise generate one
        if cache_key is None:
            cache_key = _get_cache_key(model, contents, config)
            
        cached = _get_cached_response(cache_key)
        if cached:
            class CachedResponse:
                def __init__(self, data):
                    self.text = data.get("text", "")
                    self.parsed = data.get("parsed")
            return CachedResponse(cached)
    
    client = get_client()
    
    for retry in range(max_retries):
        try:
            # Use the simpler gemini-flash model when possible to reduce latency
            if model == "gemini-2.5-pro" and len(str(contents)) < 10000:
                actual_model = "gemini-2.5-flash"
            else:
                actual_model = model
                
            response = client.models.generate_content(
                model=actual_model,
                contents=contents,
                **config
            )
            
            # Cache the response
            if use_cache and cache_key:
                response_data = {
                    "text": getattr(response, "text", ""),
                    "parsed": getattr(response, "parsed", None),
                }
                _save_to_cache(cache_key, response_data)
                
            return response
            
        except Exception as e:
            if "overloaded" in str(e).lower() and retry < max_retries - 1:
                wait_time = (2 ** retry) * 0.5  # Exponential backoff
                time.sleep(wait_time)
            else:
                # Return simple object with the error message
                class ErrorResponse:
                    def __init__(self, error):
                        self.text = f"Error: {error}"
                        self.parsed = None
                return ErrorResponse(e)
    
    return None

# Local processing functions that don't need LLM API
def analyze_csv_locally(csv_data: Union[str, bytes]) -> Dict[str, Any]:
    """Analyze CSV file locally without LLM."""
    import csv
    import io
    from statistics import mean, median, pstdev
    
    # Handle bytes data
    if isinstance(csv_data, bytes):
        try:
            csv_data = csv_data.decode('utf-8')
        except UnicodeDecodeError:
            try:
                csv_data = csv_data.decode('latin-1')
            except:
                return {"error": "Could not decode CSV data"}
    
    # Parse CSV
    try:
        reader = csv.reader(io.StringIO(csv_data))
        rows = list(reader)
        headers = rows[0]
        data_rows = rows[1:]
        
        # Calculate basic statistics
        num_columns = {}
        for i, header in enumerate(headers):
            try:
                values = [float(row[i]) for row in data_rows if i < len(row) and row[i].strip()]
                if values:
                    num_columns[header] = {
                        "mean": mean(values),
                        "median": median(values),
                        "min": min(values),
                        "max": max(values),
                        "std_dev": pstdev(values) if len(values) > 1 else 0
                    }
            except (ValueError, TypeError):
                # Not a numeric column
                pass
                
        # Analyze categorical columns
        cat_columns = {}
        for i, header in enumerate(headers):
            if header not in num_columns:
                values = [row[i] for row in data_rows if i < len(row)]
                value_counts = {}
                for val in values:
                    if val in value_counts:
                        value_counts[val] += 1
                    else:
                        value_counts[val] = 1
                cat_columns[header] = {
                    "unique_values": len(value_counts),
                    "most_common": sorted(value_counts.items(), key=lambda x: x[1], reverse=True)[:5]
                }
                
        # Generate quick summary
        return {
            "headers": headers,
            "row_count": len(data_rows),
            "numeric_columns": num_columns,
            "categorical_columns": cat_columns,
            "sample_rows": data_rows[:5]
        }
        
    except Exception as e:
        return {"error": f"Error analyzing CSV: {str(e)}"}
