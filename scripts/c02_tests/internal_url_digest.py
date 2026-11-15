"""Local half of the C02 operational binding check (operator's own machine).

Usage:
    python scripts/c02_tests/internal_url_digest.py --nonce <same nonce>

Paste the *Internal Database URL* from the Render Dashboard (Connect ->
Internal) at the hidden prompt. The URL is read with getpass (no echo, not in
shell history, not a command-line argument) and never printed or stored.
Optionally pass --expected-digest with the value printed by the Render Web
Shell to get a MATCH / MISMATCH verdict.

Standard library only; no network access, no database connection.
"""
import argparse
import getpass
import hashlib
import hmac
import re
import sys
from urllib.parse import urlsplit

NONCE = re.compile(r"[0-9a-f]{32,128}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
EXPECTED_INTERNAL_HOST = "dpg-dagru1h42hec73eqr960-a"


def digest(nonce, url):
    return hmac.new(nonce.encode("ascii"), url.strip().encode("utf-8"), hashlib.sha256).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--nonce", required=True)
    parser.add_argument("--expected-digest")
    args = parser.parse_args(argv)
    if not NONCE.fullmatch(args.nonce):
        sys.exit("nonce must be 32-128 lowercase hex characters")
    if args.expected_digest is not None and not DIGEST.fullmatch(args.expected_digest):
        sys.exit("expected digest must be 64 lowercase hex characters")
    url = getpass.getpass("Render Dashboard Internal Database URL (hidden): ")
    if not url.strip():
        sys.exit("empty URL")
    host = (urlsplit(url.strip()).hostname or "").lower()
    print("DASHBOARD_URL_HOST_IS_INTERNAL_EXACT:", host == EXPECTED_INTERNAL_HOST)
    value = digest(args.nonce, url)
    print("DASHBOARD_INTERNAL_URL_HMAC_SHA256:", value)
    if args.expected_digest is not None:
        verdict = hmac.compare_digest(value, args.expected_digest)
        print("C02_DIGEST_COMPARISON:", "MATCH" if verdict else "MISMATCH")
        return 0 if verdict else 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
