import streamlit as st
import json
import os
import time

# Import your existing modular engine
from config import REPORT_FILE, client
from tests import run_all_tests
from enricher import enrich_agent_findings
from reporter import generate_final_report

# We need to import the Agent class from main.py
from main import HybridTestingAgent

# --- UI Configuration ---
st.set_page_config(page_title="Sentinel API Auditor", page_icon="🛡️", layout="wide")

st.title("🛡️ Sentinel API Auditor")
st.markdown("Automated Black-Box REST API Testing Agent across 14 Vulnerability Categories.")

# --- Action Sidebar ---
with st.sidebar:
    st.header("Control Panel")
    st.markdown("Click below to initialize the agent and begin the automated testing sequence.")

    run_button = st.button("🚀 Run Full API Audit", type="primary", use_container_width=True)

    st.divider()
    st.caption("Agent Modules Loaded:")
    st.checkbox("Deterministic Test Engine", value=True, disabled=True)
    st.checkbox("Schema Validation", value=True, disabled=True)
    st.checkbox("LLM Enrichment", value=True if client else False, disabled=True)

# --- Test Execution Logic ---
if run_button:
    # Use empty containers to show real-time terminal-like updates
    status_text = st.empty()
    progress_bar = st.progress(0)

    try:
        # Step 1: Bootstrapping
        status_text.info("[*] Bootstrapping Auth Matrix...")
        agent = HybridTestingAgent()
        agent.authenticate()
        progress_bar.progress(20)
        time.sleep(0.5)  # Slight delay for visual feedback

        # Step 2: Test Execution
        status_text.warning("[*] Executing Deterministic Test Suite (Firing Payloads)...")
        run_all_tests(agent)
        progress_bar.progress(60)
        time.sleep(0.5)

        # Step 3: LLM Enrichment
        status_text.info("[*] Asking Gemini LLM to enrich technical descriptions...")
        enrich_agent_findings(agent, client)
        progress_bar.progress(85)

        # Step 4: Report Generation
        status_text.success("[*] Compiling and strictly validating report.json...")
        generate_final_report(agent)
        progress_bar.progress(100)

        status_text.success("✅ Audit Complete! Report generated successfully.")
        time.sleep(1)
        status_text.empty()  # Clear the status text
        progress_bar.empty()  # Clear the progress bar

    except Exception as e:
        st.error(f"An error occurred during the audit: {e}")

# --- Dashboard Visualization ---
if os.path.exists(REPORT_FILE):
    st.divider()

    # Load the generated report
    with open(REPORT_FILE, "r", encoding="utf-8") as f:
        report = json.load(f)

    summary = report.get("summary", {})

    # --- Metrics Row ---
    st.subheader("📊 Audit Summary")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Findings", summary.get("total", 0))
    col2.metric("Critical Bugs", summary.get("by_severity", {}).get("critical", 0))
    col3.metric("High Bugs", summary.get("by_severity", {}).get("high", 0))
    col4.metric("Coverage", f"{summary.get('coverage_percent', 0)}%")
    col5.metric("Tested Endpoints", summary.get("endpoints_tested", 0))

    st.write("")  # Spacer
    st.subheader("🐛 Vulnerability Findings")

    findings = report.get("findings", [])

    if not findings or findings[0].get("id") == "BUG-PLACEHOLDER":
        st.info("No vulnerabilities found during this run.")
    else:
        # --- Interactive Findings List ---
        for finding in findings:
            # Determine color and icon based on severity
            sev = finding.get("severity", "low")
            if sev == "critical":
                icon = "🔴"
            elif sev == "high":
                icon = "🟠"
            elif sev == "medium":
                icon = "🟡"
            else:
                icon = "🔵"

            title = f"{icon} [{finding.get('category').upper()}] {finding.get('title')}"

            with st.expander(title):
                st.markdown(f"**Endpoint:** `{finding.get('method')} {finding.get('endpoint')}`")
                st.markdown(f"**Description:** {finding.get('description')}")

                if finding.get("suggested_fix"):
                    st.markdown(f"**Suggested Fix:** {finding.get('suggested_fix')}")

                st.markdown("---")

                # Split Expected/Actual and Evidence into two columns for readability
                col_left, col_right = st.columns(2)

                with col_left:
                    st.markdown("### 🎯 Expected Behavior")
                    st.success(finding.get("expected", "N/A"))
                    st.markdown("### 📤 Request Evidence")
                    st.json(finding.get("evidence", {}).get("request", {}))

                with col_right:
                    st.markdown("### ⚠️ Actual Behavior")
                    st.error(finding.get("actual", "N/A"))
                    st.markdown("### 📥 Response Evidence")
                    st.json(finding.get("evidence", {}).get("response", {}))