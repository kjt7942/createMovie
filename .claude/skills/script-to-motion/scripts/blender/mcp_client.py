"""
mcp_client.py — call the official Blender MCP server over stdio, the same way an MCP client does.

Run with the MCP venv's Python (blender_mcp.mjs does this):
    python mcp_client.py --server /path/to/blender-mcp --list
    python mcp_client.py --server … --tool execute_blender_code --code-file script.py
    python mcp_client.py --server … --tool get_objects_summary --args '{}'

Prints the tool result as JSON. Exit code 1 when the tool reports an error (including Python
exceptions raised inside Blender). Every call is appended to --log (JSON lines) when given.
"""
from __future__ import annotations   # (`str | None` below on an older Python; the mcp SDK itself needs 3.10+)

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def blender_error(result) -> str | None:
    if getattr(result, "isError", False):
        return "MCP tool call failed"
    for content in getattr(result, "content", []) or []:
        if getattr(content, "type", "") != "text":
            continue
        try:
            value = json.loads(content.text)
        except ValueError:
            continue
        if isinstance(value, dict) and value.get("status") == "error":
            return value.get("message", "Blender reported an error")
    return None


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", required=True)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--tool", default="execute_blender_code")
    ap.add_argument("--code-file")
    ap.add_argument("--args", default=None, help="JSON object of tool arguments")
    ap.add_argument("--log")
    a = ap.parse_args()

    params = StdioServerParameters(command=a.server)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            if a.list:
                result = await session.list_tools()
                tool = "list_tools"
            else:
                args = json.loads(a.args) if a.args else {}
                if a.code_file:
                    args["code"] = Path(a.code_file).read_text(encoding="utf-8")
                result = await session.call_tool(a.tool, args)
                tool = a.tool
    data = result.model_dump(mode="json", exclude_none=True)
    if a.log:
        with open(a.log, "a", encoding="utf-8") as f:
            f.write(json.dumps({"time": datetime.now(timezone.utc).isoformat(), "tool": tool,
                                "code_file": a.code_file, "response": data}, ensure_ascii=False) + "\n")
    print(json.dumps(data, ensure_ascii=False, indent=2))
    err = None if a.list else blender_error(result)
    if err:
        print("ERROR: " + err, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
