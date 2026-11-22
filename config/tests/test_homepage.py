import re
from html.parser import HTMLParser
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils.translation import override


class HomepageSimplificationTests(TestCase):
    """Homepage V2 contract: one task-focused AI workspace screen.

    The marketing sections (signal navigation, evidence demo, capabilities,
    how-it-works, trust, principles, final CTA) were removed by owner request.
    """

    REMOVED_SECTION_IDS = ("start", "capabilities", "how-it-works", "trust", "principles", "explore")

    def get_english_home(self, params=None):
        with override("en"):
            return self.client.get(reverse("home"), data=params or {})

    def test_homepage_is_single_task_focused_workspace(self):
        response = self.get_english_home()
        html = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="vq-home"')
        self.assertContains(response, "What do you need today?")
        for section_id in self.REMOVED_SECTION_IDS:
            self.assertNotIn(f'id="{section_id}"', html)
        self.assertNotIn("data-homepage-signal-section", html)
        self.assertNotIn("world-evidence-panel", html)
        self.assertNotContains(response, 'id="discoveries"')
        self.assertNotContains(response, "Featured Discoveries")
        self.assertNotContains(response, "Latest Discoveries")

    def test_signal_navigation_removed(self):
        response = self.get_english_home()
        self.assertNotContains(response, 'class="homepage-signal-nav')
        self.assertNotContains(response, "js/homepage-signal-nav-v2")
        self.assertNotContains(response, "js/evidence-signal-v2-3")
        self.assertContains(response, 'class="standalone-nav')

    def test_signal_navigation_is_homepage_only(self):
        with override("en"):
            response = self.client.get(reverse("discover"))

        self.assertNotContains(
            response,
            'class="homepage-signal-nav',
        )

    def test_homepage_search_is_primary_entry_without_refinement(self):
        response = self.get_english_home()
        html = response.content.decode()

        with override("en"):
            search_url = reverse("search_page")

        self.assertEqual(html.count('role="search"'), 1)
        self.assertContains(response, f'action="{search_url}"')
        self.assertContains(response, 'name="q"')
        self.assertNotContains(response, 'name="type"')
        self.assertNotContains(response, 'name="item_type"')
        self.assertNotContains(response, 'name="media_type"')
        self.assertNotContains(response, 'name="category"')
        self.assertNotContains(response, "Advanced filters")
        self.assertNotContains(response, "Quick content filters")
        self.assertNotContains(response, "Open advanced search")

    def test_public_tools_route_to_existing_surfaces(self):
        response = self.get_english_home()
        with override("en"):
            expected_urls = (
                reverse("search_page"),
                reverse("discover"),
                reverse("marketplace:index"),
                reverse("account_login"),
            )
        for url in expected_urls:
            self.assertContains(response, f'href="{url}"')
        self.assertContains(response, "Your tools")
        self.assertNotContains(response, "Checkout")
        self.assertNotContains(response, "Entitlement")
        self.assertNotContains(response, "Search results")

    def test_private_tools_only_for_authenticated_users(self):
        with override("en"):
            private_urls = (
                reverse("documents:list"),
                reverse("notes:list"),
                reverse("documents:create"),
                reverse("notes:create"),
                reverse("platform_shell:personal_home"),
            )
        anonymous = self.get_english_home().content.decode()
        for url in private_urls:
            self.assertNotIn(f'href="{url}"', anonymous)

        user = get_user_model().objects.create_user(username="home-v2-user", password="pass")
        self.client.force_login(user)
        authenticated = self.get_english_home()
        for url in private_urls:
            self.assertContains(authenticated, f'href="{url}"')
        self.assertContains(authenticated, "Welcome back. What do you need?")
        self.assertNotContains(authenticated, "Use your own workspace")

    def test_ai_is_labelled_honestly(self):
        response = self.get_english_home()
        self.assertContains(response, "AI answers · coming soon")
        self.assertContains(response, "AI answers are not enabled yet.")
        self.assertContains(response, 'aria-disabled="true"')

    def test_anonymous_home_runs_no_database_queries(self):
        with CaptureQueriesContext(connection) as ctx:
            response = self.get_english_home()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(ctx.captured_queries), 0)

    def test_home_does_not_execute_search_for_query_parameters(self):
        response = self.get_english_home({"q": "anything", "type": "product"})

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Search results")
        self.assertNotContains(response, "No results found")
        self.assertNotContains(response, 'id="discoveries"')


class _DiscoverVisibleText(HTMLParser):
    """Approximate visible text with block boundaries; ignore hidden markup.

    This is a conservative HTML test helper, not a browser layout engine.
    Inline descendants share a text segment; independent blocks and controls
    do not. Labels are tested separately from surrounding text nodes.
    """

    _BOUNDARIES = {
        "a", "article", "aside", "blockquote", "br", "button", "dd", "div",
        "dl", "dt", "fieldset", "footer", "form", "h1", "h2", "h3", "h4",
        "h5", "h6", "header", "hr", "li", "main", "nav", "ol", "p",
        "pre", "section", "table", "tbody", "td", "th", "tr", "ul",
    }
    _SKIP_TAGS = {"script", "style", "template", "noscript"}
    _VOID_TAGS = {
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.fragments = []
        self._text_parts = []
        self._excluded = []

    def _flush(self):
        if self._text_parts:
            self.fragments.append("".join(self._text_parts))
            self._text_parts.clear()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if self._excluded:
            if tag not in self._VOID_TAGS:
                self._excluded.append(tag)
            return

        style = re.sub(r"\s+", "", attrs.get("style") or "").lower()
        not_visible = (
            tag in self._SKIP_TAGS
            or "hidden" in attrs
            or (attrs.get("aria-hidden") or "").lower() == "true"
            or "display:none" in style
            or "visibility:hidden" in style
        )
        if not_visible:
            self._flush()
            if tag not in self._VOID_TAGS:
                self._excluded.append(tag)
            return

        if tag in self._BOUNDARIES:
            self._flush()
        if tag == "input" and (attrs.get("type") or "").lower() == "hidden":
            return
        if tag in {"a", "button", "form", "input"}:
            for name in ("aria-label", "title"):
                if attrs.get(name):
                    self.fragments.append(attrs[name])
        if tag == "input" and (attrs.get("type") or "").lower() in {"submit", "button"}:
            self.fragments.append(attrs.get("value", ""))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self._VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if self._excluded:
            if tag in self._excluded:
                # Discard nested excluded elements up to the matching close.
                del self._excluded[len(self._excluded) - 1 - self._excluded[::-1].index(tag):]
            return
        if tag in self._BOUNDARIES:
            self._flush()

    def handle_data(self, data):
        if not self._excluded:
            self._text_parts.append(data)

    def visible_fragments(self):
        self.close()
        self._flush()
        return self.fragments


class DiscoverRouteContractTests(TestCase):
    def assertNoVisibleBuy(self, html):
        parser = _DiscoverVisibleText()
        parser.feed(html)
        pattern = re.compile(r"\bbuy\b", re.I)
        for fragment in parser.visible_fragments():
            self.assertNotRegex(fragment, pattern)

    def test_canonical_discover_routes_resolve(self):
        route_names = (
            "discover",
            "discover_knowledge",
            "discover_media",
            "discover_software_services",
            "discover_products_commerce",
        )

        with override("en"):
            for route_name in route_names:
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'class="discover-page"')
                self.assertContains(response, 'class="discover-controls"')

    def test_placeholder_does_not_define_discover_product_surface(self):
        with override("en"):
            response = self.client.get(reverse("discover"))

        self.assertNotContains(response, "Search results")
        self.assertNotContains(response, "Advanced filters")
        self.assertNotContains(response, "Checkout")
        self.assertNoVisibleBuy(response.content.decode(response.charset))

    def test_csrf_with_buy_text_does_not_create_a_false_purchase_control(self):
        # Deliberately invalid as a real CSRF token: this synthetic value proves
        # the parser excludes hidden values even when Buy has word boundaries.
        token = "a" * 16 + " Buy " + "b" * 43  # 64 characters
        with patch("django.middleware.csrf._mask_cipher_secret", return_value=token):
            with override("en"):
                response = self.client.get(reverse("discover"))
        self.assertContains(response, 'value="' + token + '"')
        self.assertNoVisibleBuy(response.content.decode(response.charset))

    def test_a_real_buy_button_is_rejected_by_the_contract(self):
        with self.assertRaises(AssertionError):
            self.assertNoVisibleBuy('<button type="submit"><span>Buy now</span></button>')

    def test_nested_button_label_is_detected(self):
        with self.assertRaises(AssertionError):
            self.assertNoVisibleBuy("<button>B<span>uy</span></button>")

    def test_nested_link_label_is_detected(self):
        with self.assertRaises(AssertionError):
            self.assertNoVisibleBuy("<a><b>B</b><i>u</i>y</a>")

    def test_independent_paragraphs_are_not_joined(self):
        self.assertNoVisibleBuy("<p>B</p><p>uy</p>")

    def test_independent_link_labels_are_not_joined(self):
        self.assertNoVisibleBuy('<a aria-label="B"></a><a aria-label="uy"></a>')

    def test_template_descendant_labels_are_ignored(self):
        self.assertNoVisibleBuy('<template><button aria-label="Buy"></button></template>')

    def test_hidden_input_label_is_ignored(self):
        self.assertNoVisibleBuy('<input type="hidden" aria-label="Buy" value=" Buy ">')

    def test_hidden_input_value_never_forms_visible_buy(self):
        self.assertNoVisibleBuy('<form><input type="hidden" value=" Buy "></form>')

    def test_submit_value_is_a_visible_buy_control(self):
        with self.assertRaises(AssertionError):
            self.assertNoVisibleBuy('<input type="submit" value="Buy">')

    def test_script_and_style_does_not_create_buy_control(self):
        self.assertNoVisibleBuy('<script>var x="Buy";</script><style>.Buy{}</style>')

    def test_buy_injected_into_actual_discover_response_is_rejected(self):
        with override("en"):
            response = self.client.get(reverse("discover"))
        html = response.content.decode(response.charset)
        with self.assertRaises(AssertionError):
            self.assertNoVisibleBuy(html + '<button>B<span>uy</span></button>')
