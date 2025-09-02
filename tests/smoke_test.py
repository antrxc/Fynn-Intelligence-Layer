"""Smoke tests for the intelligence layer services.

These tests check that the service classes can be imported and instantiated.
They avoid making actual LLM calls.
"""
import sys
import os

# Ensure project root is on sys.path so local packages can be imported when
# running this file directly from the tests/ directory.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from structuredOutput.summary import SummaryService
from structuredOutput.recommendations import RecommendationService
from structuredOutput.visuals import VisualsService


def run():
    print("Instantiating services...")
    s = SummaryService()
    r = RecommendationService()
    v = VisualsService()
    print("Services instantiated:", s.__class__.__name__, r.__class__.__name__, v.__class__.__name__)


if __name__ == "__main__":
    run()
