from pydantic import BaseModel
from typing import List, Dict, Optional, Union
from tools.llm_client import get_client, generate_content
from tools.chunker import DocumentChunker
from AgentContracts.visuals import VISUALS_PROMPT
import json
import re

class ChartSpec(BaseModel):
    chart_type: str
    purpose: Optional[str] = None
    x_axis: Optional[str] = None
    y_axis: Optional[str] = None
    notes: Optional[str] = None
    data: Optional[Dict] = None  # For Chart.js compatible chart data/config


class VisualsService:
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
        system = VISUALS_PROMPT

        if isinstance(input_data, bytes):
            from google.genai import types

            part = types.Part.from_bytes(data=input_data, mime_type=mime_type or "application/pdf")
            return [system, part]

        return [system, input_data]

    def recommend_charts(self, input_data: Union[str, bytes], max_charts: int = 5, mime_type: Optional[str] = None) -> List[ChartSpec]:
        # For text input or small files, use the standard approach
        if isinstance(input_data, str) or (isinstance(input_data, bytes) and len(input_data) < 1000000):  # Less than ~1MB
            contents = self._make_contents(input_data, mime_type=mime_type)
            response = generate_content(
                model=self.MODEL_NAME, 
                contents=contents, 
                config={"response_mime_type": "application/json"}
            )
        else:
            # For large files, use chunking
            text = self._extract_text(input_data, mime_type)
            chunks = self.chunker.chunk_text(text)
            
            # Process chunks to identify potential visualizations from each part
            all_chart_specs = []
            for i, chunk in enumerate(chunks[:3]):  # Process up to 3 chunks
                enhanced_prompt = (
                    f"{VISUALS_PROMPT}\n\n"
                    f"This is part {i+1} of a larger document. "
                    f"Identify the most meaningful visualizations for this section."
                )
                
                chunk_response = generate_content(
                    model=self.LIGHT_MODEL,
                    contents=[enhanced_prompt, chunk],
                    config={"response_mime_type": "application/json"},
                )
                
                # Extract chart recommendations from chunk response
                chunk_charts = self._parse_response(chunk_response, max_charts=2)  # Limit to 2 per chunk
                if chunk_charts:
                    all_chart_specs.extend(chunk_charts)
            
            # If we found charts from chunks, use them directly
            if all_chart_specs:
                return all_chart_specs[:max_charts]
                
            # Fallback: generate charts from a summary of the document
            summary_prompt = f"{VISUALS_PROMPT}\n\nThis is a large document. Based on your analysis, recommend the most informative visualizations."
            response = generate_content(
                model=self.MODEL_NAME,
                contents=[summary_prompt, text[:10000]],  # Use first part of text
                config={"response_mime_type": "application/json"},
            )

        return self._parse_response(response, max_charts)
        
    def _parse_response(self, response, max_charts: int = 5) -> List[ChartSpec]:
        """Parse the response to extract chart specifications."""
        parsed = getattr(response, "parsed", None)
        data = None
        
        if parsed:
            data = parsed
        else:
            text = getattr(response, "text", "")
            try:
                data = json.loads(text)
            except Exception:
                # Try to extract JSON array/object substrings
                m = re.search(r"(\[.*\])", text, re.S)
                if m:
                    try:
                        data = json.loads(m.group(1))
                    except Exception:
                        data = None
                else:
                    m = re.search(r"(\{.*\})", text, re.S)
                    if m:
                        try:
                            data = json.loads(m.group(1))
                        except Exception:
                            data = None
                    else:
                        data = None

        specs: List[ChartSpec] = []
        # If data is a list of dicts, convert to ChartSpec forgivingly
        if isinstance(data, list):
            for entry in data[:max_charts]:
                if isinstance(entry, dict):
                    # allow missing keys by building a safe dict
                    safe = {
                        "chart_type": entry.get("chart_type") or entry.get("chart_name") or "chart",
                        "purpose": entry.get("purpose") or entry.get("description"),
                        "x_axis": entry.get("x_axis") or entry.get("x"),
                        "y_axis": entry.get("y_axis") or entry.get("y"),
                        "notes": entry.get("notes"),
                        # Add Chart.js data if available
                        "data": entry.get("data") or entry.get("chart_data"),
                    }
                    specs.append(ChartSpec(**safe))
                elif isinstance(entry, str):
                    specs.append(ChartSpec(chart_type="text_summary", purpose=entry[:200]))
        elif isinstance(data, dict):
            # Check if it's a Chart.js spec directly
            if "type" in data and ("data" in data or "options" in data):
                specs.append(ChartSpec(
                    chart_type=data.get("type", "chart"),
                    purpose="Chart.js visualization",
                    data=data
                ))
            else:
                items = data.get("charts") or data.get("recommended_charts") or []
                for entry in items[:max_charts]:
                    if isinstance(entry, dict):
                        safe = {
                            "chart_type": entry.get("chart_type") or entry.get("chart_name") or "chart",
                            "purpose": entry.get("purpose") or entry.get("description"),
                            "x_axis": entry.get("x_axis") or entry.get("x"),
                            "y_axis": entry.get("y_axis") or entry.get("y"),
                            "notes": entry.get("notes"),
                            "data": entry.get("data") or entry.get("chart_data") if isinstance(entry.get("data") or entry.get("chart_data"), dict) else {},
                        }
                        specs.append(ChartSpec(**safe))

        # If still empty, fallback to a single text summary
        if not specs:
            raw = getattr(response, "text", str(response))
            specs = [ChartSpec(chart_type="text_summary", purpose=raw[:200])]

        return specs

