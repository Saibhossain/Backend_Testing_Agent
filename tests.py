import requests
import time
import concurrent.futures


def run_all_tests(agent):
    print("\n[*] Engine: Commencing Deterministic Test Suite...")

    # 1. Global Tests
    test_global_rate_limit(agent)
    test_global_endpoint_existence(agent)

    # 2. Advanced Category Tests
    test_input_validation(agent)
    test_schema_contract(agent)
    test_business_logic(agent)
    test_idor_authorization(agent)
    test_mass_assignment(agent)
    test_error_handling_leaks(agent)

    # 3. Iterate through OpenAPI spec for protocol & basic auth tests
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


def test_input_validation(agent):
    print("-> Auditing Input Validation (/users/me)")
    endpoint = "/users/me"
    headers = {"Authorization": f"Bearer {agent.tokens.get('alice', '')}"}
    bad_payload = {"age": "twenty-five"}

    res = requests.patch(f"{agent.base_url}{endpoint}", headers=headers, json=bad_payload)
    if res.status_code not in [422, 400]:
        agent.log_finding(
            "input_validation", "high", endpoint, "PATCH",
            "Missing Type Validation on User Profile",
            "422 Validation Error", str(res.status_code),
            {"payload": bad_payload}, {"status": res.status_code, "body": res.text}
        )


def test_schema_contract(agent):
    print("-> Auditing Schema Contract (/users/me)")
    endpoint = "/users/me"
    headers = {"Authorization": f"Bearer {agent.tokens.get('alice', '')}"}

    res = requests.get(f"{agent.base_url}{endpoint}", headers=headers)
    if res.status_code == 200:
        data = res.json()
        required_fields = ["id", "username", "email", "role"]
        missing = [field for field in required_fields if field not in data]

        if missing:
            agent.log_finding(
                "schema_contract", "high", endpoint, "GET",
                f"Missing required fields in response: {', '.join(missing)}",
                f"Response containing keys: {required_fields}", f"Missing keys: {missing}",
                {}, {"response_keys": list(data.keys())}
            )


def test_business_logic(agent):
    print("-> Auditing Business Logic (Self-Following)")
    headers = {"Authorization": f"Bearer {agent.tokens.get('alice', '')}"}
    me_res = requests.get(f"{agent.base_url}/users/me", headers=headers)

    if me_res.status_code == 200:
        alice_id = me_res.json().get("id")
        endpoint = f"/users/{alice_id}/follow"
        res = requests.post(f"{agent.base_url}{endpoint}", headers=headers)

        if res.status_code in [200, 201]:
            agent.log_finding(
                "business_logic", "medium", "/users/{user_id}/follow", "POST",
                "User can follow themselves",
                "400 Bad Request or 422 Unprocessable Entity", str(res.status_code),
                {"target_user_id": alice_id}, {"status": res.status_code, "body": res.text}
            )


def test_idor_authorization(agent):
    print("-> Auditing IDOR / Cross-User Authorization (/posts/{post_id})")
    headers = {"Authorization": f"Bearer {agent.tokens.get('alice', '')}"}
    endpoint = "/posts/99999"
    res = requests.delete(f"{agent.base_url}{endpoint}", headers=headers)

    if res.status_code == 200:
        agent.log_finding(
            "authorization", "critical", "/posts/{post_id}", "DELETE",
            "Insecure Direct Object Reference (IDOR) on Post Deletion",
            "403 Forbidden or 404 Not Found", str(res.status_code),
            {"target_post_id": 99999}, {"status": res.status_code}
        )


def test_mass_assignment(agent):
    print("-> Auditing Privilege Escalation / Mass Assignment (/users/me)")
    endpoint = "/users/me"
    headers = {"Authorization": f"Bearer {agent.tokens.get('alice', '')}"}
    malicious_payload = {"bio": "Just updated my bio", "role": "admin"}

    res = requests.patch(f"{agent.base_url}{endpoint}", headers=headers, json=malicious_payload)
    if res.status_code == 200:
        check_res = requests.get(f"{agent.base_url}{endpoint}", headers=headers)
        if check_res.status_code == 200 and check_res.json().get("role") == "admin":
            agent.log_finding(
                "authorization", "critical", endpoint, "PATCH",
                "Mass Assignment allowed Privilege Escalation",
                "API should ignore or reject protected fields like 'role'",
                "API successfully updated the user's role to admin",
                {"payload": malicious_payload}, {"status": check_res.status_code, "role_returned": "admin"}
            )


def test_error_handling_leaks(agent):
    print("-> Auditing Error Handling (/users/me)")
    endpoint = "/users/me"
    res = requests.patch(f"{agent.base_url}{endpoint}")

    if res.status_code == 500:
        body = res.text.lower()
        if "traceback" in body or "file \"" in body or "line " in body:
            agent.log_finding(
                "error_handling", "high", endpoint, "PATCH",
                "Server Exception Leaks Stack Trace",
                "Generic 500 Error Message",
                "Response contains sensitive Python/FastAPI stack trace details",
                {}, {"status": res.status_code, "body_snippet": res.text[:200]}
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
    if res_no_token.status_code not in [401, 403, 422]:
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