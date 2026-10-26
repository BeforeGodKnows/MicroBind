"""Expose the same source evidence tools over official MCP SDK stdio transport."""

import argparse
from pathlib import Path

from .engine import Analyzer
from .evidence_tools import EvidenceTools
from .frontend import Project


def main():
    from mcp.server import MCPServer

    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    project = Project(args.manifest)
    tools = EvidenceTools(project, Analyzer(project).run())
    server = MCPServer("MicroBind source evidence")

    @server.tool()
    def get_method(method_id: str) -> dict:
        """Read a parsed method with source location and evidence ID."""
        return tools.call("get_method", {"method_id": method_id})

    @server.tool()
    def get_sql(method_id: str) -> dict:
        """Read SQL and its parameter constraints."""
        return tools.call("get_sql", {"method_id": method_id})

    @server.tool()
    def get_path(finding_id: str) -> dict:
        """Read cross-service call steps and object bindings."""
        return tools.call("get_path", {"finding_id": finding_id})

    @server.tool()
    def get_policy(finding_id: str) -> dict:
        """Read configured policy and trust assumptions."""
        return tools.call("get_policy", {"finding_id": finding_id})

    @server.tool()
    def search_methods(query: str) -> dict:
        """Search parsed method identifiers, with a bounded literal query."""
        return tools.call("search_methods", {"query": query})

    server.run(transport="stdio")


if __name__ == "__main__":
    main()
