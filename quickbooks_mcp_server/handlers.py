"""
Tool handlers for the QuickBooks MCP server.
Contains all the tool function implementations.
"""

import logging
from typing import Dict, Any

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


async def query_quickbooks(query: str) -> Dict[str, Any]:
    """
    Executes a SQL-like query on a QuickBooks entity.
    **IMPORTANT**: Before using this tool, you MUST first use the `get_quickbooks_entity_schema` tool to get the schema for the entity you want to query (e.g., 'Bill', 'Customer'). This will show you the available fields to use in your query's `select` and `where` clauses.
    """
    if quickbooks is None:
        raise RuntimeError(
            "QuickBooks session not initialized. Please check your credentials and restart the server."
        )

    response = quickbooks.query(query)
    if isinstance(response, dict):
        return response
    elif isinstance(response, list):
        return {"results": response}
    else:
        raise TypeError(f"Expected dict response but got {type(response).__name__}")


# Hardcoded API tool functions
async def get_account(account_id: str) -> Dict[str, Any]:
    """Retrieve a specific QuickBooks account by its ID."""
    if quickbooks is None:
        raise RuntimeError("QuickBooks session not initialized.")

    response = quickbooks.call_route("get", f"/account/{account_id}")
    return response if isinstance(response, dict) else {"results": response}


async def get_bill(bill_id: str) -> Dict[str, Any]:
    """Retrieve a specific bill by its ID."""
    if quickbooks is None:
        raise RuntimeError("QuickBooks session not initialized.")

    response = quickbooks.call_route("get", f"/bill/{bill_id}")
    return response if isinstance(response, dict) else {"results": response}


async def get_billpayment(billpayment_id: str) -> Dict[str, Any]:
    """Retrieve a specific bill payment by its ID."""
    if quickbooks is None:
        raise RuntimeError("QuickBooks session not initialized.")

    response = quickbooks.call_route("get", f"/billpayment/{billpayment_id}")
    return response if isinstance(response, dict) else {"results": response}


async def get_customer(customer_id: str) -> Dict[str, Any]:
    """Retrieve a specific customer by their ID."""
    if quickbooks is None:
        raise RuntimeError("QuickBooks session not initialized.")

    response = quickbooks.call_route("get", f"/customer/{customer_id}")
    return response if isinstance(response, dict) else {"results": response}


async def get_vendor(vendor_id: str) -> Dict[str, Any]:
    """Retrieve a specific vendor by their ID."""
    if quickbooks is None:
        raise RuntimeError("QuickBooks session not initialized.")

    response = quickbooks.call_route("get", f"/vendor/{vendor_id}")
    return response if isinstance(response, dict) else {"results": response}


async def get_taxagency(taxagency_id: str, minorversion: str = None) -> Dict[str, Any]:
    """Retrieve a specific tax agency by its ID."""
    if quickbooks is None:
        raise RuntimeError("QuickBooks session not initialized.")

    params = {"minorversion": minorversion} if minorversion else {}
    response = quickbooks.call_route("get", f"/taxagency/{taxagency_id}", params=params)
    return response if isinstance(response, dict) else {"results": response}


async def get_payment(payment_id: str) -> Dict[str, Any]:
    """Retrieve a specific payment by its ID."""
    if quickbooks is None:
        raise RuntimeError("QuickBooks session not initialized.")

    response = quickbooks.call_route("get", f"/payment/{payment_id}")
    return response if isinstance(response, dict) else {"results": response}


async def get_item(item_id: str, minorversion: str = None) -> Dict[str, Any]:
    """Retrieve a specific item/product by its ID."""
    if quickbooks is None:
        raise RuntimeError("QuickBooks session not initialized.")

    params = {"minorversion": minorversion} if minorversion else {}
    response = quickbooks.call_route("get", f"/item/{item_id}", params=params)
    return response if isinstance(response, dict) else {"results": response}


async def get_employee(employee_id: str, minorversion: str = None) -> Dict[str, Any]:
    """Retrieve a specific employee by their ID."""
    if quickbooks is None:
        raise RuntimeError("QuickBooks session not initialized.")

    params = {"minorversion": minorversion} if minorversion else {}
    response = quickbooks.call_route("get", f"/employee/{employee_id}", params=params)
    return response if isinstance(response, dict) else {"results": response}


async def get_class(class_id: str) -> Dict[str, Any]:
    """Retrieve a specific class by its ID."""
    if quickbooks is None:
        raise RuntimeError("QuickBooks session not initialized.")

    response = quickbooks.call_route("get", f"/class/{class_id}")
    return response if isinstance(response, dict) else {"results": response}


async def get_department(department_id: str) -> Dict[str, Any]:
    """Retrieve a specific department by its ID."""
    if quickbooks is None:
        raise RuntimeError("QuickBooks session not initialized.")

    response = quickbooks.call_route("get", f"/department/{department_id}")
    return response if isinstance(response, dict) else {"results": response}


async def get_journalentry(journal_entry_id: str) -> Dict[str, Any]:
    """Retrieve a specific journal entry by its ID."""
    if quickbooks is None:
        raise RuntimeError("QuickBooks session not initialized.")

    response = quickbooks.call_route("get", f"/journalentry/{journal_entry_id}")
    return response if isinstance(response, dict) else {"results": response}


async def get_estimate(estimate_id: str) -> Dict[str, Any]:
    """Retrieve a specific estimate/quote by its ID."""
    if quickbooks is None:
        raise RuntimeError("QuickBooks session not initialized.")

    response = quickbooks.call_route("get", f"/estimate/{estimate_id}")
    return response if isinstance(response, dict) else {"results": response}


async def get_preferences() -> Dict[str, Any]:
    """Retrieve the company's preferences and settings."""
    if quickbooks is None:
        raise RuntimeError("QuickBooks session not initialized.")

    response = quickbooks.call_route("get", "/preferences")
    return response if isinstance(response, dict) else {"results": response}


async def get_reports_profit_and_loss(**kwargs) -> Dict[str, Any]:
    """Generate a Profit and Loss report."""
    if quickbooks is None:
        raise RuntimeError("QuickBooks session not initialized.")

    # Apply Previous->Last mapping for date_macro
    params = {}
    for key, value in kwargs.items():
        if value is not None:
            if key == "date_macro" and isinstance(value, str):
                params[key] = convert_previous_to_last(value)
            else:
                params[key] = value

    response = quickbooks.call_route("get", "/reports/ProfitAndLoss", params=params)
    return response if isinstance(response, dict) else {"results": response}


# Dictionary to hold all tool functions
TOOL_FUNCTIONS: Dict[str, Any] = {
    "get_entity_schema": get_quickbooks_entity_schema,
    "query_quickbooks": query_quickbooks,
    "get_account": get_account,
    "get_bill": get_bill,
    "get_billpayment": get_billpayment,
    "get_customer": get_customer,
    "get_vendor": get_vendor,
    "get_taxagency": get_taxagency,
    "get_payment": get_payment,
    "get_item": get_item,
    "get_employee": get_employee,
    "get_class": get_class,
    "get_department": get_department,
    "get_journalentry": get_journalentry,
    "get_estimate": get_estimate,
    "get_preferences": get_preferences,
    "get_reports_profit_and_loss": get_reports_profit_and_loss,
}

logger.info(f"Registered {len(TOOL_FUNCTIONS)} hardcoded tool functions")
