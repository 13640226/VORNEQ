from django.db.models import Exists, F, OuterRef, Q

from apps.search.services import SearchAdapter, SearchResult

from .models import Document, DocumentAccess


class DocumentSearchAdapter(SearchAdapter):
    """Identity-bound retrieval adapter for private Documents.

    Authorization is applied in the queryset before counting, pagination, or
    serialization. Search itself does not grant access.
    """

    type_name = "document"

    def __init__(self, *, identity):
        self.identity = identity

    def get_queryset(self, query: str, filters: dict):
        collaborator_access = DocumentAccess.objects.filter(
            document_id=OuterRef("pk"),
            identity=self.identity,
            role__in=(
                DocumentAccess.Role.EDITOR,
                DocumentAccess.Role.VIEWER,
            ),
        )
        queryset = (
            Document.objects.filter(is_active=True)
            .annotate(_has_document_access=Exists(collaborator_access))
            .filter(
                Q(owner_identity=self.identity)
                | Q(_has_document_access=True)
            )
        )
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query)
                | Q(content__icontains=query)
                | Q(tags__icontains=query)
            )
        return queryset

    def global_time_expression(self):
        return F("updated_at")

    def serialize(self, document: Document, *, language: str) -> SearchResult:
        return SearchResult(
            key=f"document:{document.pk}",
            type=self.type_name,
            title=document.title,
            description=document.content,
            url=None,
            image_url=None,
            source="",
            published_at=document.updated_at,
            category="document",
        )
