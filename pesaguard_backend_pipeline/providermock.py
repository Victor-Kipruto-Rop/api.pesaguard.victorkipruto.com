from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any, Dict


class ProviderMock:
    def __init__(self, responses: Dict[str, Any] | None = None) -> None:
        self._responses: Dict[str, Any] = responses or {}
        self.sent: list[Dict[str, Any]] = []

    def configure(self, responses: Dict[str, Any]) -> ProviderMock:
        self._responses = responses
        return self

    def send_stk_push(self, phone: str, amount: str, reference: str, **kwargs: Any) -> Dict[str, Any]:
        payload = {
            'phone': phone,
            'amount': amount,
            'reference': reference,
            'at': datetime.now(timezone.utc).isoformat(),
        }
        self.sent.append({'type': 'stk_push', 'payload': payload})
        return self._responses.get('stk_push', {'ResultCode': 0, 'ResultDesc': 'Success'})

    def parse_webhook(self, raw_body: bytes) -> Dict[str, Any]:
        return json.loads(raw_body.decode('utf-8'))

    def serialize_callback_request(self, payload: Dict[str, Any]) -> bytes:
        return json.dumps(payload, sort_keys=True).encode('utf-8')

    def webhook_headers(self, shared_secret: str, payload: bytes) -> Dict[str, str]:
        digest = hmac.new(shared_secret.encode(), payload, hashlib.sha256).hexdigest()
        return {'X-Daraja-Signature': f'sha256={digest}'}


def build_fake_provider(responses: Dict[str, Any] | None = None) -> ProviderMock:
    return ProviderMock(responses=responses)

