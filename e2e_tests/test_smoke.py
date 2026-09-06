import re

import pytest
from playwright.sync_api import Browser, Page, expect


pytestmark = pytest.mark.django_db(transaction=True)


def _goto_ok(page: Page, url: str):
    response = page.goto(url)
    assert response is not None
    assert response.ok, f"Expected successful response for {url}, got {response.status}"
    return response


def test_home_and_discovery_search(page: Page, live_server):
    page.set_viewport_size({"width": 1440, "height": 900})
    _goto_ok(page, f"{live_server.url}/en/")

    expect(page).to_have_title(re.compile(r"VORNEQ"))
    expect(page.get_by_role("heading", name=re.compile(r"Discover.*knowledge", re.I))).to_be_visible()

    search = page.get_by_role("searchbox", name="Search VORNEQ")
    search.fill("test query")
    page.get_by_role("button", name=re.compile(r"Search")).click()

    expect(page).to_have_url(re.compile(r"/en/\?q=test(?:\+|%20)query$"))
    expect(page.get_by_role("heading", name=re.compile(r"Results for"))).to_be_visible()


def test_unified_search_api(page: Page, live_server):
    response = page.request.get(
        f"{live_server.url}/api/search/",
        params={"q": "test", "type": "article", "page_size": "5"},
    )
    assert response.ok
    payload = response.json()
    assert payload["query"] == "test"
    assert payload["normalized_query"] == "test"
    assert isinstance(payload["results"], list)
    assert payload["page"] == 1
    assert payload["page_size"] == 5


def test_library_and_marketplace_navigation(page: Page, live_server):
    _goto_ok(page, f"{live_server.url}/en/library/")
    library_link = page.get_by_role("link", name="Library")
    expect(library_link).to_have_attribute("aria-current", "page")

    _goto_ok(page, f"{live_server.url}/en/marketplace/")
    marketplace_link = page.get_by_role("link", name="Marketplace")
    expect(marketplace_link).to_have_attribute("aria-current", "page")


def test_account_login_and_profile(page: Page, live_server, e2e_user):
    _goto_ok(page, f"{live_server.url}/en/accounts/login/")
    expect(page.get_by_role("heading", name="Sign In")).to_be_visible()

    page.locator('input[name="login"]').fill(e2e_user["username"])
    page.locator('input[name="password"]').fill(e2e_user["password"])
    page.get_by_role("button", name="Sign In").click()

    expect(page.get_by_role("link", name="Sign out")).to_be_visible()
    _goto_ok(page, f"{live_server.url}/en/profile/")
    expect(page.get_by_role("link", name="Open profile")).to_have_attribute("aria-current", "page")


def test_mobile_rtl_and_dark_theme(browser: Browser, live_server):
    mobile = browser.new_context(viewport={"width": 375, "height": 667}, locale="en-US")
    mobile_page = mobile.new_page()
    _goto_ok(mobile_page, f"{live_server.url}/en/")
    expect(mobile_page.get_by_role("heading", name=re.compile(r"Discover.*knowledge", re.I))).to_be_visible()
    mobile.close()

    rtl = browser.new_context(viewport={"width": 1440, "height": 900}, locale="fa-IR")
    rtl_page = rtl.new_page()
    _goto_ok(rtl_page, f"{live_server.url}/fa/")
    expect(rtl_page.locator("html")).to_have_attribute("dir", "rtl")
    rtl.close()

    dark = browser.new_context(viewport={"width": 1440, "height": 900}, locale="en-US")
    dark_page = dark.new_page()
    dark_page.add_init_script("localStorage.setItem('vorneq-theme', 'dark');")
    _goto_ok(dark_page, f"{live_server.url}/en/")
    expect(dark_page.locator("html")).to_have_attribute("data-theme", "dark")
    dark.close()
