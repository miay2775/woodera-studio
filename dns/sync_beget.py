#!/usr/bin/env python3
import json, os, sys, urllib.parse, urllib.request
from pathlib import Path

API = "https://api.beget.com/api"
DOMAIN = "woodera-studio.ru"
A_SET = ["185.199.108.153","185.199.109.153","185.199.110.153","185.199.111.153"]
CNAME = "miay2775.github.io"
MX = [{"priority":10,"value":"mx1.beget.com"},{"priority":20,"value":"mx2.beget.com"}]
TXT = [{"priority":0,"value":"v=spf1 redirect=beget.com"}]


def fail(msg):
    print("ERROR:", msg, file=sys.stderr)
    raise SystemExit(1)


def call(method, payload=None):
    login = os.environ.get("BEGET_LOGIN", "").strip()
    password = os.environ.get("BEGET_PASSWORD", "")
    if not login or not password:
        fail("GitHub secrets are missing")
    p = {"login":login,"passwd":password,"output_format":"json"}
    if payload is not None:
        p["input_format"] = "json"
        p["input_data"] = json.dumps(payload, separators=(",",":"))
    req = urllib.request.Request(f"{API}/{method}?{urllib.parse.urlencode(p)}")
    try:
        data = json.loads(urllib.request.urlopen(req, timeout=30).read().decode())
    except Exception as e:
        fail(f"API request failed: {e}")
    if data.get("status") != "success": fail(data)
    ans = data.get("answer", {})
    if isinstance(ans, dict) and ans.get("status") not in (None, "success"):
        fail(ans)
    return ans.get("result") if isinstance(ans, dict) and "result" in ans else ans


def main():
    desired = json.loads(Path(__file__).with_name("desired.json").read_text())
    if desired.get("domain") != DOMAIN: fail("Unexpected domain")
    if set(desired.get("root_a", [])) != set(A_SET): fail("Unexpected A records")
    if str(desired.get("www_cname", "")).rstrip(".") != CNAME: fail("Unexpected CNAME")

    root = call("dns/getData", {"fqdn":DOMAIN})
    if not isinstance(root, dict) or not root.get("is_beget_dns"): fail("Domain is not on Beget DNS")
    print("Beget API access OK")

    ok = call("dns/changeRecords", {"fqdn":DOMAIN,"records":{"A":[{"priority":0,"value":x} for x in A_SET],"MX":MX,"TXT":TXT}})
    if ok is not True: fail(f"Root DNS update returned {ok!r}")
    print("Root DNS updated")

    domains = call("domain/getList") or []
    row = next((x for x in domains if x.get("fqdn") == DOMAIN), None)
    if not row: fail("Domain not found")
    subs = call("domain/getSubdomainList") or []
    fqdn = "www." + DOMAIN
    if not any(x.get("fqdn") == fqdn for x in subs):
        call("domain/addSubdomainVirtual", {"subdomain":"www","domain_id":int(row["id"])})
        print("www created")
    ok = call("dns/changeRecords", {"fqdn":fqdn,"records":{"CNAME":[{"priority":10,"value":CNAME}]}})
    if ok is not True: fail(f"www update returned {ok!r}")
    print("SUCCESS: DNS accepted by Beget")


if __name__ == "__main__": main()
