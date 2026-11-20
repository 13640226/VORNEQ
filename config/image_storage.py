"""Private image bucket options (pure; imported by settings, no Django imports).

Cloudflare R2 accepts only AWS Signature Version 4. Without an explicit
signature version and region, botocore presigns with the legacy SigV2 query
form (AWSAccessKeyId/Signature/Expires), which R2 rejects, while header-signed
PUT/HEAD calls still succeed. Both values are therefore pinned here.
"""
from urllib.parse import urlsplit

SIGNATURE_VERSION = "s3v4"
R2_REGION = "auto"


class InvalidImageStorage(ValueError):
    pass


def image_storage_options(*, bucket, endpoint_url, access_key, secret_key):
    endpoint = urlsplit(endpoint_url)
    host = (endpoint.hostname or "").lower()
    if (endpoint.scheme != "https" or endpoint.username or endpoint.password
            or endpoint.query or endpoint.fragment
            or not (host.endswith(".r2.cloudflarestorage.com")
                    or host.endswith(".amazonaws.com"))):
        raise InvalidImageStorage("invalid image storage endpoint")
    return {
        "bucket_name": bucket,
        "endpoint_url": endpoint_url,
        "access_key": access_key,
        "secret_key": secret_key,
        "default_acl": "private",
        "querystring_auth": True,
        "file_overwrite": False,
        "custom_domain": None,
        "signature_version": SIGNATURE_VERSION,
        "region_name": R2_REGION if host.endswith(".r2.cloudflarestorage.com") else None,
        "addressing_style": "path",
    }
