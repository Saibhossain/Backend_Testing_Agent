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

        Return ONLY a valid JSON object. Do not include markdown formatting.
        {{
            "enriched_title": "Clear, concise bug title",
            "enriched_description": "Detailed explanation of the security/functional risk",
            "suggested_fix": "Brief instruction for developers to fix it"
        }}
        """
        try:
            res = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )

            # Clean up the text just in case Gemini wraps it in markdown backticks
            clean_text = res.text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.startswith("```"):
                clean_text = clean_text[3:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]

            enriched = json.loads(clean_text.strip())

            # Overwrite the raw text with the beautifully written LLM text
            finding["title"] = enriched.get("enriched_title", finding["title"])
            finding["description"] = enriched.get("enriched_description", finding["description"])
            finding["suggested_fix"] = enriched.get("suggested_fix", "")

            print(f"   [+] Successfully enriched: {finding['category']}")

        except Exception as e:
            # Tell us exactly why it failed instead of hiding it!
            print(f"   [-] LLM Enrichment skipped for {finding['category']} due to error: {e}")