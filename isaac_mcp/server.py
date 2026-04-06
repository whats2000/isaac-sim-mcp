# MIT License
#
# Copyright (c) 2023-2025 omni-mcp
# Copyright (c) 2026 whats2000
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""Isaac Sim MCP Server — entry point.

Registers all tools from tools/ submodules and starts the FastMCP server.
"""

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict

from mcp.server.fastmcp import FastMCP

from isaac_mcp.connection import get_isaac_connection, reset_isaac_connection
from isaac_mcp.tools import register_all_tools

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("IsaacMCPServer")


@asynccontextmanager
async def server_lifespan(server: FastMCP) -> AsyncIterator[Dict[str, Any]]:
    """Manage server startup and shutdown lifecycle."""
    try:
        logger.info("IsaacMCP server starting up")
        try:
            get_isaac_connection()
            logger.info("Successfully connected to Isaac on startup")
        except Exception as e:
            logger.warning(f"Could not connect to Isaac on startup: {e}")
        yield {}
    finally:
        reset_isaac_connection()
        logger.info("IsaacMCP server shut down")


_INSTRUCTIONS = """\
Isaac Sim integration through the Model Context Protocol.

## MCP Tools vs Scripts / Action Graphs

MCP tools operate BETWEEN frames (editor-level): scene setup, inspection, stepping, joint control, diagnostics.
Scripts/Action Graphs operate WITHIN frames (runtime-level): control loops, IK, state machines.

## Workflow

### Scene Setup
1. get_scene_info → 2. create_physics_scene → 3. create_robot / create_object → 4. get_prim_info (verify sizes)
- create_robot: call list_available_robots first for exact keys (lowercase, no spaces, e.g. "frankafr3")
- Always get_prim_info to query actual positions/sizes BEFORE writing controller scripts

### Debug Loop
step_simulation with observe_prims/observe_joints. If issues: get_joint_config, get_physics_state, get_isaac_logs.
Do NOT use play_simulation + sleep + execute_script as a debug loop.

### Controller Development
Write .py file → reload_script → step_simulation to debug → edit & reload → play_simulation when ready.

### ScriptNode (Action Graph)
create_action_graph(script_file="/path/to/controller.py") wires OnPlaybackTick → ScriptNode.

**ScriptNode rules:**
1. MUST define setup(db) and compute(db) — never use legacy mode (no compute = broken exec scoping)
2. Use module-level globals + `global` keyword in compute() for persistent state
3. Subscribe to timeline STOP event to reset state (or Stop→Play leaves stale objects)
4. WARMUP pattern: skip ~30 frames in compute() before calling World.initialize_physics() + robot.initialize()
5. ScriptNode fires once during create_action_graph — objects created then go stale at Play

See demo/franka_pick_place.py for a complete working example.

### Tool Priority
Prefer named tools over execute_script: get_joint_positions, get_prim_info, get_physics_state,
get_joint_config, get_isaac_logs, create_action_graph, edit_action_graph.
"""

mcp = FastMCP(
    "IsaacSimMCP",
    instructions=_INSTRUCTIONS,
    lifespan=server_lifespan,
)

register_all_tools(mcp, get_isaac_connection)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
