import requests
import time
import concurrent.futures


def run_all_tests(agent):
    print("\n[*] Engine: Commencing Deterministic Test Suite...")

    test_global_rate_limit(agent)
    test_global_endpoint_existence(agent)

    for path, methods in agent.spec.get("paths", {}).items():
        for method, details in methods.items():
            agent.endpoints_tested.add(path)
            print(f"-> Auditing {method.upper()} {path}")

            test_http_protocol(agent, path, method)
            test_authentication(agent, path, method, details)
            test_performance(agent, path, method)


def test_global_rate_limit(agent):
    print("-> Auditing Global Rate Limits (Burst test)")
    endpoint = "/auth/login"
    payload = {"username": "test", "password": "pwd"}

    def burst_req():
        return requests.post(f"{agent.base_url}{endpoint}", json=payload)

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        responses = list(executor.map(lambda _: burst_req(), range(50)))

    status_codes = [r.status_code for r in responses]
    if 429 not in status_codes:
        agent.log_finding(
            "rate_limiting", "high", endpoint, "POST",
            "No Rate Limiting on Login",
            "429 Too Many Requests after threshold",
            "No 429 response received after 50 concurrent requests",
            {"burst_count": 50},
            {"observed_status_codes": list(set(status_codes))}
        )


def test_global_endpoint_existence(agent):
    junk_endpoint = "/api/v1/does_not_exist_xyz"
    res = requests.get(f"{agent.base_url}{junk_endpoint}")
    if res.status_code != 404:
        agent.log_finding(
            "endpoint_existence", "medium", junk_endpoint, "GET",
            "Improper handling of non-existent endpoints",
            "404 Not Found", str(res.status_code),
            {"url": junk_endpoint}, {"status": res.status_code, "body": res.text}
        )


def test_http_protocol(agent, path, method):
    res = requests.options(f"{agent.base_url}{path}")
    if 'Access-Control-Allow-Origin' not in res.headers:
        agent.log_finding(
            "headers_cors", "low", path, "OPTIONS",
            "Missing CORS Headers",
            "Response includes Access-Control-Allow-Origin",
            "CORS header missing",
            {"method": "OPTIONS"}, {"headers": dict(res.headers)}
        )


def test_authentication(agent, path, method, details):
    requires_auth = False
    if "parameters" in details:
        if any(p.get("name") == "authorization" for p in details["parameters"]):
            requires_auth = True

    if not requires_auth:
        return

    url = f"{agent.base_url}{path.replace('{user_id}', '1').replace('{post_id}', '1')}"

    res_no_token = requests.request(method.upper(), url)
    if res_no_token.status_code not in [401, 403]:
        agent.log_finding(
            "authentication", "critical", path, method,
            "Broken Authentication Enforcement",
            "401 Unauthorized", str(res_no_token.status_code),
            {"headers": {}}, {"status": res_no_token.status_code}
        )

    res_inv_token = requests.request(method.upper(), url,
                                     headers={"Authorization": f"Bearer {agent.tokens.get('invalid', '')}"})
    if res_inv_token.status_code not in [401, 403]:
        agent.log_finding(
            "authentication", "high", path, method,
            "Invalid Token Accepted",
            "401 Unauthorized", str(res_inv_token.status_code),
            {"headers": {"Authorization": "Bearer invalid"}}, {"status": res_inv_token.status_code}
        )


def test_performance(agent, path, method):
    url = f"{agent.base_url}{path.replace('{user_id}', '1').replace('{post_id}', '1')}"
    headers = {"Authorization": f"Bearer {agent.tokens.get('alice', '')}"}

    start_t = time.time()
    res = requests.request(method.upper(), url, headers=headers)
    duration = time.time() - start_t

    if duration > 2.0:
        agent.log_finding(
            "performance", "medium", path, method,
            "High Endpoint Latency",
            "< 2.0 seconds", f"{duration:.2f} seconds",
            {}, {"duration": duration, "status": res.status_code}
        )