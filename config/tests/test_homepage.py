import re
from html.parser import HTMLParser
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils.translation import override


class HomepageSimplificationTests(TestCase):
    def get_english_home(self, params=None):
        with override("en"):
            return self.client.get(reverse("home"), data=params or {})

    def test_homepage_keeps_only_orientation_and_routing_surfaces(self):
        response = self.get_english_home()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="world-home ')
        self.assertContains(response, 'id="start"')
        self.assertContains(response, 'id="principles"')
        self.assertContains(response, 'id="capabilities"')

        self.assertNotContains(response, 'id="discoveries"')
        self.assertNotContains(response, 'id="identity"')
        self.assertNotContains(response, 'id="apps"')
        self.assertContains(response, 'id="explore"')
        self.assertNotContains(response, "Featured Discoveries")
        self.assertNotContains(response, "Latest Discoveries")
        self.assertNotContains(response, "Explore topics")
        self.assertNotContains(response, "Software categories")

    def test_homepage_signal_navigation_contract(self):
        response = self.get_english_home()
        html = response.content.decode()

        section_ids = (
            "home",
            "start",
            "capabilities",
            "how-it-works",
            "trust",
            "principles",
            "explore",
        )

        for section_id in section_ids:
            self.assertContains(response, f'id="{section_id}"')

        self.assertContains(response, 'href="#home"')
        self.assertContains(response, 'href="#start"')
        self.assertContains(response, 'href="#capabilities"')
        self.assertContains(response, 'href="#how-it-works"')
        self.assertContains(response, 'href="#trust"')
        self.assertContains(response, 'href="#principles"')
        self.assertContains(response, 'href="#explore"')

        self.assertEqual(
            html.count("data-homepage-signal-section"),
            7,
        )
        self.assertEqual(
            html.count("data-homepage-signal-link"),
            7,
        )

        self.assertContains(
            response,
            'aria-label="Section navigation"',
        )
        self.assertEqual(
            html.count('aria-current="location"'),
            1,
        )

        self.assertContains(
            response,
            "css/homepage-signal-nav-v2",
        )
        self.assertContains(
            response,
            "js/homepage-signal-nav-v2",
        )

        # Global navigation and homepage section navigation coexist.
        self.assertContains(response, 'class="standalone-nav')
        self.assertContains(response, 'class="homepage-signal-nav')

    def test_signal_navigation_is_homepage_only(self):
        with override("en"):
            response = self.client.get(reverse("discover"))

        self.assertNotContains(
            response,
            'class="homepage-signal-nav',
        )

    def test_homepage_search_is_primary_entry_without_refinement(self):
        response = self.get_english_home()

        with override("en"):
            search_url = reverse("search_page")

        self.assertContains(response, f'action="{search_url}"')
        self.assertContains(response, 'name="q"')
        self.assertNotContains(response, 'name="type"')
        self.assertNotContains(response, 'name="item_type"')
        self.assertNotContains(response, 'name="media_type"')
        self.assertNotContains(response, 'name="category"')
        self.assertNotContains(response, "Advanced filters")
        self.assertNotContains(response, "Quick content filters")
        self.assertNotContains(response, "Open advanced search")

    def test_homepage_has_independent_discover_handoff(self):
        response = self.get_english_home()
        with override("en"):
            discover_url = reverse("discover")

        self.assertContains(response, f'href="{discover_url}"')
        self.assertContains(response, "Open Discover")

    def test_homepage_capability_surface_routes_without_replication(self):
        response = self.get_english_home()

        with override("en"):
            expected_urls = (
                reverse("search_page"),
                reverse("discover"),
                reverse("marketplace:index"),
            )

        for url in expected_urls:
            self.assertContains(response, f'href="{url}"')

        self.assertContains(response, "Capabilities")
        self.assertContains(response, "Independent applications. Connected possibilities. Permissions remain explicit.")
        self.assertNotContains(response, "Checkout")
        self.assertNotContains(response, "Entitlement")
        self.assertNotContains(response, "Search results")

    def test_homepage_preserves_platform_principles_and_visual_contract(self):
        response = self.get_english_home()

        self.assertContains(
            response,
            "One Platform. Many Applications. Connected Possibilities.",
        )
        self.assertContains(response, "Context, not Score")
        self.assertContains(response, "Evidence, not Truth")
        self.assertContains(response, "Portable Identity")
        self.assertNotContains(response, 'class="global-home__globe"')
        self.assertNotContains(response, 'class="global-home__globe-node"')
        self.assertNotContains(response, "global-home__atlas")

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
