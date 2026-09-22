# PesaGuard Advanced Features Documentation

## 🚀 New Features Added

### 1. **CSV Export** (`/discrepancies/export/csv`)
- **Purpose**: Export all or filtered incidents to CSV file
- **Method**: GET
- **Query Parameters**: 
  - `status` - Filter by anomaly type or status
  - `severity` - Filter by severity level (critical, warning)
  - `resolved` - Filter by state (open, resolved)
- **Response**: CSV file download
- **Use Case**: Generate reports, audit trails, external system imports

**Frontend Access**: Advanced Tools → Download CSV

---

### 2. **Incident Trends Analysis** (`/analytics/incident-trends`)
- **Purpose**: Weekly (4 weeks) and monthly (12 months) trend data
- **Method**: GET
- **Response**: 
  ```json
  {
    "weekly": [
      {"week": "W1", "incidents": 45, "resolved": 30, "open": 15}
    ],
    "monthly": [
      {"month": "Jan", "incidents": 200, "resolved": 150, "open": 50}
    ]
  }
  ```
- **Use Case**: Track system health trends, identify patterns

**Frontend Access**: Advanced Tools → Generate Report (includes trend data)

---

### 3. **Filter Presets Management** (`/incidents/filters/presets`)
- **Purpose**: Save and retrieve custom filter configurations
- **Methods**: 
  - GET: Retrieve all saved presets
  - POST: Save new preset
- **Default Presets**:
  - `critical_open`: Critical unresolved incidents
  - `warning_assigned`: Warning incidents assigned to operators
  - `needs_review`: Incidents needing immediate review
- **Use Case**: Quick access to frequently used filters

**Example Usage**:
```bash
# Get presets
curl http://localhost:5001/incidents/filters/presets

# Save custom preset
curl -X POST http://localhost:5001/incidents/filters/presets \
  -H "Content-Type: application/json" \
  -d '{"name": "my_filter", "filters": {"severity": "critical", "resolved": "open"}}'
```

---

### 4. **Auto-Escalation** (`/incidents/auto-escalate`)
- **Purpose**: Automatically escalate old unresolved critical incidents
- **Method**: POST
- **Query Parameters**:
  - `escalation_minutes` - Minutes before escalation (default: 45)
- **Behavior**: 
  - Finds critical incidents unresolved longer than threshold
  - Assigns to "On-Call Lead" if unassigned
  - Creates audit trail entry
- **Response**: 
  ```json
  {
    "status": "escalated",
    "count": 5,
    "threshold_minutes": 45
  }
  ```
- **Use Case**: SLA compliance, prevent incident abandonment

**Frontend Access**: Advanced Tools → Auto-escalation (configurable trigger)

**Can be automated**: `curl -X POST http://localhost:5001/incidents/auto-escalate?escalation_minutes=45`

---

### 5. **Reconciliation Report** (`/analytics/reconciliation-report`)
- **Purpose**: Generate comprehensive reconciliation summary
- **Method**: GET
- **Query Parameters**:
  - `days` - Report period in days (default: 7)
- **Response Includes**:
  - Total incidents, resolved, open counts
  - Resolution rate and average resolution time
  - Breakdown by severity and status
  - SLA compliance percentage
  - Critical incident count
- **Use Case**: Management reports, compliance audits, performance tracking

**Response Structure**:
```json
{
  "report_period_days": 7,
  "generated_at": "2026-07-04T12:34:56.789Z",
  "summary": {
    "total_incidents": 150,
    "resolved": 120,
    "open": 30,
    "resolution_rate": 0.8,
    "average_resolution_minutes": 18
  },
  "by_severity": {"critical": 10, "warning": 80, "info": 60},
  "by_status": {"needs_review": 20, "assigned": 80, "escalated": 50},
  "critical_count": 10,
  "sla_compliant_percentage": 95.5
}
```

**Frontend Access**: Advanced Tools → Generate Report

---

### 6. **Bulk Assignment** (`/incidents/bulk-assign`)
- **Purpose**: Assign multiple incidents to an operator in one action
- **Method**: POST
- **Request Body**:
  ```json
  {
    "ids": ["incident-1", "incident-2", "incident-3"],
    "assignee": "operator_name",
    "note": "Batch from critical queue"
  }
  ```
- **Response**: Count of successfully assigned incidents
- **Use Case**: Quick load balancing, batch processing

**Frontend Access**: Advanced Tools → Bulk Assign

---

### 7. **Full-Text Search** (`/incidents/search`)
- **Purpose**: Advanced search across all incident fields
- **Method**: GET
- **Query Parameters**:
  - `q` - Search term (searches trans_id, anomaly_type, details, notes)
  - `severity` - Filter by severity
  - `assignee` - Filter by assignee
  - `page` - Pagination (default: 1)
  - `per_page` - Results per page (default: 20)
- **Search Fields**:
  - Transaction ID
  - Anomaly Type
  - Details/Description
  - Operator Notes
- **Use Case**: Finding specific incidents, audit searches

**Example**:
```bash
curl "http://localhost:5001/incidents/search?q=duplicate&severity=warning&page=1&per_page=10"
```

---

## 📊 Frontend Pages

### **/tools** - Advanced Tools Dashboard
New page providing UI for all bulk operations:
- **Auto-Escalation Control**: Set escalation threshold in minutes, trigger escalations
- **CSV Export**: One-click export of all incidents
- **Reconciliation Reports**: Generate period-based summaries with key metrics
- **Bulk Assign**: Assign multiple incidents to operators
- **Trend Analysis**: View 4-week and 12-month incident trends with resolved/open breakdown

---

## 🔄 API Endpoint Summary

| Endpoint | Method | Purpose | Authentication |
|----------|--------|---------|-----------------|
| `/discrepancies/export/csv` | GET | Export incidents | None (MVP) |
| `/analytics/incident-trends` | GET | Weekly/monthly trends | None |
| `/incidents/filters/presets` | GET/POST | Manage filter presets | None |
| `/incidents/auto-escalate` | POST | Auto-escalate incidents | None |
| `/analytics/reconciliation-report` | GET | Generate reports | None |
| `/incidents/bulk-assign` | POST | Bulk assignment | None |
| `/incidents/search` | GET | Full-text search | None |

---

## 💡 Usage Scenarios

### Scenario 1: End-of-Day Report
```bash
# Generate 24-hour report at 5 PM
curl http://localhost:5001/analytics/reconciliation-report?days=1
```

### Scenario 2: SLA Management
```bash
# Auto-escalate incidents breaching 1-hour critical SLA
curl -X POST http://localhost:5001/incidents/auto-escalate?escalation_minutes=60
```

### Scenario 3: Batch Processing
```bash
# Assign 10 warning incidents to lead operator
curl -X POST http://localhost:5001/incidents/bulk-assign \
  -d '{"ids": ["id1", "id2", ...], "assignee": "alice", "note": "Daily batch"}'
```

### Scenario 4: CSV Audit
```bash
# Export all critical unresolved incidents for audit
curl "http://localhost:5001/discrepancies/export/csv?severity=critical&resolved=open" > audit.csv
```

---

## 🎯 Key Benefits

1. **Efficiency**: Bulk operations reduce manual work
2. **Visibility**: Comprehensive reporting and trend analysis
3. **Compliance**: Auto-escalation and audit trails for SLA adherence
4. **Flexibility**: Filter presets and advanced search
5. **Data Portability**: CSV export for external systems
6. **Analytics**: Weekly/monthly trends identify patterns

---

## 📈 Performance Metrics Tracked

- **Weekly Trends**: 4-week incident history
- **Monthly Trends**: 12-month incident history
- **Resolution Times**: Average, median, P95 metrics
- **SLA Compliance**: Percentage of incidents resolved in SLA window
- **Severity Distribution**: Critical, warning, info breakdown
- **Status Distribution**: By needs_review, assigned, escalated

---

## 🔐 Security Considerations

**Current MVP Status**: No authentication on endpoints
**Production Recommendations**:
1. Add API key/bearer token authentication
2. Implement role-based access (view reports, bulk ops, escalation)
3. Audit log all bulk operations
4. Rate limit bulk operations
5. Validate assignee names against active operators
6. Add data retention policies for CSV exports

---

## 🚀 Deployment Checklist

- ✅ Backend endpoints implemented in `app_2.py`
- ✅ Frontend tools page created (`/tools`)
- ✅ Sidebar navigation updated with tools link
- ✅ CSV export functionality working
- ✅ Report generation operational
- ✅ Auto-escalation logic ready
- ✅ Frontend build verified (6 routes prerendered)
- ✅ All components TypeScript validated

---

## 📝 Next Enhancement Ideas

1. **Webhook Notifications**: Notify external systems of escalations
2. **Email Reports**: Automated email distribution of reconciliation reports
3. **Custom Alert Rules**: User-defined escalation criteria
4. **Operator On-Call Rotation**: Track who's available for escalations
5. **Historical Trend Charts**: Visual trend analysis on dashboard
6. **Batch Reconciliation**: Process multiple reconciliation jobs
7. **API Rate Limiting**: Protect against abuse
8. **Advanced Search Syntax**: Boolean operators, date ranges
