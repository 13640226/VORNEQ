import os
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.content.models import Article, Category
from apps.media.models import MediaAsset
from library.models import LibraryItem
from marketplace.models import Product


SEED_PREFIX = "vorneq-benchmark"
MEDIA_TITLE_PREFIX = "VORNEQ Benchmark Media"
SEED_USER = "vorneq-benchmark-seed"
TERMS = ("ai", "knowledge", "science", "research", "verification")


class Command(BaseCommand):
    help = "Create deterministic synthetic staging data for search benchmarks."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=None, help="Set the same count for every seeded model.")
        parser.add_argument("--articles", type=int, default=1000)
        parser.add_argument("--products", type=int, default=500)
        parser.add_argument("--library-items", type=int, default=500, dest="library_items")
        parser.add_argument("--media-assets", type=int, default=200, dest="media_assets")
        parser.add_argument("--dry-run", action="store_true", help="Print the seed plan without writing data.")
        parser.add_argument("--force", action="store_true", help="Apply the staging seed plan.")

    def handle(self, *args, **options):
        counts = {
            "articles": options["articles"],
            "products": options["products"],
            "library_items": options["library_items"],
            "media_assets": options["media_assets"],
        }
        if options["count"] is not None:
            counts = {key: options["count"] for key in counts}

        if any(value < 0 for value in counts.values()):
            raise CommandError("Seed counts must be zero or greater.")

        self.stdout.write(
            "Seed plan: "
            + ", ".join(f"{name}={value}" for name, value in counts.items())
        )

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run only; no database writes were performed."))
            return

        if not options["force"]:
            raise CommandError("Refusing to write without --force. Use --dry-run to inspect the plan.")

        if os.environ.get("VORNEQ_ALLOW_STAGING_SEED", "").lower() != "yes":
            raise CommandError(
                "Refusing to seed: VORNEQ_ALLOW_STAGING_SEED must be set to 'yes'."
            )

        now = timezone.now()
        User = get_user_model()

        with transaction.atomic():
            Article.objects.filter(slug__startswith=f"{SEED_PREFIX}-article-").delete()
            Product.objects.filter(slug__startswith=f"{SEED_PREFIX}-product-").delete()
            LibraryItem.objects.filter(slug__startswith=f"{SEED_PREFIX}-library-").delete()
            MediaAsset.objects.filter(title__startswith=MEDIA_TITLE_PREFIX).delete()

            category, _ = Category.objects.get_or_create(
                name="VORNEQ Benchmark",
                defaults={"slug": f"{SEED_PREFIX}-category", "description": "Synthetic benchmark data."},
            )
            seller, created = User.objects.get_or_create(username=SEED_USER)
            if created:
                seller.set_unusable_password()
                seller.save(update_fields=["password"])

            articles = []
            for index in range(counts["articles"]):
                term = TERMS[index % len(TERMS)]
                articles.append(
                    Article(
                        title=f"Benchmark {term} article {index:06d}",
                        slug=f"{SEED_PREFIX}-article-{index:06d}",
                        summary=f"Synthetic {term} benchmark summary for search profiling.",
                        content=(f"{term} knowledge science benchmark content " * 8).strip(),
                        category=category,
                        is_published=True,
                        published_at=now - timedelta(minutes=index),
                        editorial_metadata={"benchmark_seed": True, "index": index},
                    )
                )
            Article.objects.bulk_create(articles, batch_size=500)

            products = []
            for index in range(counts["products"]):
                term = TERMS[index % len(TERMS)]
                products.append(
                    Product(
                        seller=seller,
                        title=f"Benchmark {term} product {index:06d}",
                        slug=f"{SEED_PREFIX}-product-{index:06d}",
                        short_description=f"Synthetic {term} product for benchmark search.",
                        description=(f"{term} knowledge science marketplace benchmark " * 6).strip(),
                        category=Product.CATEGORY_OTHER,
                        tags=f"{term},knowledge,science,benchmark",
                        price=Decimal("9.99") + Decimal(index % 100),
                        status=Product.STATUS_APPROVED,
                        is_published=True,
                        published_at=now - timedelta(minutes=index),
                    )
                )
            Product.objects.bulk_create(products, batch_size=500)

            library_items = []
            for index in range(counts["library_items"]):
                term = TERMS[index % len(TERMS)]
                library_items.append(
                    LibraryItem(
                        title=f"Benchmark {term} library item {index:06d}",
                        title_en=f"Benchmark {term} library item {index:06d}",
                        slug=f"{SEED_PREFIX}-library-{index:06d}",
                        category="benchmark",
                        short_description=f"Synthetic {term} library benchmark record.",
                        short_description_en=f"Synthetic {term} library benchmark record.",
                        content=(f"{term} knowledge science library benchmark " * 8).strip(),
                        content_en=(f"{term} knowledge science library benchmark " * 8).strip(),
                        author="VORNEQ Benchmark Seed",
                        item_type="document",
                        allow_public_reading=True,
                        is_published=True,
                        published_at=now - timedelta(minutes=index),
                    )
                )
            LibraryItem.objects.bulk_create(library_items, batch_size=500)

            media_assets = []
            for index in range(counts["media_assets"]):
                term = TERMS[index % len(TERMS)]
                media_assets.append(
                    MediaAsset(
                        media_type=MediaAsset.MediaType.IMAGE,
                        title=f"{MEDIA_TITLE_PREFIX} {term} {index:06d}",
                        alt_text=f"Synthetic {term} knowledge science benchmark image.",
                        file=f"benchmark/{SEED_PREFIX}-media-{index:06d}.jpg",
                        mime_type="image/jpeg",
                        byte_size=1024 + index,
                        width=1200,
                        height=800,
                        presentation_metadata={"benchmark_seed": True, "index": index},
                        is_active=True,
                    )
                )
            MediaAsset.objects.bulk_create(media_assets, batch_size=500)

        self.stdout.write(
            self.style.SUCCESS(
                "Staging benchmark seed complete: "
                + ", ".join(f"{name}={value}" for name, value in counts.items())
            )
        )
