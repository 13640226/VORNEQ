from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.content.models import Article, Category, Tag
from apps.content.services import register_article_as_artifact
from apps.core.models import ArtifactIdentityRole, Identity
from apps.core.services.registry import resolve_artifact


class ContentFoundationTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Technology")
        self.tag = Tag.objects.create(name="AI")
        self.identity = Identity.objects.create(
            kind=Identity.Kind.HUMAN,
            display_name="Test Author",
        )

    def _article(self, title="Test Article", **overrides):
        values = {
            "title": title,
            "summary": "Test summary",
            "content": "Test content",
            "category": self.category,
        }
        values.update(overrides)
        return Article.objects.create(**values)

    def test_published_article_sets_publication_time(self):
        article = self._article(is_published=True)

        self.assertEqual(article.slug, "test-article")
        self.assertIsNotNone(article.published_at)

    def test_article_slug_collision_uses_stable_uuid_suffix(self):
        first = self._article(title="Same Title")
        second = self._article(title="Same Title")

        self.assertEqual(first.slug, "same-title")
        self.assertTrue(second.slug.startswith("same-title-"))
        self.assertNotEqual(first.slug, second.slug)

    def test_article_tags_are_domain_owned(self):
        article = self._article()
        article.tags.add(self.tag)

        self.assertEqual(list(article.tags.all()), [self.tag])

    def test_register_article_creates_artifact_and_explicit_author_role(self):
        article = self._article()

        artifact, artifact_created, role, role_created = register_article_as_artifact(
            article,
            self.identity,
        )

        self.assertTrue(artifact_created)
        self.assertTrue(role_created)
        self.assertEqual(resolve_artifact(article), artifact)
        self.assertEqual(role.artifact, artifact)
        self.assertEqual(role.identity, self.identity)
        self.assertEqual(role.role, ArtifactIdentityRole.Role.AUTHOR)
        self.assertTrue(role.is_primary)

    def test_registration_is_idempotent(self):
        article = self._article()

        first = register_article_as_artifact(article, self.identity)
        second = register_article_as_artifact(article, self.identity)

        self.assertTrue(first[1])
        self.assertTrue(first[3])
        self.assertFalse(second[1])
        self.assertFalse(second[3])
        self.assertEqual(first[0], second[0])
        self.assertEqual(first[2], second[2])

    def test_registration_rejects_inactive_author_identity(self):
        article = self._article()
        self.identity.is_active = False
        self.identity.save(update_fields=["is_active"])

        with self.assertRaises(ValidationError):
            register_article_as_artifact(article, self.identity)

        self.assertIsNone(resolve_artifact(article))
