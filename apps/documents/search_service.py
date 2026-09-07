from apps.search.services import UnifiedSearch

from .identity_resolver import IdentityResolver
from .search_adapter import DocumentSearchAdapter


class SearchError(Exception):
    """Raised when private Documents search orchestration fails."""


class DocumentSearchService:
    identity_resolver = IdentityResolver
    search_backend = UnifiedSearch

    @classmethod
    def search(
        cls,
        *,
        user,
        query="",
        filters=None,
        page=1,
        page_size=UnifiedSearch.DEFAULT_PAGE_SIZE,
        language=None,
    ):
        identity = cls.identity_resolver.resolve(user)
        search = cls.search_backend(adapters=[DocumentSearchAdapter(identity=identity)])
        try:
            return search.search(
                query=query,
                filters=filters or {},
                page=page,
                page_size=page_size,
                language=language,
            )
        except Exception as exc:
            raise SearchError("Documents search failed.") from exc
