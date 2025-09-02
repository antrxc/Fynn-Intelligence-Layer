from pydantic import BaseModel
from typing import List, Optional, Union
from tools.llm_client import get_client


class SummaryModel(BaseModel):
    title: Optional[str] = None
    summary: str
    key_points: List[str] = []
    recommended_charts: List[str] = []


class SummaryService:
    MODEL_NAME = "gemini-2.5-pro"

    def __init__(self):
        self.client = get_client()

    def _make_contents(self, input_data: Union[str, bytes], mime_type: Optional[str] = None):
        system = (
            "You are an expert summarizer. Produce a short title, a concise summary paragraph, "
            "a list of key points and a list of recommended chart names with axes. Return JSON."
        )

        if isinstance(input_data, bytes):
            from google.genai import types

            part = types.Part.from_bytes(data=input_data, mime_type=mime_type or "application/pdf")
            return [system, part]

        return [system, input_data]

    def generate_summary(self, input_data: Union[str, bytes], max_key_points: int = 5, mime_type: Optional[str] = None) -> SummaryModel:
        contents = self._make_contents(input_data, mime_type=mime_type)

        from tools.llm_client import generate_content

        response = generate_content(
            model=self.MODEL_NAME, contents=contents, config={"response_mime_type": "application/json"}
        )

        parsed = getattr(response, "parsed", None)
        if parsed:
            data = parsed
        else:
            import json

            try:
                data = json.loads(getattr(response, "text", ""))
            except Exception:
                txt = getattr(response, "text", str(response))
                return SummaryModel(summary=txt, key_points=[txt[:200]])

        title = data.get("title") if isinstance(data, dict) else None
        summary = data.get("summary") if isinstance(data, dict) else str(data)
        key_points = data.get("key_points", []) if isinstance(data, dict) else []
        recommended_charts = data.get("recommended_charts", []) if isinstance(data, dict) else []

        # Normalize chart entries: allow either strings or dicts; convert dicts to readable strings
        normalized_charts: list[str] = []
        for entry in recommended_charts:
            if isinstance(entry, str):
                normalized_charts.append(entry)
            from pydantic import BaseModel
            from typing import List, Optional, Union
            from tools.llm_client import get_client


            class SummaryModel(BaseModel):
                title: Optional[str] = None
                summary: str
                key_points: List[str] = []
                recommended_charts: List[str] = []


            class SummaryService:
                MODEL_NAME = "gemini-2.5-pro"

                def __init__(self):
                    self.client = get_client()

                def _make_contents(self, input_data: Union[str, bytes], mime_type: Optional[str] = None):
                    system = (
                        "You are an expert summarizer. Produce a short title, a concise summary paragraph, "
                        "a list of key points and a list of recommended chart names with axes. Return JSON."
                    )

                    if isinstance(input_data, bytes):
                        from google.genai import types

                        part = types.Part.from_bytes(data=input_data, mime_type=mime_type or "application/pdf")
                        return [system, part]

                    return [system, input_data]

                def generate_summary(self, input_data: Union[str, bytes], max_key_points: int = 5, mime_type: Optional[str] = None) -> SummaryModel:
                    contents = self._make_contents(input_data, mime_type=mime_type)

                    from tools.llm_client import generate_content

                    response = generate_content(
                        model=self.MODEL_NAME, contents=contents, config={"response_mime_type": "application/json"}
                    )

                    parsed = getattr(response, "parsed", None)
                    if parsed:
                        data = parsed
                    else:
                        import json

                        try:
                            data = json.loads(getattr(response, "text", ""))
                        except Exception:
                            txt = getattr(response, "text", str(response))
                            return SummaryModel(summary=txt, key_points=[txt[:200]])

                    title = data.get("title") if isinstance(data, dict) else None
                    summary = data.get("summary") if isinstance(data, dict) else str(data)
                    key_points = data.get("key_points", []) if isinstance(data, dict) else []
                    recommended_charts = data.get("recommended_charts", []) if isinstance(data, dict) else []

                    # Normalize chart entries: allow either strings or dicts; convert dicts to readable strings
                    normalized_charts: list[str] = []
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

                    if isinstance(key_points, str):
                        key_points = [kp.strip() for kp in key_points.splitlines() if kp.strip()][:max_key_points]

                    return SummaryModel(title=title, summary=summary, key_points=key_points[:max_key_points], recommended_charts=normalized_charts)



