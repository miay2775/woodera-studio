#!/usr/bin/env python3
"""Synchronize the WOODERA domain DNS in Beget with dns/desired.json.

The script is intentionally scoped to woodera-studio.ru and only uses:
- domain/getList
- domain/getSubdomainList
- domain/addSubdomainVirtual
- dns/getData
- dns/changeRecords

Credentials are read only from BEGET_LOGIN and BEGET_API_PASSWORD.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

API_BASE = "https://api.beget.com/api"
ALLOWED_DOMAIN = "woodera-studio.ru"
DESIRED_PATH = Path(__file__).with_name("desired.json")


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def api_call(method: str, payload: dict | None = None):
    login = os.environ.get("BEGET_LOGIN", "").strip()
    password = os.environ.get("BEGET_API_PASSWORD", "")
    if not login or not password:
        fail("BEGET_LOGIN / BEGET_API_PASSWORD are not configured")

    params = {
        "login": login,
        "passwd": password,
        "output_format": "json",
    }
    if payload is not None:
        params["input_format"] = "json"
        params["input_data"] = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    url = f"{API_BASE}/{method}?{urllib.parse.urlencode(params)}"
    # Do not log the URL: it contains credentials.
    req = urllib.request.Request(url, headers={"User-Agent": "WOODERA-DNS-Bridge/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        fail(f"Beget API request failed for {method}: {exc}")

    if data.get("status") != "success":
        fail(f"Beget API top-level error for {method}: {data.get('error_text') or data}")

    answer = data.get("answer", {})
    if isinstance(answer, dict) and answer.get("status") not in (None, "success"):
        fail(f"Beget API method error for {method}: {answer.get('error_text') or answer}")
    return answer.get("result") if isinstance(answer, dict) and "result" in answer else answer


def normalize_records(records):
    out = []
    for rec in records or []:
        value = str(rec.get("value", ""))
        priority = int(rec.get("priority") or 0)
        out.append({"priority": priority, "value": value})
    return out


def main() -> None:
    desired = json.loads(DESIRED_PATH.read_text(encoding="utf-8"))
    domain = desired.get("domain")
    if domain != ALLOWED_DOMAIN:
        fail(f"Refusing to operate on domain {domain!r}; allowed domain is {ALLOWED_DOMAIN}")

    wanted_a = [str(x) for x in desired.get("root_a", [])]
    if set(wanted_a) != {
        "185.199.108.153",
        "185.199.109.153",
        "185.199.110.153",
        "185.199.111.153",
    }:
        fail("Root A records are not the approved GitHub Pages addresses")

    cname = str(desired.get("www_cname", "")).rstrip(".")
    if cname != "miay2775.github.io":
        fail("www CNAME is not the approved GitHub Pages target")

    print(f"Reading current DNS for {domain}...")
    root = api_call("dns/getData", {"fqdn": domain})
    if not isinstance(root, dict) or not root.get("is_beget_dns"):
        fail("Domain is not currently using Beget DNS")

    records = root.get("records") or {}
    current_a = [str(r.get("value")) for r in records.get("A", [])]
    print("Current root A:", ", ".join(current_a) if current_a else "(none)")

    # Preserve mail-related records exactly as they are. Replace only the root A set.
    new_root_records = {
        "A": [{"priority": 0, "value": ip} for ip in wanted_a],
        "MX": normalize_records(records.get("MX", [])),
        "TXT": normalize_records(records.get("TXT", [])),
    }
    print("Applying approved GitHub Pages root A records while preserving MX/TXT...")
    result = api_call("dns/changeRecords", {"fqdn": domain, "records": new_root_records})
    if result is not True:
        fail(f"Unexpected result while changing root records: {result!r}")

    domains = api_call("domain/getList")
    domain_row = next((d for d in (domains or []) if d.get("fqdn") == domain), None)
    if not domain_row:
        fail("Could not find the domain in domain/getList")
    domain_id = int(domain_row["id"])

    www_fqdn = f"www.{domain}"
    subdomains = api_call("domain/getSubdomainList")
    www = next((s for s in (subdomains or []) if s.get("fqdn") == www_fqdn), None)
    if not www:
        print(f"Creating virtual subdomain {www_fqdn}...")
        api_call("domain/addSubdomainVirtual", {"subdomain": "www", "domain_id": domain_id})
    else:
        print(f"Subdomain {www_fqdn} already exists.")

    print(f"Setting {www_fqdn} CNAME -> {cname}...")
    result = api_call(
        "dns/changeRecords",
        {
            "fqdn": www_fqdn,
            "records": {"CNAME": [{"priority": 10, "value": cname}]},
        },
    )
    if result is not True:
        fail(f"Unexpected result while changing www CNAME: {result!r}")

    # Verify through Beget after applying.
    root_after = api_call("dns/getData", {"fqdn": domain})
    www_after = api_call("dns/getData", {"fqdn": www_fqdn})
    root_after_a = {str(r.get("value")) for r in (root_after.get("records") or {}).get("A", [])}
    www_cnames = {str(r.get("value", "")).rstrip(".") for r in (www_after.get("records") or {}).get("CNAME", [])}

    if root_after_a != set(wanted_a):
        fail(f"Root verification failed. Beget reports A={sorted(root_after_a)}")
    if cname not in www_cnames:
        fail(f"www verification failed. Beget reports CNAME={sorted(www_cnames)}")

    print("SUCCESS: Beget DNS now matches the approved WOODERA GitHub Pages configuration.")


if __name__ == "__main__":
    main()
