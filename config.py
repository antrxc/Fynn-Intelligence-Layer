# config.py
import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class AppConfig:
    # File processing
    max_file_size_mb: int = int(os.getenv('MAX_FILE_SIZE_MB', '50'))
    allowed_mime_types: list = os.getenv('ALLOWED_MIME_TYPES', 'application/pdf,text/csv,text/plain').split(',')
    
    # LLM settings
    model_name: str = os.getenv('LLM_MODEL', 'gemini-2.5-flash')
    max_retries: int = int(os.getenv('LLM_MAX_RETRIES', '3'))
    timeout_seconds: int = int(os.getenv('LLM_TIMEOUT', '30'))
    
    # Concurrency
    max_workers: int = int(os.getenv('MAX_WORKERS', '3'))
    rate_limit_rpm: int = int(os.getenv('RATE_LIMIT_RPM', '60'))
    
    # Cache
    cache_ttl_seconds: int = int(os.getenv('CACHE_TTL', '3600'))
    redis_url: Optional[str] = os.getenv('REDIS_URL')

# metrics.py
from prometheus_client import Counter, Histogram, generate_latest

REQUEST_COUNT = Counter('service_requests_total', 'Total requests', ['service', 'status'])
REQUEST_DURATION = Histogram('service_duration_seconds', 'Request duration', ['service'])
ERROR_COUNT = Counter('service_errors_total', 'Total errors', ['service', 'error_type'])

class MetricsMiddleware:
    def track_request(self, service_name: str):
        start_time = time.time()
        REQUEST_COUNT.labels(service=service_name, status='started').inc()
        
        def record_metrics(success: bool, error_type: str = None):
            duration = time.time() - start_time
            REQUEST_DURATION.labels(service=service_name).observe(duration)
            status = 'success' if success else 'error'
            REQUEST_COUNT.labels(service=service_name, status=status).inc()
            if not success:
                ERROR_COUNT.labels(service=service_name, error_type=error_type).inc()
        
        return record_metrics