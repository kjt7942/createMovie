"""
bridge.py — run the unmodified official Blender Lab MCP add-on inside a background Blender.

Started by blender_mcp.mjs:
    blender --background [file.blend] --factory-startup --python bridge.py -- --port 9876

The add-on is imported from the cloned repository (BLENDER_MCP_REPO/addon), so nothing is installed
into Blender's user preferences. It listens on 127.0.0.1 only and serves requests until killed.
"""
import os
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
port = "9876"
if "--port" in argv:
    port = argv[argv.index("--port") + 1]

repo = os.environ.get("BLENDER_MCP_REPO")
if not repo or not os.path.isdir(os.path.join(repo, "addon")):
    print("bridge: BLENDER_MCP_REPO does not point to the blender_mcp repository", flush=True)
    sys.exit(2)
sys.path.insert(0, os.path.join(repo, "addon"))

import blender_mcp_addon  # noqa: E402
from blender_mcp_addon.cli import cli_execute  # noqa: E402

blender_mcp_addon.register()
print(f"bridge: official add-on registered, serving on 127.0.0.1:{port}", flush=True)
sys.exit(cli_execute(["--host", "127.0.0.1", "--port", port]))
