#!/usr/bin/env python
"""
VORNEQ HTTP Smoke Test

Checks critical language-prefixed public routes, authentication pages,
search/filter endpoints, unauthenticated redirects for protected marketplace
routes, public product-detail file exposure, and rough response times.

This script uses only Python's standard library and does not modify data.
"""

from __future__ import annotations

import argparse
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen


LANGUAGES = ("en", "fa", "de")
PUBLIC_PATHS = ("", "library/", "marketplace/")
AUTH_PATHS = ("accounts/login/", "accounts/signup/")
SEARCH_QUERIES = ("q=test", "type=book", "type=audio", "type=product")
PROTECTED_PATHS = (
    "marketplace/seller/",
    "marketplace/seller/create/",
    "marketplace/review/",
)
REDIRECT_STATUSES = {301, 302, 303, 307, 308}
PERFORMANCE_PATHS = ("", "library/", "marketplace/")
PERFORMANCE_TARGET_SECONDS = 2.0


class NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


NO_REDIRECT_OPENER = build_opener(NoRedirectHandler())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="VORNEQ HTTP Smoke Test")
    parser.add_argument(
        "--base-url",
        required=True,
        help="Deployment base URL, for example https://vorneq.example.com",
    )
    parser.add_argument(
        "--product-slug",
        help="Known public product slug for protected-file exposure checks",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Request timeout in seconds (default: 10)",
    )
    return parser.parse_args()


def normalize_base_url(value: str) -> str:
    value = value.strip().rstrip("/") + "/"
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("--base-url must be an absolute http(s) URL")
    return value


def deployment_url(base_url: str, language: str, path: str = "") -> str:
    return urljoin(base_url, f"{language}/{path}")


def request_url(url: str, timeout: float, follow_redirects: bool = True):
    request = Request(
        url,
        headers={"User-Agent": "VORNEQ-Smoke-Test/1.0"},
        method="GET",
    )
    started = time.perf_counter()

    try:
        if follow_redirects:
            response = urlopen(request, timeout=timeout)
        else:
            response = NO_REDIRECT_OPENER.open(request, timeout=timeout)

        elapsed = time.perf_counter() - started
        body = response.read()
        return response.status, response.geturl(), response.headers, body, elapsed

    except HTTPError as exc:
        elapsed = time.perf_counter() - started
        body = exc.read()
        return exc.code, exc.geturl(), exc.headers, body, elapsed


def check_public_url(url: str, description: str, timeout: float) -> tuple[bool, float | None]:
    try:
        status, final_url, _, _, elapsed = request_url(url, timeout, follow_redirects=True)
    except (URLError, TimeoutError, OSError) as exc:
        print(f"❌ {description} → ERROR: {exc}")
        return False, None

    if status == 200:
        print(f"✅ {description} → 200 ({elapsed:.2f}s) → {final_url}")
        return True, elapsed

    print(f"❌ {description} → {status} (expected final 200) → {final_url}")
    return False, elapsed


def check_protected_redirect(url: str, description: str, timeout: float) -> bool:
    try:
        status, _, headers, _, elapsed = request_url(url, timeout, follow_redirects=False)
    except (URLError, TimeoutError, OSError) as exc:
        print(f"❌ {description} → ERROR: {exc}")
        return False

    location = headers.get("Location", "")
    valid_login_target = "/accounts/login/" in location or "/admin/login/" in location

    if status in REDIRECT_STATUSES and valid_login_target:
        print(f"✅ {description} → {status} ({elapsed:.2f}s) → {location}")
        return True

    if status in REDIRECT_STATUSES:
        print(f"❌ {description} → {status}, but redirect target is unexpected: {location}")
        return False

    print(f"❌ {description} → {status} (expected redirect to a login page)")
    return False


def check_product_security(base_url: str, product_slug: str, timeout: float) -> bool:
    url = deployment_url(base_url, "en", f"marketplace/{product_slug}/")

    try:
        status, final_url, _, body, elapsed = request_url(url, timeout, follow_redirects=True)
    except (URLError, TimeoutError, OSError) as exc:
        print(f"❌ Product security check → ERROR: {exc}")
        return False

    if status != 200:
        print(f"❌ Product security check → {status} for {final_url}")
        return False

    html = body.decode("utf-8", errors="replace").lower()
    leaked_markers = [marker for marker in ("digital_file", "products/files/") if marker in html]

    if leaked_markers:
        print(
            "❌ Protected product-file marker exposed "
            f"({', '.join(leaked_markers)}) in {final_url}"
        )
        return False

    print(f"✅ No protected product-file path exposed ({elapsed:.2f}s) → {final_url}")
    return True


def smoke_test(base_url: str, product_slug: str | None, timeout: float) -> int:
    print(f"\n🚀 VORNEQ HTTP Smoke Test — {base_url.rstrip('/')}\n")
    all_passed = True

    print("📄 1. Public Routes\n" + "-" * 48)
    for language in LANGUAGES:
        for path in PUBLIC_PATHS:
            url = deployment_url(base_url, language, path)
            description = f"/{language}/{path}" if path else f"/{language}/"
            passed, _ = check_public_url(url, description, timeout)
            all_passed = all_passed and passed

    print("\n🔐 2. Authentication Pages\n" + "-" * 48)
    for language in LANGUAGES:
        for path in AUTH_PATHS:
            url = deployment_url(base_url, language, path)
            passed, _ = check_public_url(url, f"/{language}/{path}", timeout)
            all_passed = all_passed and passed

    print("\n🔍 3. Search & Filters (en)\n" + "-" * 48)
    for query in SEARCH_QUERIES:
        url = deployment_url(base_url, "en") + f"?{query}"
        passed, _ = check_public_url(url, f"/en/?{query}", timeout)
        all_passed = all_passed and passed

    print("\n🛡️ 4. Protected Marketplace Routes (unauthenticated)\n" + "-" * 48)
    for path in PROTECTED_PATHS:
        url = deployment_url(base_url, "en", path)
        passed = check_protected_redirect(url, f"/en/{path}", timeout)
        all_passed = all_passed and passed

    print("\n🔒 5. Protected Product File Exposure\n" + "-" * 48)
    if product_slug:
        passed = check_product_security(base_url, product_slug, timeout)
        all_passed = all_passed and passed
    else:
        print("⚠️ Skipped — provide --product-slug to test a known public product detail page")

    print("\n⏱️ 6. Approximate Response Times (en)\n" + "-" * 48)
    for path in PERFORMANCE_PATHS:
        url = deployment_url(base_url, "en", path)
        description = f"/en/{path}" if path else "/en/"
        passed, elapsed = check_public_url(url, description, timeout)
        all_passed = all_passed and passed
        if elapsed is not None:
            marker = "✅" if elapsed < PERFORMANCE_TARGET_SECONDS else "⚠️"
            print(
                f"{marker} {description} response time: {elapsed:.2f}s "
                f"(target < {PERFORMANCE_TARGET_SECONDS:.1f}s)"
            )

    print("\n" + "=" * 56)
    if all_passed:
        print("✅ ALL HTTP SMOKE CHECKS PASSED.")
        return 0

    print("❌ SOME HTTP SMOKE CHECKS FAILED — review the output above.")
    return 1


def main() -> int:
    args = parse_args()

    try:
        base_url = normalize_base_url(args.base_url)
    except ValueError as exc:
        print(f"❌ {exc}")
        return 2

    if args.timeout <= 0:
        print("❌ --timeout must be greater than zero")
        return 2

    return smoke_test(base_url, args.product_slug, args.timeout)


if __name__ == "__main__":
    sys.exit(main())
