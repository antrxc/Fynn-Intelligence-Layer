from google import genai
from pydantic import BaseModel
import os
import requests
from google.genai import types
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Summary(BaseModel):
    doc_: str
    summary: str
    charts_: list[str]

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)
doc_url = "https://jfhprwwvcftxglhvbeol.supabase.co/storage/v1/object/sign/uploads/Sample%20Business%20Report.pdf?token=eyJraWQiOiJzdG9yYWdlLXVybC1zaWduaW5nLWtleV9mYTZkYzFiZC00N2Q0LTRiMzItODQ2MS1jMGQ0NDlhOTA5ZGUiLCJhbGciOiJIUzI1NiJ9.eyJ1cmwiOiJ1cGxvYWRzL1NhbXBsZSBCdXNpbmVzcyBSZXBvcnQucGRmIiwiaWF0IjoxNzU2NzkwOTc1LCJleHAiOjE3NTczOTU3NzV9.Bcpqe2TGn2Eadn7GBU8oB2JtGhcZIdo7zjpeMOcq1MQ"
# Download the PDF data
response_pdf = requests.get(doc_url)
doc_data = response_pdf.content

prompt = '''You are an expert in Financial Analysis and have good experience in converting data into understandable visuals.
Your task is to analyze the provided document and generate a concise summary along with any relevant charts or visualizations.
Also, please recommend any charts that would make the data more comprehensible.

No need for descriptions for the charts, just name the charts and what they represent with x-axis,y-axis labels.
'''
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=[
        types.Part.from_bytes(
            data=doc_data,
            mime_type='application/pdf',
        ),
        prompt
    ],
    config={
        "response_mime_type": "application/json",
        "response_schema": Summary
    }
)

summary_: Summary = response.parsed 

# Access the parsed summary fields
print(f"Document: {summary_.doc_}\n")
print(f"Summary: {summary_.summary}\n")
print(f"Charts: {summary_.charts_}")

