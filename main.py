import json
import time
import uuid
import requests

# Import from our custom modules
from config import BASE_URL, OPENAPI_FILE, SCHEMA_FILE, client
from tests import run_all_tests
from enricher import enrich_agent_findings
from reporter import generate_final_report


class HybridTestingAgent:
    def __init__(self):
        self.base_url = BASE_URL
        self.start_time = time.time()

        with open(OPENAPI_FILE, 'r') as f:
            self.spec = json.load(f)

        with open(SCHEMA_FILE, 'r') as f:
            self.report_schema = json.load(f)

        self.endpoints_total = len(self.spec.get("paths", {}))
        self.endpoints_tested = set()
        self.raw_findings = {}
        self.tokens = {}

    def authenticate(self):
        print("[*] Engine: Bootstrapping Auth Matrix...")
        accounts = {"alice": "alice123", "bob": "bob123"}
        for user, pwd in accounts.items():
            res = requests.post(f"{self.base_url}/auth/login", json={"username": user, "password": pwd})
            if res.status_code == 200:
                self.tokens[user] = res.json().get("access_token")

        self.tokens["invalid"] = "eyJhbGciOiJIUzI1NiIsInR5cCI.invalid.signature"
        print(f"[+] Auth Matrix loaded. Users: {list(self.tokens.keys())}")

    def log_finding(self, category, severity, endpoint, method, raw_title, expected, actual, req_data, res_data):
        sig = f"{category}_{method}_{endpoint}"
        if sig in self.raw_findings:
            return

        finding = {
            "id": f"BUG-{uuid.uuid4().hex[:8].upper()}",
            "category": category,
            "severity": severity,
            "endpoint": endpoint,
            "method": method.upper(),
            "title": raw_title,
            "description": f"Expected: {expected} | Actual: {actual}",
            "evidence": {
                "request": req_data,
                "response": res_data
            },
            "reproduction": f"Send {method.upper()} to {endpoint}",
            "expected": str(expected),
            "actual": str(actual),
            "confidence": "high"
        }
        self.raw_findings[sig] = finding
        print(f"   [!] DETECTED: {raw_title} ({category})")


if __name__ == "__main__":
    # 1. Initialize State
    agent = HybridTestingAgent()

    # 2. Setup Authentication
    agent.authenticate()

    # 3. Execute Deterministic Engine (tests.py)
    run_all_tests(agent)

    # 4. Enrich with LLM (enricher.py)
    enrich_agent_findings(agent, client)

    # 5. Generate JSON output (reporter.py)
    generate_final_report(agent)