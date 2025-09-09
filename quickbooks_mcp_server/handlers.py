"""
Tool handlers for the QuickBooks MCP server.
Implements three tools: get_entity_schema, query_quickbooks, get_report (normalized).
"""

import logging
from typing import Dict, Any, List, Optional

from .quickbooks_interaction import QuickBooksSession
from .api_importer import load_json_file

logger = logging.getLogger(__name__)


# Mapping from user-friendly "Previous" terminology to QuickBooks API "Last" terminology
PREVIOUS_TO_LAST_MAPPING = {
    "Previous Week": "Last Week",
    "Previous Week-to-date": "Last Week-to-date",
    "Previous Month": "Last Month",
    "Previous Month-to-date": "Last Month-to-date",
    "Previous Fiscal Quarter": "Last Fiscal Quarter",
    "Previous Fiscal Quarter-to-date": "Last Fiscal Quarter-to-date",
    "Previous Fiscal Year": "Last Fiscal Year",
    "Previous Fiscal Year-to-date": "Last Fiscal Year-to-date",
}


def convert_previous_to_last(value: str) -> str:
    """Convert 'Previous' terminology to 'Last' for QuickBooks API compatibility."""
    return PREVIOUS_TO_LAST_MAPPING.get(value, value)


def check_for_api_error(response: Dict[str, Any]) -> None:
    """Check if the response contains a QuickBooks API error and raise an exception if so."""
    if isinstance(response, dict) and "Fault" in response:
        error_msg = f"Error: {response.get('time', '')} {response}"
        raise RuntimeError(error_msg)


# Initialize QuickBooks session with error handling
quickbooks = None
try:
    quickbooks = QuickBooksSession()
    logger.info("QuickBooks session initialized successfully")
except Exception as e:
    logger.warning(f"QuickBooks session initialization deferred: {e}")


async def get_quickbooks_entity_schema(entity_name: str) -> Dict[str, Any]:
    """
    Fetches the schema for a given QuickBooks entity (e.g., 'Bill', 'Customer').
    Use this tool to understand the available fields for an entity before constructing a query with the `query_quickbooks` tool.
    """
    try:
        all_schemas = load_json_file("quickbooks_entity_schemas.json")
        entity_schema = all_schemas.get(entity_name)

        if entity_schema:
            return {"schema": entity_schema, "entity": entity_name}
        else:
            available_entities = list(all_schemas.keys())
            raise ValueError(
                f"Schema not found for entity '{entity_name}'. Available entities: {available_entities}"
            )
    except FileNotFoundError:
        raise FileNotFoundError(
            "The schema definition file `quickbooks_entity_schemas.json` was not found."
        )
    except Exception as e:
        raise RuntimeError(f"An error occurred: {e}")


def _extract_query_results(query_response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract the list of entity rows from a QuickBooks QueryResponse."""
    if not isinstance(query_response, dict):
        return []
    # Find the first key whose value is a list (entity collection)
    for key, value in query_response.items():
        if isinstance(value, list):
            return value
    return []


async def query_quickbooks(
    query: str, page_token: Optional[str] = None, page_size: Optional[int] = 500
) -> Dict[str, Any]:
    """
    Executes a read-only SQL-like query on a QuickBooks entity and returns a normalized shape:
    { result: [...], next_page_token?: string }
    """
    if quickbooks is None:
        raise RuntimeError(
            "QuickBooks session not initialized. Please check your credentials and restart the server."
        )

    start_position: Optional[int] = None
    if page_token:
        try:
            start_position = int(page_token)
        except ValueError:
            raise ValueError(
                "Invalid page_token; expected integer string for start position"
            )

    response = quickbooks.query(
        query, start_position=start_position, max_results=page_size
    )
    check_for_api_error(response)

    if not isinstance(response, dict):
        raise TypeError(f"Expected dict response but got {type(response).__name__}")

    qr = response.get("QueryResponse", {})
    rows = _extract_query_results(qr)

    # Compute next page token if available
    next_page_token: Optional[str] = None
    try:
        start = int(qr.get("startPosition", 1))
        max_results_val = None
        if "maxResults" in qr:
            try:
                max_results_val = int(qr.get("maxResults"))
            except Exception:
                max_results_val = None
        if max_results_val is None and page_size is not None:
            max_results_val = page_size
        total = None
        if "totalCount" in qr:
            try:
                total = int(qr.get("totalCount"))
            except Exception:
                total = None
        if (
            total is not None
            and max_results_val is not None
            and start + max_results_val <= total
        ):
            next_page_token = str(start + max_results_val)
        elif max_results_val is not None and len(rows) == max_results_val:
            next_page_token = str(start + max_results_val)
    except Exception:
        next_page_token = None

    result: Dict[str, Any] = {"result": rows}
    if next_page_token:
        result["next_page_token"] = next_page_token
    return result


def _get_column_titles(report_json: Dict[str, Any]) -> List[str]:
    columns = report_json.get("Columns", {}).get("Column", [])
    titles: List[str] = []
    for col in columns:
        title = col.get("ColTitle") or col.get("ColType") or ""
        titles.append(title)
    return titles


def _flatten_report_rows(report_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flatten QuickBooks report rows into long-format list of dict rows.
    Each output row corresponds to one (line, period) pair with an amount.
    """
    columns = _get_column_titles(report_json)
    rows_container = report_json.get("Rows", {})
    top_rows = rows_container.get("Row", []) if isinstance(rows_container, dict) else []

    flat_rows: List[Dict[str, Any]] = []

    def walk(rows: List[Dict[str, Any]], lineage: List[str]) -> None:
        for row in rows:
            row_type = row.get("type") or row.get("RowType")
            # Section rows contain nested Rows
            if row_type == "Section":
                header = row.get("Header", {})
                header_title = None
                coldata = header.get("ColData") or []
                if coldata and isinstance(coldata, list):
                    header_title = coldata[0].get("value")
                if not header_title:
                    header_title = header.get("Title")
                new_lineage = lineage + ([header_title] if header_title else [])
                nested = row.get("Rows", {}).get("Row", [])
                if isinstance(nested, list) and nested:
                    walk(nested, new_lineage)
                # Summary under section
                summary = row.get("Summary")
                if isinstance(summary, dict):
                    coldata = summary.get("ColData", [])
                    label = summary.get("ColTitle") or (
                        coldata[0].get("value") if coldata else None
                    )
                    full_line = " > ".join(new_lineage + ([label] if label else []))
                    for idx, cd in enumerate(coldata[1:], start=1):
                        amount_str = cd.get("value")
                        try:
                            amount = float(amount_str)
                        except (TypeError, ValueError):
                            continue
                        period = columns[idx] if idx < len(columns) else f"col_{idx}"
                        flat_rows.append(
                            {
                                "line": full_line,
                                "period": period,
                                "amount": amount,
                                "line_type": "Summary",
                                "depth": len(new_lineage),
                            }
                        )
                continue

            # Data or Summary rows with values
            coldata = row.get("ColData", [])
            label = coldata[0].get("value") if coldata else None
            line_id = coldata[0].get("id") if coldata else None
            full_line = " > ".join(lineage + ([label] if label else []))
            for idx, cd in enumerate(coldata[1:], start=1):
                amount_str = cd.get("value")
                try:
                    amount = float(amount_str)
                except (TypeError, ValueError):
                    # Skip non-numeric columns in long format
                    continue
                period = columns[idx] if idx < len(columns) else f"col_{idx}"
                flat_rows.append(
                    {
                        "line": full_line,
                        "period": period,
                        "amount": amount,
                        "line_type": row_type or "Data",
                        "depth": len(lineage),
                        **({"line_id": line_id} if line_id else {}),
                    }
                )

    if isinstance(top_rows, list):
        walk(top_rows, [])

    return flat_rows


def _build_report_meta(
    report_json: Dict[str, Any],
    report_name: str,
    date_macro: Optional[str],
    group_by: Optional[str],
    qb_realm_id: Optional[str],
) -> Dict[str, Any]:
    header = report_json.get("Header", {})
    meta: Dict[str, Any] = {
        "report_name": report_name,
        "period": {
            "start_date": header.get("StartPeriod"),
            "end_date": header.get("EndPeriod"),
            "date_macro": date_macro,
        },
        "columns": _get_column_titles(report_json),
    }
    currency = header.get("Currency")
    if currency is not None:
        meta["currency"] = currency
    if group_by is not None:
        meta["group_by"] = group_by
    if qb_realm_id is not None:
        meta["source"] = {"qb_realm_id": qb_realm_id}
    return meta


async def get_report(
    report_name: str,
    accounting_method: Optional[str] = None,
    date_macro: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    group_by: Optional[str] = None,
    filters: Optional[Dict[str, str]] = None,
    page_token: Optional[str] = None,
) -> Dict[str, Any]:
    """Run a QuickBooks report and return normalized long-format rows with meta."""
    if quickbooks is None:
        raise RuntimeError("QuickBooks session not initialized.")

    params: Dict[str, Any] = {}

    if accounting_method:
        params["accounting_method"] = accounting_method
    if date_macro:
        params["date_macro"] = convert_previous_to_last(date_macro)
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    if group_by:
        params["summarize_column_by"] = group_by
    if isinstance(filters, dict):
        for k in ["customer", "vendor", "class", "department", "item", "account"]:
            v = filters.get(k)
            if v:
                params[k] = v
    if page_token:
        try:
            params["startposition"] = int(page_token)
        except ValueError:
            raise ValueError(
                "Invalid page_token; expected integer string for start position"
            )

    response = quickbooks.call_route("get", f"/reports/{report_name}", params=params)
    check_for_api_error(response)

    if not isinstance(response, dict):
        raise TypeError(f"Expected dict response but got {type(response).__name__}")

    normalized_rows = _flatten_report_rows(response)
    meta = _build_report_meta(
        response,
        report_name=report_name,
        date_macro=date_macro,
        group_by=group_by,
        qb_realm_id=getattr(quickbooks, "company_id", None),
    )

    result: Dict[str, Any] = {"result": normalized_rows, "meta": meta}
    # Reports pagination (if present) – QuickBooks may include startPosition/maxResults/totalCount
    try:
        header = response.get("Header", {})
        start = int(header.get("StartPosition", 0) or header.get("startPosition", 0))
        max_results = int(header.get("MaxResults", 0) or header.get("maxResults", 0))
        total = int(header.get("TotalCount", 0) or header.get("totalCount", 0))
        if total and start and max_results and (start + max_results <= total):
            result["next_page_token"] = str(start + max_results)
    except Exception:
        pass

    return result


# Dictionary to hold all tool functions (only the three requested)
TOOL_FUNCTIONS: Dict[str, Any] = {
    "get_entity_schema": get_quickbooks_entity_schema,
    "query_quickbooks": query_quickbooks,
    "get_report": get_report,
}

logger.info(
    f"Registered {len(TOOL_FUNCTIONS)} tool functions: {list(TOOL_FUNCTIONS.keys())}"
)
