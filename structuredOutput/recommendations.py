from pydantic import BaseModel
from typing import List, Union, Optional
from tools.llm_client import get_client
from AgentContracts.recommendations import RECOMMENDATIONS_PROMPT

class RecommendationModel(BaseModel):
    recommendations: List[str]


class RecommendationService:
    """Generate recommendations from a text or document input using gemini-2.5-pro.

    The input may be a str (plain text) or bytes (file content, e.g., PDF).
    """

    MODEL_NAME = "gemini-2.5-flash"

    def __init__(self):
        self.client = get_client()

    def _make_contents(self, input_data: Union[str, bytes], mime_type: Optional[str] = None):
        """Return a contents list suitable for client.models.generate_content.

        If input_data is bytes, include it as a Part (PDF/binary). Otherwise pass text.
        """
        system = (RECOMMENDATIONS_PROMPT)

        if isinstance(input_data, bytes):
            # Lazy import of types
            from google.genai import types

            part = types.Part.from_bytes(data=input_data, mime_type=mime_type or "application/pdf")
            return [system, part]

        return [system, input_data]

    def generate_recommendations(self, input_data: Union[str, bytes], max_output: int = 5, mime_type: Optional[str] = None) -> RecommendationModel:
        contents = self._make_contents(input_data, mime_type=mime_type)

        from tools.llm_client import generate_content

        response = generate_content(
            model=self.MODEL_NAME, contents=contents, config={"response_mime_type": "application/json"}
        )

        # Robust parsing: prefer parsed, then try to parse JSON, then try to extract JSON substrings
        import json, re

        parsed = getattr(response, "parsed", None)
        text = getattr(response, "text", None) or (response if isinstance(response, str) else None)

        items = None
        if parsed:
            items = parsed
        else:
            # Try direct JSON load
            try:
                if isinstance(text, str):
                    items = json.loads(text)
            except Exception:
                items = None

            # Try to extract a JSON array or object substring from text
            if items is None and isinstance(text, str):
                # look for JSON array
                m = re.search(r"(\[.*\])", text, re.S)
                if m:
                    try:
                        items = json.loads(m.group(1))
                    except Exception:
                        items = None

            if items is None and isinstance(text, str):
                # look for JSON object
                m = re.search(r"(\{.*\})", text, re.S)
                if m:
                    try:
                        obj = json.loads(m.group(1))
                        # If object contains recommendations key, use it
                        if isinstance(obj, dict) and "recommendations" in obj:
                            items = obj["recommendations"]
                        else:
                            items = obj
                    except Exception:
                        items = None

        # Fallback: split lines and clean them
        if not isinstance(items, list):
            raw = text if isinstance(text, str) else str(text)
            # If the LLM returned pretty-printed JSON lines, join and try once more
            joined = "".join([ln.strip() for ln in raw.splitlines()])
            try:
                maybe = json.loads(joined)
                if isinstance(maybe, list):
                    items = maybe
            except Exception:
                pass

        if not isinstance(items, list):
            items = [line.strip(" -\t\"'") for line in raw.splitlines() if line.strip()]

        items = items[:max_output]
        return RecommendationModel(recommendations=items)

