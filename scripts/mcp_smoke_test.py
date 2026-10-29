"""Protocol-level MCP smoke test; requires exported CSVs in data/."""
import asyncio
import os
import sys
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    source = Path(os.environ.get("QUALITY_DATA_DIR", "data")).resolve()
    if not (source / "gold.csv").is_file() or not (source / "quarantine_reasons.csv").is_file():
        raise SystemExit("Export gold.csv and quarantine_reasons.csv into data/ first")
    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "quality_portal.mcp_server"],
        env={"QUALITY_DATA_DIR": str(source)},
    )
    async with stdio_client(server) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            listed = await session.list_tools()
            expected = {"get_quality_summary", "list_quarantine_reasons", "list_gold_segments"}
            names = {tool.name for tool in listed.tools}
            print("MCP TOOLS:", sorted(names))
            assert names == expected, f"Unexpected MCP interface: {names}"
            for name, args in [
                ("get_quality_summary", {}),
                ("list_quarantine_reasons", {}),
                ("list_gold_segments", {"limit": 2}),
            ]:
                response = await session.call_tool(name, arguments=args)
                assert not response.isError, f"MCP call {name} failed: {response.content}"
                print(name, response.content)
    print("MCP VALIDATION COMPLETE")

if __name__ == "__main__":
    asyncio.run(main())
