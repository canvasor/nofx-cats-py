from __future__ import annotations

import hashlib
import hmac
from urllib.parse import urlencode


def sign_params(secret: str, params: dict[str, object]) -> str:
    query = urlencode(params, doseq=True)
    signature = hmac.new(secret.encode("utf-8"), query.encode("utf-8"), hashlib.sha256).hexdigest()
    return signature
