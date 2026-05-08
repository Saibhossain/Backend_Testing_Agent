import os
from google import genai

# --- CONFIGURATION ---
BASE_URL = "https://backend-agent-test.onrender.com"
OPENAPI_FILE = "Testing Agent/openapi.json"
SCHEMA_FILE = "Testing Agent/report.schema.json"
REPORT_FILE = "report.json"

# Initialize Gemini Client
api_key = os.environ.get("GEMINI_API_KEY")
if api_key:
    client = genai.Client(api_key=api_key)
else:
    client = None