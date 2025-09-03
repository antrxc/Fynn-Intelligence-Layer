from pydantic import BaseModel
from typing import List, Optional, Union
from tools.llm_client import get_client, generate_content
from tools.chunker import DocumentChunker
from AgentContracts.summary import SUMMARY_PROMPT
import json


class SummaryModel(BaseModel):
    title: Optional[str] = None
    summary: str
    key_points: List[str] = []
    recommended_charts: List[str] = []


class SummaryService:
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
                # For PDF, consider using PyPDF2 or similar library
                # This would require additional dependencies
                return input_data.decode('utf-8', errors='ignore')
            except UnicodeDecodeError:
                return str(input_data)  # Fallback
        return input_data

    def _make_contents(self, input_data: Union[str, bytes], mime_type: Optional[str] = None):
        system = SUMMARY_PROMPT

        if isinstance(input_data, bytes):
            from google.genai import types
            part = types.Part.from_bytes(
                data=input_data, mime_type=mime_type or "application/pdf"
            )
            return [system, part]

        return [system, input_data]

    def generate_summary(
        self, input_data: Union[str, bytes], max_key_points: int = 5, mime_type: Optional[str] = None
    ) -> SummaryModel:
        # For text input or small files, use the standard approach
        if isinstance(input_data, str) or len(input_data) < 1000000:  # Less than ~1MB
            contents = self._make_contents(input_data, mime_type=mime_type)
            response = generate_content(
                model=self.MODEL_NAME,
                contents=contents,
                config={"response_mime_type": "application/json"},
            )
        else:
            # For large files, use chunking
            text = self._extract_text(input_data, mime_type)
            chunks = self.chunker.chunk_text(text)
            
            # Process the first few chunks to get a representative summary
            chunk_summaries = []
            for i, chunk in enumerate(chunks[:5]):  # Process up to 5 chunks
                chunk_response = generate_content(
                    model=self.LIGHT_MODEL,
                    contents=[SUMMARY_PROMPT, chunk],
                    config={"response_mime_type": "application/json"},
                )
                # Extract summary from chunk response
                try:
                    parsed = getattr(chunk_response, "parsed", None)
                    if parsed and isinstance(parsed, dict) and "summary" in parsed:
                        chunk_summaries.append(parsed["summary"])
                    else:
                        chunk_summaries.append(getattr(chunk_response, "text", "")[:300])
                except Exception:
                    chunk_summaries.append(chunk[:200])
            
            # Generate final summary from the chunk summaries
            meta_prompt = f"{SUMMARY_PROMPT}\n\nBased on these excerpt summaries from a larger document, create a comprehensive summary:\n"
            meta_prompt += "\n\n".join([f"Excerpt {i+1}: {s}" for i, s in enumerate(chunk_summaries)])
            
            response = generate_content(
                model=self.MODEL_NAME,
                contents=[meta_prompt],
                config={"response_mime_type": "application/json"},
            )

        try:
            # Try to parse using model's parsed response
            parsed = getattr(response, "parsed", None)
            if parsed and isinstance(parsed, dict):
                # If we have a valid dict with the expected fields, create the model
                if "summary" in parsed:
                    return SummaryModel(**parsed)
                else:
                    # Extract summary from nested structure if needed
                    summary_text = str(parsed)
                    return SummaryModel(summary=summary_text)
                
        except Exception as e:
            print(f"Error parsing response as JSON: {e}")
            
        # Fallback: try to extract JSON from text response
        try:
            response_text = getattr(response, "text", "")
            # Look for JSON block in response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                data = json.loads(json_str)
                
                # Check if the data has a summary field
                if isinstance(data, dict) and "summary" in data:
                    return SummaryModel(**data)
                else:
                    # Create a summary using the entire JSON structure
                    return SummaryModel(summary=json_str)
                
        except Exception as e:
            print(f"Error extracting JSON from text: {e}")
        
        # Last resort: create minimal object with whatever text we have
        text_response = getattr(response, "text", "Failed to generate summary")
        return SummaryModel(
            summary=text_response,
            key_points=[]
        )

        # Normalize chart entries
        normalized_charts: List[str] = []
        for entry in recommended_charts:
            if isinstance(entry, str):
                normalized_charts.append(entry)
            elif isinstance(entry, dict):
                # Attempt to build a concise chart description
                name = entry.get("chart_name") or entry.get("chart_type") or "chart"
                x = entry.get("x_axis") or entry.get("x") or "x"
                y = entry.get("y_axis") or entry.get("y") or "y"
                normalized_charts.append(f"{name} (x: {x}, y: {y})")
            else:
                normalized_charts.append(str(entry))

        # Ensure key_points is always a list
        if isinstance(key_points, str):
            key_points = [kp.strip() for kp in key_points.splitlines() if kp.strip()]

        return SummaryModel(
            title=title,
            summary=summary,
            key_points=key_points[:max_key_points],
            recommended_charts=normalized_charts,
        )