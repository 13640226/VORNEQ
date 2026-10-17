"""Regression tests for canonical and reciprocal hreflang on public routes."""
from html.parser import HTMLParser

from django.test import TestCase
from django.urls import reverse
from django.utils.translation import override

from config.seo import PUBLIC_SEO_ROUTES, SEO_LANGUAGES


class HeadLinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "link":
            self.links.append(dict(attrs))


def get_links(response):
    parser = HeadLinkParser()
    parser.feed(response.content.decode("utf-8"))
    return parser.links


class PublicSeoMetadataTests(TestCase):
    def test_public_routes_have_single_canonical_and_reciprocal_alternates(self):
        for route in sorted(PUBLIC_SEO_ROUTES):
            for language in SEO_LANGUAGES:
                with self.subTest(route=route, language=language), override(language):
                    path = reverse(route)
                    response = self.client.get(path)
                    self.assertEqual(response.status_code, 200)
                    links = get_links(response)
                    canonicals = [x for x in links if x.get("rel") == "canonical"]
                    self.assertEqual(len(canonicals), 1)
                    self.assertEqual(canonicals[0]["href"], "http://testserver" + path)
                    alternates = {
                        x["hreflang"]: x["href"] for x in links
                        if x.get("rel") == "alternate" and x.get("hreflang")
                    }
                    self.assertEqual(set(alternates), set(SEO_LANGUAGES))
                    for other in SEO_LANGUAGES:
                        with override(other):
                            target = reverse(route)
                        self.assertEqual(alternates[other], "http://testserver" + target)

    def test_query_parameters_do_not_create_distinct_canonical(self):
        with override("en"):
            path = reverse("search_page")
        response = self.client.get(path + "?q=privacy&type=article")
        self.assertEqual(response.status_code, 200)
        canonical = [x for x in get_links(response) if x.get("rel") == "canonical"]
        self.assertEqual(len(canonical), 1)
        self.assertEqual(canonical[0]["href"], "http://testserver" + path)

    def test_home_and_account_indexing_policies_remain_unchanged(self):
        for route in ("home", "account_login", "account_signup"):
            with self.subTest(route=route), override("en"):
                response = self.client.get(reverse(route))
                self.assertEqual(response.status_code, 200)
                links = get_links(response)
                canonical = [x for x in links if x.get("rel") == "canonical"]
                alternate = [x for x in links if x.get("rel") == "alternate"]
                if route == "home":
                    self.assertEqual(len(canonical), 1)
                else:
                    self.assertEqual(canonical, [])
                    self.assertEqual(alternate, [])
