import json
import sys
from typing import Dict, List, Any, TypedDict, Optional

from mcp.server.fastmcp import FastMCP

from .quickbooks_interaction import QuickBooksSession
from .api_importer import load_apis, load_json_file

# Initialize QuickBooks session with error handling
quickbooks = None
try:
    quickbooks = QuickBooksSession()
    print("✓ QuickBooks session initialized successfully", file=sys.stderr)
except Exception:
    # Defer reporting to tool invocation time
    pass

# Create the MCP server
mcp = FastMCP("quickbooks")


# Define structured response types
class QuickBooksEntity(TypedDict, total=False):
    """Base QuickBooks entity structure."""

    Id: str
    Name: str
    Active: bool
    SyncToken: str
    MetaData: Dict[str, Any]


class QuickBooksAccount(QuickBooksEntity, total=False):
    """QuickBooks Account entity structure."""

    SubAccount: bool
    FullyQualifiedName: str
    Classification: str
    AccountType: str
    AccountSubType: str
    CurrentBalance: float
    CurrentBalanceWithSubAccounts: float
    CurrencyRef: Dict[str, str]
    domain: str
    sparse: bool


class QueryResponse(TypedDict, total=False):
    """QuickBooks Query Response structure."""

    Account: List[QuickBooksAccount]
    Bill: List[Dict[str, Any]]
    Customer: List[Dict[str, Any]]
    Vendor: List[Dict[str, Any]]
    Item: List[Dict[str, Any]]
    startPosition: int
    maxResults: int


class QuickBooksQueryResult(TypedDict):
    """Complete QuickBooks query result structure."""

    QueryResponse: QueryResponse
    time: str


class EntitySchema(TypedDict):
    """QuickBooks entity schema structure."""

    properties: Dict[str, Dict[str, Any]]


@mcp.tool()
def get_quickbooks_entity_schema(entity_name: str) -> Dict[str, Any]:
    """
    Fetches the schema for a given QuickBooks entity (e.g., 'Bill', 'Customer').
    Use this tool to understand the available fields for an entity before constructing a query with the `query_quickbooks` tool.
    """
    try:
        all_schemas = load_json_file("quickbooks_entity_schemas.json")
        entity_schema = all_schemas.get(entity_name)

        if entity_schema:
            # Return the raw schema - FastMCP should handle this as structured content
            return entity_schema
        else:
            available_entities = list(all_schemas.keys())
            raise KeyError(
                f"Schema not found for entity '{entity_name}'. Available entities: {available_entities}"
            )
    except FileNotFoundError:
        raise FileNotFoundError(
            "The schema definition file `quickbooks_entity_schemas.json` was not found."
        )
    except Exception as e:
        raise RuntimeError(f"An error occurred: {e}")


@mcp.tool()
def query_quickbooks(query: str) -> Dict[str, Any]:
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
        # Return the raw response - FastMCP should handle this as structured content
        return response
    elif isinstance(response, list):
        # Handle list responses by wrapping in a results structure
        return {"results": response}
    else:
        raise TypeError(f"Expected dict response but got {type(response).__name__}")


def register_all_apis():
    apis = load_apis()
    for api in apis:
        response_description = api["response_description"]

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

        method_name = f"{api['method']}{clean_route_for_name}"
        clean_summary = api["summary"]
        if clean_summary is None:
            words = method_name.split("_")
            words[0] = words[0].capitalize()
            clean_summary = " ".join(words) + ". "

        doc = clean_summary + ". "
        if response_description != "OK":
            doc += (
                f'If successful, the outcome will be "{api["response_description"]}". '
            )

        # Combine request_data and parameters for the docstring
        all_params = {}
        api_params_filtered = [
            p for p in api.get("parameters", []) if p["name"] != "realmId"
        ]

        if api_params_filtered:
            for p in api_params_filtered:
                all_params[p["name"]] = {
                    "description": p.get("description", "No description provided"),
                    "required": p.get("required", False),
                    "type": p.get("type", "unknown"),
                    "in": p.get("location"),
                }

        if api.get("request_data"):
            doc += f"The request body should be a JSON object with the following structure: {json.dumps(api['request_data'])}. "

        if all_params:
            doc += f"Parameters: {json.dumps(all_params, indent=2)}. "

        # Create a more structured tool function definition with proper return type
        method_str = f'''
@mcp.tool()
def {method_name}(**kwargs) -> Dict[str, Any]:
    """{doc}"""
    
    # Check if QuickBooks is initialized
    if quickbooks is None:
        raise RuntimeError("Error: QuickBooks session not initialized. Please check your credentials and restart the server.")
    
    # Workaround for clients that pass all arguments as a single string in 'kwargs'
    if 'kwargs' in kwargs and isinstance(kwargs['kwargs'], str) and '=' in kwargs['kwargs']:
        try:
            key, value = kwargs['kwargs'].split('=', 1)
            # Overwrite kwargs with the parsed arguments
            kwargs = {{key: value}}
        except Exception:
            # If parsing fails, do nothing and proceed with the original kwargs
            pass

    try:
        route = "{clean_api_route}"
        api_method = "{api["method"]}"
        
        path_params = {{}}
        query_params = {{}}
        request_body = {{}}

        # Separate parameters based on their location ('in')
        api_params = {api_params_filtered}
        for p_info in api_params:
            p_name = p_info['name']
            if p_name in kwargs:
                if p_info['location'] == 'path':
                    path_params[p_name] = kwargs[p_name]
                elif p_info['location'] == 'query':
                    query_params[p_name] = kwargs[p_name]

        # The rest of kwargs are assumed to be the request body for POST/PUT/PATCH
        if api_method.lower() in ['post', 'put', 'patch']:
            body_keys = set(kwargs.keys()) - set(path_params.keys()) - set(query_params.keys())
            for k in body_keys:
                request_body[k] = kwargs[k]

        # Format the route with path parameters
        if path_params:
            try:
                route = route.format(**path_params)
            except KeyError as e:
                raise KeyError(f"Error: Missing required path parameter {{e}} for route {{route}}")

        response = quickbooks.call_route(
            method_type=api_method,
            route=route,
            params=query_params,
            body=request_body if request_body else None
        )
        
        # Return the actual Python object - FastMCP will handle structured content
        if isinstance(response, dict):
            return response
        elif isinstance(response, list):
           return {{"results": response}}
        else:
            raise TypeError(f"Expected dict response but got {{type(response).__name__}}")
    except Exception as e:
        raise RuntimeError(f"Error executing {method_name}: {{e}}")
'''
        exec(method_str, globals(), locals())


register_all_apis()


def main():
    """Main entry point for the QuickBooks MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
