"""Single source of truth for public Marketplace product visibility.

Two separate concepts (see docs/marketplace/PUBLIC_FIXTURE_VISIBILITY.md):

* Publication state (``published_products``): the moderation/publication
  data state. Changed only by audited transitions (``publication.py``) or by
  the local, signed synthetic quarantine (``apps.core.synthetic_quarantine``).
* Public visibility (``public_products``): what anonymous/public surfaces may
  show. It is the publication state MINUS known historical benchmark/smoke
  fixtures. This guard is permanent, read-only and never mutates or deletes
  records; quarantine remains the audited way to change the data itself.

Name/slug markers are defense in depth, not proof of provenance.
"""
from django.db.models import Q

from .models import Product

KNOWN_FIXTURE_SLUG_PREFIXES = ("vorneq-benchmark-", "inspect-staging-smoke")
KNOWN_FIXTURE_SELLERS = frozenset({"vorneq-benchmark-seed", "vorneq-inspect-smoke"})


def known_fixture_q():
    """Database predicate equivalent to :func:`is_known_fixture`."""
    q = Q(seller__username__in=sorted(KNOWN_FIXTURE_SELLERS))
    for prefix in KNOWN_FIXTURE_SLUG_PREFIXES:
        q |= Q(slug__startswith=prefix)
    return q


def is_known_fixture(product):
    """Python predicate equivalent to :func:`known_fixture_q`."""
    return (
        product.slug.startswith(KNOWN_FIXTURE_SLUG_PREFIXES)
        or product.seller.username in KNOWN_FIXTURE_SELLERS
    )


def published_products():
    """Approved AND published (data state). NOT a public-display queryset."""
    return Product.objects.filter(status=Product.STATUS_APPROVED, is_published=True)


def public_products():
    """Everything public surfaces may show: published, minus known fixtures."""
    return published_products().exclude(known_fixture_q()).select_related("seller")
