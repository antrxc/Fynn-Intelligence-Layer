import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Dict, Any

from .summary import SummaryService
from .visuals import VisualsService
from .recommendations import RecommendationService


class Orchestrator:
    """Download a file URL or accept raw text and run summary, visuals, and recommendations concurrently."""

    def __init__(self):
        self.summary_srv = SummaryService()
        self.visuals_srv = VisualsService()
        self.reco_srv = RecommendationService()

    def _download(self, url: str) -> bytes:
        r = requests.get(url)
        r.raise_for_status()
        return r.content

    def analyze(self, *, file_url: Optional[str] = None, text: Optional[str] = None, mime_type: Optional[str] = None) -> Dict[str, Any]:
        """Run the three services concurrently and return combined results.

        Provide either `file_url` or `text`.
        """
        if not (file_url or text):
            raise ValueError("Provide either file_url or text")

        input_data = None
        if file_url:
            input_data = self._download(file_url)
        else:
            input_data = text

        results: Dict[str, Any] = {}

        with ThreadPoolExecutor(max_workers=3) as ex:
            futures = {
                ex.submit(self.summary_srv.generate_summary, input_data, 5, mime_type): "summary",
                ex.submit(self.visuals_srv.recommend_charts, input_data, 5, mime_type): "visuals",
                ex.submit(self.reco_srv.generate_recommendations, input_data, 5, mime_type): "recommendations",
            }

            for fut in as_completed(futures):
                name = futures[fut]
                try:
                    results[name] = fut.result()
                except Exception as e:
                    results[name] = {"error": str(e)}

        return results
