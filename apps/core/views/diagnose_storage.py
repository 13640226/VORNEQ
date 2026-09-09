import os
import secrets
from urllib.parse import urlsplit

from django.core.files.storage import default_storage
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def diagnose_storage(request):
    if os.environ.get("ENABLE_STORAGE_DIAGNOSTIC") != "True":
        raise Http404

    expected_token = os.environ.get("DIAGNOSTIC_TOKEN")
    if not expected_token:
        raise Http404

    supplied_token = request.headers.get("X-Diagnostic-Token", "")
    if not supplied_token or not secrets.compare_digest(supplied_token, expected_token):
        return JsonResponse({"error": "unauthorized"}, status=401)

    result = {
        "storage_backend": default_storage.__class__.__name__,
    }

    if not hasattr(default_storage, "bucket_name"):
        result["storage_is_s3"] = False
        return JsonResponse(result)

    result["storage_is_s3"] = True
    endpoint_url = getattr(default_storage, "endpoint_url", None)
    parsed_endpoint = urlsplit(endpoint_url or "")
    result.update(
        {
            "bucket_matches_expected": bool(default_storage.bucket_name),
            "endpoint_is_r2": parsed_endpoint.hostname is not None
            and parsed_endpoint.hostname.endswith(".r2.cloudflarestorage.com"),
            "endpoint_has_path": parsed_endpoint.path not in ("", "/"),
            "region_name": getattr(default_storage, "region_name", None),
        }
    )

    try:
        client = default_storage.connection.meta.client
        config = client.meta.config
        result["signature_version"] = config.signature_version
        result["addressing_style"] = (config.s3 or {}).get("addressing_style")
        result["client_region_matches_storage"] = (
            client.meta.region_name == getattr(default_storage, "region_name", None)
        )

        try:
            client.head_object(
                Bucket=default_storage.bucket_name,
                Key="vorneq-diagnostic-does-not-exist",
            )
            result["head_object_http_status"] = 200
            result["head_object_error_code"] = None
        except Exception as exc:
            response = getattr(exc, "response", {}) or {}
            result["head_object_http_status"] = response.get(
                "ResponseMetadata", {}
            ).get("HTTPStatusCode")
            result["head_object_error_code"] = response.get("Error", {}).get("Code")
    except Exception as exc:
        result["client_config_error_type"] = exc.__class__.__name__

    return JsonResponse(result)
