from pydantic import BaseModel
from typing import List, Union, Optional
from tools.llm_client import get_client, generate_content
from tools.chunker import DocumentChunker
from AgentContracts.recommendations import RECOMMENDATIONS_PROMPT
import json
import re

class RecommendationModel(BaseModel):
    recommendations: List[str]


class RecommendationService:
    """Generate recommendations from a text or document input using gemini-2.5-pro.

    The input may be a str (plain text) or bytes (file content, e.g., PDF).
    Handles large files using chunking and hierarchical processing.
    """

    MODEL_NAME = "gemini-2.5-flash"
    LIGHT_MODEL = "gemini-1.5-flash"  # For large-file analysis

    def __init__(self):
        self.client = get_client()
        self.chunker = DocumentChunker()

    def _extract_text(self, input_data: Union[str, bytes], mime_type: Optional[str] = None) -> str:
        """Extract text from bytes or return string."""
        if isinstance(input_data, bytes):
            try:
                # For CSV, simple UTF-8 decoding often works
                if mime_type == "text/csv":
                    return input_data.decode('utf-8')
                # For other formats, fall back to simple decoding
                return input_data.decode('utf-8', errors='ignore')
            except UnicodeDecodeError:
                return str(input_data)  # Fallback
        return input_data

    def _make_contents(self, input_data: Union[str, bytes], mime_type: Optional[str] = None):
        """Return a contents list suitable for client.models.generate_content.

        If input_data is bytes, include it as a Part (PDF/binary). Otherwise pass text.
        """
        system = RECOMMENDATIONS_PROMPT

        if isinstance(input_data, bytes):
            # Lazy import of types
            from google.genai import types

            part = types.Part.from_bytes(data=input_data, mime_type=mime_type or "application/pdf")
            return [system, part]

        return [system, input_data]

    def generate_recommendations(self, input_data: Union[str, bytes], max_output: int = 5, mime_type: Optional[str] = None) -> RecommendationModel:
        # For text input or small files, use the standard approach
        if isinstance(input_data, str) or (isinstance(input_data, bytes) and len(input_data) < 1000000):  # Less than ~1MB
            contents = self._make_contents(input_data, mime_type=mime_type)
            response = generate_content(
                model=self.MODEL_NAME, contents=contents, config={"response_mime_type": "application/json"}
            )
        else:
            # For large files, use chunking
            text = self._extract_text(input_data, mime_type)
            chunks = self.chunker.chunk_text(text)
            
            # Process chunks to get recommendations from each part
            all_recommendations = []
            for i, chunk in enumerate(chunks[:4]):  # Process up to 4 chunks
                chunk_response = generate_content(
                    model=self.LIGHT_MODEL,
                    contents=[RECOMMENDATIONS_PROMPT, chunk],
                    config={"response_mime_type": "application/json"},
                )
                
                # Extract recommendations from chunk response
                chunk_recs = self._parse_response(chunk_response)
                if chunk_recs and isinstance(chunk_recs, list):
                    all_recommendations.extend(chunk_recs[:2])  # Take top 2 from each chunk
            
            # Generate final combined recommendations
            if all_recommendations:
                meta_prompt = f"{RECOMMENDATIONS_PROMPT}\n\nBased on these preliminary recommendations from different sections, create a final consolidated list of the most important recommendations:\n"
                meta_prompt += "\n".join([f"- {rec}" for rec in all_recommendations])
                
                response = generate_content(
                    model=self.MODEL_NAME,
                    contents=[meta_prompt],
                    config={"response_mime_type": "application/json"},
                )
            else:
                # Fallback if no recommendations were extracted from chunks
                response = generate_content(
                    model=self.MODEL_NAME,
                    contents=[RECOMMENDATIONS_PROMPT, text[:10000]],  # Use first part of text
                    config={"response_mime_type": "application/json"},
                )

        return self._parse_response(response)
        
    def _parse_response(self, response):
        """Robustly parse the response to extract recommendations."""
        parsed = getattr(response, "parsed", None)
        text = getattr(response, "text", None) or (response if isinstance(response, str) else None)

        items = None
        if parsed:
            if isinstance(parsed, dict) and "recommendations" in parsed:
                items = parsed["recommendations"]
            else:
                items = parsed
        else:
            # Try direct JSON load
            try:
                if isinstance(text, str):
                    parsed_json = json.loads(text)
                    if isinstance(parsed_json, dict) and "recommendations" in parsed_json:
                        items = parsed_json["recommendations"]
                    else:
                        items = parsed_json
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
                if isinstance(maybe, dict) and "recommendations" in maybe:
                    items = maybe["recommendations"]
                elif isinstance(maybe, list):
                    items = maybe
            except Exception:
                pass

        if not isinstance(items, list):
            items = [line.strip(" -\t\"'") for line in raw.splitlines() if line.strip()]

        # Limit to 10 items by default if max_output wasn't specified
        max_items = 10
        items = items[:max_items]
        return RecommendationModel(recommendations=items)

