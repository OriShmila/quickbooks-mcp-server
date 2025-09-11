"""
QuickBooks MCP Server using standard MCP server implementation.
Provides QuickBooks API access through MCP tools with proper input schemas and enums.
"""

import json
import sys
import os
import logging
from typing import Dict, List, Any

from mcp.server import Server
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types

from .handlers import TOOL_FUNCTIONS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("QuickBooksMCP")
logging.getLogger("httpx").setLevel(logging.WARNING)


def _package_path(filename: str) -> str:
    """Get the path to a file in the package directory."""
    base_dir = os.path.dirname(__file__)
    return os.path.join(base_dir, filename)


def load_tool_schemas() -> Dict[str, Any]:
    """Load tool schemas bundled in the package."""
    # Prefer package copy; fall back to CWD for local dev
    candidates = [
        _package_path("tools.json"),
        os.path.join(os.getcwd(), "tools.json"),
    ]
    for path in candidates:
        try:
            with open(path, "r") as f:
                schema_data = json.load(f)
            logger.info(f"Loaded tool schemas from {path}")
            return {tool["name"]: tool for tool in schema_data["tools"]}
        except FileNotFoundError:
            continue
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing tools.json at {path}: {e}")
            return {}
    logger.error("tools.json file not found in package or working directory")
    return {}


# Load tool schemas
TOOL_SCHEMAS = load_tool_schemas()
logger.info(f"Loaded {len(TOOL_SCHEMAS)} tool schemas")

# Create the MCP server
server = Server("QuickBooks")


@server.list_tools()
async def handle_list_tools() -> List[types.Tool]:
    """Handle list_tools request by returning all available tools with their schemas."""
    try:
        tools: List[types.Tool] = []

        for tool_name, tool_schema in TOOL_SCHEMAS.items():
            # Ensure the tool function exists
            if tool_name not in TOOL_FUNCTIONS:
                logger.warning(
                    f"Tool schema exists for {tool_name} but no handler function found"
                )
                continue

            tools.append(
                types.Tool(
                    name=tool_name,
                    description=tool_schema["description"],
                    inputSchema=tool_schema["inputSchema"],
                )
            )

        return tools
    except Exception as e:
        raise e


@server.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any] | None) -> Any:
    """Handle call_tool request by executing the requested tool with provided arguments."""
# todo validate env exisit here
    if name not in TOOL_FUNCTIONS:
        logger.error(f"Unknown tool requested: {name}")
        raise ValueError(f"Unknown tool: {name}")

    if arguments is None:
        arguments = {}

    try:
        tool_function = TOOL_FUNCTIONS[name]
        result = await tool_function(**arguments)
        return result
    except Exception as e:
        raise ValueError(f"Tool execution error: {str(e)}")


async def run_server() -> None:
    """Run the MCP server with stdio transport."""
    logger.info("Starting QuickBooks MCP Server")

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="QuickBooks",
                server_version="1.0.0",
                capabilities=types.ServerCapabilities(tools=types.ToolsCapability()),
            ),
        )


def main():
    """Main entry point for the QuickBooks MCP server."""
    import asyncio

    try:
        logger.info("QuickBooks MCP Server starting...")
        asyncio.run(run_server())
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception:
        # Log full traceback to diagnose TaskGroup/async errors
        logger.exception("Server error")
        sys.exit(1)


if __name__ == "__main__":
    main()
