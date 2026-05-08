import json
from google.genai import types

def enrich_agent_findings(agent, client):
    if not client:
        print("[!] GEMINI_API_KEY not set. Running in purely deterministic mode without LLM enrichment.")
        return

    print("\n[*] Reporter: Asking LLM to enrich technical descriptions...")
    for sig, finding in agent.raw_findings.items():
        prompt = f"""
        You are a Senior QA Engineer writing a bug report.
        I have detected a deterministic bug. Enhance the title and description to be highly professional.

        Category: {finding['category']}
        Endpoint: {finding['method']} {finding['endpoint']}
        Raw Issue: {finding['title']}
        Expected: {finding['expected']}
        Actual: {finding['actual']}

        Return ONLY a valid JSON object:
        {{
            "enriched_title": "Clear, concise bug title",
            "enriched_description": "Detailed explanation of the security/functional risk",
            "suggested_fix": "Brief instruction for developers to fix it"
        }}
        """
        try:
            res = client.models.generate_content(
                model='gemini-1.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )
            enriched = json.loads(res.text)
            finding["title"] = enriched.get("enriched_title", finding["title"])
            finding["description"] = enriched.get("enriched_description", finding["description"])
            finding["suggested_fix"] = enriched.get("suggested_fix", "")
        except Exception:
            pass # Fail silently and keep the deterministic text