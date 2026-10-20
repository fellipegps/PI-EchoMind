"""Read-only external checks for the published API; no login or user data."""
import argparse
from datetime import datetime, timezone
import http.client
import json
from pathlib import Path
import socket
import ssl


def check(domain: str, origin: str) -> dict:
    context = ssl.create_default_context()
    with socket.create_connection((domain, 443), timeout=15) as raw:
        with context.wrap_socket(raw, server_hostname=domain) as tls:
            certificate = tls.getpeercert()
            protocol = tls.version()

    def request(method, path, headers=None, *, https=True):
        client = (http.client.HTTPSConnection(domain, timeout=15, context=context)
                  if https else http.client.HTTPConnection(domain, timeout=15))
        try:
            client.request(method, path, headers=headers or {})
            response = client.getresponse()
            body = response.read(8192)
            return response.status, {key.lower(): value for key, value in response.getheaders()}, body
        finally:
            client.close()

    status, headers, body = request("GET", "/health")
    assert status == 200 and json.loads(body) == {"status": "ok", "service": "EchoMind API"}
    redirect, redirect_headers, _ = request("GET", "/health", https=False)
    assert redirect in {301, 302, 307, 308}
    assert redirect_headers.get("location") == f"https://{domain}/health"
    permitted, allowed_headers, _ = request("OPTIONS", "/health", {
        "Origin": origin, "Access-Control-Request-Method": "GET",
    })
    assert permitted == 200 and allowed_headers.get("access-control-allow-origin") == origin
    rejected, other_headers, _ = request("OPTIONS", "/health", {
        "Origin": "https://untrusted.example", "Access-Control-Request-Method": "GET",
    })
    assert rejected == 400 and "access-control-allow-origin" not in other_headers
    assert "max-age=" in headers.get("strict-transport-security", "")
    unauthorized, _, _ = request("GET", "/auth/me")
    # The pinned FastAPI HTTPBearer returns 403 when the header is absent;
    # invalid supplied sessions return 401. Both must deny access.
    assert unauthorized in {401, 403}
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(), "domain": domain,
        "health_status": status, "http_redirect_status": redirect,
        "certificate_hostname_and_chain_valid": True, "tls_protocol": protocol,
        "certificate_not_after": certificate["notAfter"],
        "certificate_serial": certificate["serialNumber"],
        "certificate_issuer": dict(pair for rdn in certificate["issuer"] for pair in rdn),
        "cors_production_origin": permitted == 200,
        "cors_untrusted_origin_rejected": rejected == 400,
        "hsts": True,
        "protected_endpoint_without_credentials": unauthorized,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--origin", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = check(args.domain, args.origin)
    except Exception:
        print("Public TLS/health/CORS verification did not pass; no private data requested.")
        raise SystemExit(1) from None
    if args.output:
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
