"""
Advanced Incident & Discrepancy Search Engine for PesaGuard.

Provides full-text, field-specific, and Boolean expression query capabilities across
discrepancy incident logs.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from sqlalchemy import and_, not_, or_
from sqlalchemy.orm import Session

from models import Discrepancy

logger = logging.getLogger("pesaguard.search")


class AdvancedSearchEngine:
    """Full-text and Boolean query engine for operational discrepancy tracking."""

    def __init__(self, session: Session):
        self.session = session

    def search(
        self,
        tenant_id: str,
        query: str,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Execute boolean and field-specific search query across tenant discrepancies."""
        parsed = self._parse_query(query)
        db_query = self.session.query(Discrepancy).filter(
            Discrepancy.tenant_id == (tenant_id or "default")
        )

        filter_clause = self._build_expression_clause(parsed.get("conditions", []))
        if filter_clause is not None:
            db_query = db_query.filter(filter_clause)

        total = db_query.count()
        results = (
            db_query.order_by(Discrepancy.detected_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return {
            "query": query,
            "total": total,
            "limit": limit,
            "offset": offset,
            "results": [self._incident_to_dict(r) for r in results],
            "parsed": parsed,
        }

    def _parse_query(self, query_str: str) -> Dict[str, Any]:
        """Parse query string into structured condition tokens."""
        clean_query = " ".join(query_str.strip().split())
        if not clean_query:
            return {"query": "", "conditions": []}

        # Tokenize by logical operators AND, OR, NOT
        tokens = re.split(r"\s+(AND|OR|NOT)\s+", clean_query, flags=re.IGNORECASE)

        conditions = []
        current_op = "AND"

        i = 0
        while i < len(tokens):
            token = tokens[i].strip()
            if not token:
                i += 1
                continue

            if token.upper() in {"AND", "OR", "NOT"}:
                current_op = token.upper()
            else:
                parsed_cond = self._parse_individual_term(token)
                if parsed_cond:
                    parsed_cond["logical_op"] = current_op
                    conditions.append(parsed_cond)

            i += 1

        return {"query": clean_query, "conditions": conditions}

    def _parse_individual_term(self, term: str) -> Optional[Dict[str, Any]]:
        """Parse individual key:value, key>value, or free-text term."""
        # Field pattern match: e.g., 'severity:critical', 'age>30', 'details~error'
        match = re.match(r"(\w+)([:><=~])(.+)", term.strip())
        if not match:
            return {
                "type": "text",
                "value": term.strip().strip("\"'"),
            }

        field, operator, value = match.groups()
        return {
            "type": "field",
            "field": field.lower(),
            "operator": operator,
            "value": value.strip().strip("\"'"),
        }

    def _build_expression_clause(self, conditions: List[Dict[str, Any]]) -> Any:
        """Construct SQLAlchemy BinaryExpression trees from parsed conditions."""
        if not conditions:
            return None

        and_clauses = []
        or_clauses = []

        for cond in conditions:
            clause = self._condition_to_sql_clause(cond)
            if clause is None:
                continue

            logical_op = cond.get("logical_op", "AND")

            if logical_op == "NOT":
                and_clauses.append(not_(clause))
            elif logical_op == "OR":
                or_clauses.append(clause)
            else:  # AND
                and_clauses.append(clause)

        final_and = and_(*and_clauses) if and_clauses else None
        final_or = or_(*or_clauses) if or_clauses else None

        if final_and is not None and final_or is not None:
            return or_(final_and, final_or)
        return final_and if final_and is not None else final_or

    def _condition_to_sql_clause(self, condition: Dict[str, Any]) -> Any:
        """Convert individual parsed condition to a SQLAlchemy filter clause."""
        cond_type = condition.get("type")

        if cond_type == "text":
            text_val = f"%{condition['value']}%"
            return or_(
                Discrepancy.trans_id.ilike(text_val),
                Discrepancy.anomaly_type.ilike(text_val),
                Discrepancy.details.ilike(text_val),
                Discrepancy.notes.ilike(text_val),
                Discrepancy.resolution_note.ilike(text_val),
            )

        field = condition.get("field")
        value = condition.get("value", "")
        op = condition.get("operator", ":")

        if field == "severity":
            return Discrepancy.severity.ilike(value) if op in {":", "~"} else Discrepancy.severity == value
        
        if field == "status":
            return Discrepancy.status.ilike(value) if op in {":", "~"} else Discrepancy.status == value
        
        if field == "anomaly_type":
            return Discrepancy.anomaly_type.ilike(f"%{value}%") if op == "~" else Discrepancy.anomaly_type == value
        
        if field == "resolved":
            bool_val = value.lower() in {"true", "1", "yes"}
            return Discrepancy.resolved == bool_val
        
        if field == "trans_id":
            return Discrepancy.trans_id.ilike(f"%{value}%") if op == "~" else Discrepancy.trans_id == value
        
        if field == "assignee":
            return Discrepancy.assignee.ilike(value) if op in {":", "~"} else Discrepancy.assignee == value

        if field in {"age", "age_minutes"}:
            try:
                minutes = int(value)
                cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
                if op in {">", ">="}:
                    return Discrepancy.detected_at < cutoff
                if op in {"<", "<="}:
                    return Discrepancy.detected_at > cutoff
            except ValueError:
                return None

        return None

    def search_by_filters(
        self,
        tenant_id: str,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        anomaly_type: Optional[str] = None,
        resolved: Optional[bool] = None,
        assignee: Optional[str] = None,
        days_back: int = 30,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Structured filter query convenience method for dashboard tables."""
        query = self.session.query(Discrepancy).filter(
            Discrepancy.tenant_id == (tenant_id or "default")
        )

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
        query = query.filter(Discrepancy.detected_at >= cutoff_date)

        if severity:
            query = query.filter(Discrepancy.severity == severity)
        if status:
            query = query.filter(Discrepancy.status == status)
        if anomaly_type:
            query = query.filter(Discrepancy.anomaly_type == anomaly_type)
        if resolved is not None:
            query = query.filter(Discrepancy.resolved == resolved)
        if assignee:
            query = query.filter(Discrepancy.assignee == assignee)

        total = query.count()
        results = (
            query.order_by(Discrepancy.detected_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "filters": {
                "tenant_id": tenant_id,
                "severity": severity,
                "status": status,
                "anomaly_type": anomaly_type,
                "resolved": resolved,
                "assignee": assignee,
                "days_back": days_back,
            },
            "results": [self._incident_to_dict(r) for r in results],
        }

    def suggest_filters(self, tenant_id: str) -> Dict[str, List[str]]:
        """Retrieve dynamic filter facets for tenant dashboard dropdowns."""
        base_query = self.session.query(Discrepancy).filter(
            Discrepancy.tenant_id == (tenant_id or "default")
        )

        severities = {r[0] for r in base_query.with_entities(Discrepancy.severity).distinct().all() if r[0]}
        statuses = {r[0] for r in base_query.with_entities(Discrepancy.status).distinct().all() if r[0]}
        anomaly_types = {r[0] for r in base_query.with_entities(Discrepancy.anomaly_type).distinct().all() if r[0]}
        assignees = {r[0] for r in base_query.with_entities(Discrepancy.assignee).distinct().all() if r[0]}

        return {
            "severities": sorted(list(severities)),
            "statuses": sorted(list(statuses)),
            "anomaly_types": sorted(list(anomaly_types)),
            "assignees": sorted(list(assignees)),
        }

    def _incident_to_dict(self, incident: Discrepancy) -> Dict[str, Any]:
        """Serialize Discrepancy ORM instance into clean JSON dict."""
        return {
            "id": incident.id,
            "trans_id": incident.trans_id,
            "tenant_id": incident.tenant_id,
            "anomaly_type": incident.anomaly_type,
            "severity": incident.severity,
            "status": incident.status,
            "resolved": incident.resolved,
            "assignee": incident.assignee,
            "detected_at": incident.detected_at.isoformat() if incident.detected_at else None,
            "resolved_at": incident.resolved_at.isoformat() if incident.resolved_at else None,
            "resolution_note": incident.resolution_note,
            "details": incident.details,
            "notes": incident.notes,
        }
