from pydantic import BaseModel
from typing import List, Dict, Optional, Union
from tools.llm_client import get_client
from AgentContracts.visuals import VISUALS_PROMPT

class ChartSpec(BaseModel):
	chart_type: str
	purpose: Optional[str] = None
	x_axis: Optional[str] = None
	y_axis: Optional[str] = None
	notes: Optional[str] = None


class VisualsService:
	MODEL_NAME = "gemini-2.5-flash"

	def __init__(self):
		self.client = get_client()

	def _make_contents(self, input_data: Union[str, bytes], mime_type: Optional[str] = None):
		system = (VISUALS_PROMPT)

		if isinstance(input_data, bytes):
			from google.genai import types

			part = types.Part.from_bytes(data=input_data, mime_type=mime_type or "application/pdf")
			return [system, part]

		return [system, input_data]

	def recommend_charts(self, input_data: Union[str, bytes], max_charts: int = 5, mime_type: Optional[str] = None) -> List[ChartSpec]:
		contents = self._make_contents(input_data, mime_type=mime_type)
		from tools.llm_client import generate_content

		response = generate_content(
			model=self.MODEL_NAME, contents=contents, config={"response_mime_type": "application/json"}
		)

		parsed = getattr(response, "parsed", None)
		import json, re

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
					}
					specs.append(ChartSpec(**safe))
				elif isinstance(entry, str):
					specs.append(ChartSpec(chart_type="text_summary", purpose=entry[:200]))
		elif isinstance(data, dict):
			items = data.get("charts") or data.get("recommended_charts") or []
			for entry in items[:max_charts]:
				if isinstance(entry, dict):
					safe = {
						"chart_type": entry.get("chart_type") or entry.get("chart_name") or "chart",
						"purpose": entry.get("purpose") or entry.get("description"),
						"x_axis": entry.get("x_axis") or entry.get("x"),
						"y_axis": entry.get("y_axis") or entry.get("y"),
						"notes": entry.get("notes"),
					}
					specs.append(ChartSpec(**safe))

		# If still empty, fallback to a single text summary
		if not specs:
			raw = getattr(response, "text", str(response))
			specs = [ChartSpec(chart_type="text_summary", purpose=raw[:200])]

		return specs

