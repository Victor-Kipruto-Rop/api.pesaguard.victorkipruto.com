"""
Validation & Normalization Helpers for M-Pesa Daraja Callbacks.

Supports flat C2B PayBill/Till confirmation webhooks and nested STK Push (Lipa na M-Pesa) /
B2C callback structures, normalizing payloads for the reconciliation engine.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("pesaguard.daraja_validator")

# Flat C2B Callback standard required keys
REQUIRED_C2B_FIELDS = [
    "TransactionType",
    "TransID",
    "TransTime",
    "TransAmount",
    "BusinessShortCode",
    "MSISDN",
]


def validate_daraja_payload(payload: Dict[str, Any]) -> Tuple[bool, str]:
    """Validate raw incoming Daraja webhook structure and required fields.

    Args:
        payload: Incoming JSON request body dictionary

    Returns:
        Tuple of (is_valid: bool, error_message: str)
    """
    if not isinstance(payload, dict):
        return False, "Payload must be a JSON object"

    # 1. Evaluate Nested STK Push Callback Structure
    if "Body" in payload and "stkCallback" in payload["Body"]:
        return _validate_stk_push_callback(payload["Body"]["stkCallback"])

    # 2. Evaluate Nested B2C Callback Structure
    if "Result" in payload:
        return _validate_b2c_callback(payload["Result"])

    # 3. Evaluate Flat C2B PayBill / Till Confirmation Structure
    missing = [f for f in REQUIRED_C2B_FIELDS if f not in payload or payload[f] is None]
    if missing:
        return False, f"Missing required C2B fields: {', '.join(missing)}"

    # Validate TransAmount numerics
    try:
        amt = float(payload["TransAmount"])
        if amt <= 0:
            return False, "TransAmount must be greater than 0"
    except (ValueError, TypeError):
        return False, "TransAmount must be a valid numeric value"

    # Validate TransID non-empty
    trans_id = str(payload.get("TransID", "")).strip()
    if not trans_id:
        return False, "TransID cannot be empty"

    # Validate MSISDN format (12-digit Kenyan phone 2547XXXXXXXX / 2541XXXXXXXX)
    msisdn = str(payload.get("MSISDN", "")).strip()
    if not re.match(r"^254[17]\d{8}$", msisdn):
        return False, f"MSISDN '{msisdn}' must be a valid 12-digit string starting with 254"

    return True, ""


def extract_canonical_event(payload: Dict[str, Any], tenant_id: str = "default") -> Optional[Dict[str, Any]]:
    """Extract and normalize standard payment fields from diverse Daraja callback payloads.

    Args:
        payload: Validated incoming JSON payload
        tenant_id: Active tenant context string

    Returns:
        Normalized dictionary ready for the reconciliation pipeline
    """
    is_valid, _ = validate_daraja_payload(payload)
    if not is_valid:
        return None

    # Handle Nested STK Push
    if "Body" in payload and "stkCallback" in payload["Body"]:
        stk = payload["Body"]["stkCallback"]
        meta = {item["Name"]: item.get("Value") for item in stk.get("CallbackMetadata", {}).get("Item", []) if "Name" in item}
        
        return {
            "tenant_id": tenant_id,
            "TransID": str(meta.get("MpesaReceiptNumber", stk.get("CheckoutRequestID", "unknown"))).strip(),
            "TransAmount": float(meta.get("Amount", 0)),
            "MSISDN": str(meta.get("PhoneNumber", "")).strip(),
            "TransTime": str(meta.get("TransactionDate", datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"))),
            "BusinessShortCode": str(payload.get("BusinessShortCode", "")),
            "TransactionType": "STK_PUSH",
            "raw_payload": payload,
        }

    # Handle Flat C2B Payload
    return {
        "tenant_id": tenant_id,
        "TransID": str(payload.get("TransID", "")).strip(),
        "TransAmount": float(payload["TransAmount"]),
        "MSISDN": str(payload.get("MSISDN", "")).strip(),
        "TransTime": str(payload.get("TransTime", "")).strip(),
        "BusinessShortCode": str(payload.get("BusinessShortCode", "")).strip(),
        "TransactionType": str(payload.get("TransactionType", "C2B")),
        "BillRefNumber": str(payload.get("BillRefNumber", "")).strip(),
        "raw_payload": payload,
    }


def _validate_stk_push_callback(stk: Dict[str, Any]) -> Tuple[bool, str]:
    """Validate nested STK Push callback envelope."""
    result_code = stk.get("ResultCode")
    if result_code is None:
        return False, "STK Push callback missing ResultCode"

    if int(result_code) != 0:
        return False, f"STK Push cancelled or failed with ResultCode={result_code}: {stk.get('ResultDesc')}"

    meta_items = stk.get("CallbackMetadata", {}).get("Item", [])
    if not meta_items:
        return False, "STK Push callback missing CallbackMetadata items"

    return True, ""


def _validate_b2c_callback(result: Dict[str, Any]) -> Tuple[bool, str]:
    """Validate nested B2C result envelope."""
    result_code = result.get("ResultCode")
    if result_code is None:
        return False, "B2C callback missing ResultCode"

    if int(result_code) != 0:
        return False, f"B2C payment failed with ResultCode={result_code}: {result.get('ResultDesc')}"

    return True, ""
