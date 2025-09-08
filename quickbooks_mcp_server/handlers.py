"""
Tool handlers for the QuickBooks MCP server.
Contains all the tool function implementations.
"""

import json
import logging
from typing import Dict, List, Any, Optional

from .quickbooks_interaction import QuickBooksSession
from .api_importer import load_json_file

logger = logging.getLogger(__name__)

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


# Dynamic tool function generator
def create_api_tool_function(api_info: Dict[str, Any]):
    """Create a tool function for a specific QuickBooks API endpoint."""

    async def api_tool_function(**kwargs) -> Dict[str, Any]:
        # Check if QuickBooks is initialized
        if quickbooks is None:
            raise RuntimeError(
                "Error: QuickBooks session not initialized. Please check your credentials and restart the server."
            )

        try:
            # Clean up the route and remove the company/realm part
            original_route = api_info["route"]
            if "/v3/company/{realmId}" in original_route:
                clean_api_route = original_route.replace("/v3/company/{realmId}", "")
            else:
                clean_api_route = original_route

            route = clean_api_route
            api_method = api_info["method"]

            path_params = {}
            query_params = {}
            request_body = {}

            # Separate parameters based on their location ('in')
            api_params = [
                p for p in api_info.get("parameters", []) if p["name"] != "realmId"
            ]
            for p_info in api_params:
                p_name = p_info["name"]
                if p_name in kwargs and kwargs[p_name] is not None:
                    if p_info["location"] == "path":
                        path_params[p_name] = kwargs[p_name]
                    elif p_info["location"] == "query":
                        query_params[p_name] = kwargs[p_name]

            # The rest of kwargs are assumed to be the request body for POST/PUT/PATCH
            if api_method.lower() in ["post", "put", "patch"]:
                body_keys = (
                    set(kwargs.keys())
                    - set(path_params.keys())
                    - set(query_params.keys())
                )
                for k in body_keys:
                    if kwargs[k] is not None:
                        request_body[k] = kwargs[k]

            # Format the route with path parameters
            if path_params:
                try:
                    route = route.format(**path_params)
                except KeyError as e:
                    raise KeyError(
                        f"Error: Missing required path parameter {e} for route {route}"
                    )

            response = quickbooks.call_route(
                method_type=api_method,
                route=route,
                params=query_params,
                body=request_body if request_body else None,
            )

            # Return the actual Python object
            if isinstance(response, dict):
                return response
            elif isinstance(response, list):
                return {"results": response}
            else:
                raise TypeError(
                    f"Expected dict response but got {type(response).__name__}"
                )
        except Exception as e:
            logger.error(f"Error executing API tool: {e}")
            raise RuntimeError(f"Error executing API call: {e}")

    return api_tool_function


# Dictionary to hold all tool functions - will be populated dynamically
TOOL_FUNCTIONS: Dict[str, Any] = {
    "get_quickbooks_entity_schema": get_quickbooks_entity_schema,
    "query_quickbooks": query_quickbooks,
}


def register_api_tools():
    """Register all QuickBooks API tools dynamically."""
    from .api_importer import load_apis

    try:
        apis = load_apis()
        logger.info(f"Loading {len(apis)} QuickBooks API endpoints as tools")

        for api in apis:
            # Clean up the route and remove the company/realm part
            original_route = api["route"]
            if "/v3/company/{realmId}" in original_route:
                clean_api_route = original_route.replace("/v3/company/{realmId}", "")
            else:
                clean_api_route = original_route

            clean_route_for_name = (
                clean_api_route.replace("/", "_")
                .replace("-", "_")
                .replace(":", "_")
                .replace("{", "")
                .replace("}", "")
            )

            tool_name = f"{api['method']}{clean_route_for_name}"

            # Create the tool function
            tool_function = create_api_tool_function(api)
            TOOL_FUNCTIONS[tool_name] = tool_function

        logger.info(f"Successfully registered {len(TOOL_FUNCTIONS)} tools")

    except Exception as e:
        logger.error(f"Error registering API tools: {e}")
        raise


# Register all API tools when module is imported
register_api_tools()
