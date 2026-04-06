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

"""Simulation control MCP tools."""

import json
from typing import TYPE_CHECKING, Callable, List, Optional

from mcp.server.fastmcp import FastMCP

if TYPE_CHECKING:
    from isaac_mcp.connection import IsaacConnection


def register_tools(mcp: FastMCP, get_connection: "Callable[[], IsaacConnection]") -> None:

    @mcp.tool("play_simulation")
    def play_simulation() -> str:
        """Start the physics simulation."""
        try:
            conn = get_connection()
            result = conn.send_command("simulation.play")
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    @mcp.tool("pause_simulation")
    def pause_simulation() -> str:
        """Pause the physics simulation."""
        try:
            conn = get_connection()
            result = conn.send_command("simulation.pause")
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    @mcp.tool("stop_simulation")
    def stop_simulation() -> str:
        """Stop the physics simulation."""
        try:
            conn = get_connection()
            result = conn.send_command("simulation.stop")
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    @mcp.tool("step_simulation")
    def step_simulation(
        num_steps: int = 1, observe_prims: Optional[List[str]] = None, observe_joints: Optional[List[str]] = None
    ) -> str:
        """Step the simulation forward by N frames, then observe prim and joint states.

        This is the primary tool for debugging robot behavior. Use it instead of
        play_simulation + sleep + execute_script. The observe parameters let you
        inspect positions, velocities, and joint states in a single call.

        Typical debug loop:
          1. set_joint_positions to command the robot
          2. step_simulation with observe_prims and observe_joints
          3. get_joint_config if drives are not tracking correctly
          4. get_physics_state if objects are not behaving as expected
          5. Adjust and repeat

        Args:
            num_steps: Number of simulation frames to step.
            observe_prims: List of prim paths to observe (returns position + velocity).
            observe_joints: List of articulation prim paths to observe (returns joint positions).
        """
        try:
            conn = get_connection()
            params = {"num_steps": num_steps}
            if observe_prims is not None:
                params["observe_prims"] = observe_prims
            if observe_joints is not None:
                params["observe_joints"] = observe_joints
            result = conn.send_command("simulation.step", params)
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    @mcp.tool("set_physics_params")
    def set_physics_params(
        gravity: Optional[List[float]] = None, time_step: Optional[float] = None, gpu_enabled: Optional[bool] = None
    ) -> str:
        """Configure physics engine parameters.

        Args:
            gravity: Gravity vector [x, y, z].
            time_step: Physics time step in seconds.
            gpu_enabled: Enable GPU-accelerated physics.
        """
        try:
            conn = get_connection()
            params = {}
            if gravity is not None:
                params["gravity"] = gravity
            if time_step is not None:
                params["time_step"] = time_step
            if gpu_enabled is not None:
                params["gpu_enabled"] = gpu_enabled
            result = conn.send_command("simulation.set_physics", params)
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    @mcp.tool("get_isaac_logs")
    def get_isaac_logs(clear: bool = True, count: int = 100) -> str:
        """Diagnostic tool: get recent warnings and errors from the Isaac Sim console.

        Call this after any tool returns an error, after simulation behavior is unexpected,
        or after execute_script / reload_script fails. Helps diagnose physics warnings,
        collision issues, and script errors that are not surfaced in tool responses.

        Args:
            clear: Clear the log buffer after reading. Default True.
            count: Maximum number of log entries to return.
        """
        try:
            conn = get_connection()
            result = conn.send_command("simulation.get_logs", {"clear": clear, "count": count})
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    @mcp.tool("get_simulation_state")
    def get_simulation_state() -> str:
        """Get the current simulation state including timeline status (playing/stopped/paused),
        simulation time, and physics dt. Call this to verify the simulation is running before
        using step_simulation."""
        try:
            conn = get_connection()
            result = conn.send_command("simulation.get_state")
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    @mcp.tool("get_physics_state")
    def get_physics_state(prim_path: str) -> str:
        """Diagnostic tool: get physics state for a prim.

        Returns rigid body status, mass, velocities, kinematic flag, and collision info.
        Call this when:
        - Objects fall through the ground (check collision enabled)
        - Objects don't move when expected (check is_kinematic, mass)
        - Grasping fails (check collision on gripper fingers and target object)

        Args:
            prim_path: USD path to the prim to inspect.
        """
        try:
            conn = get_connection()
            result = conn.send_command("simulation.get_physics_state", {"prim_path": prim_path})
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    @mcp.tool("get_joint_config")
    def get_joint_config(prim_path: str) -> str:
        """Diagnostic tool: get joint drive configuration for a robot articulation.

        Returns stiffness, damping, limits, target vs actual positions, and position error
        for each joint. Call this when:
        - Joint drives are not tracking targets (check position_error)
        - Joints are oscillating or unstable (check stiffness/damping ratio)
        - Joints hit limits unexpectedly (check lower_limit/upper_limit)

        Args:
            prim_path: USD path to the robot articulation root.
        """
        try:
            conn = get_connection()
            result = conn.send_command("simulation.get_joint_config", {"prim_path": prim_path})
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    @mcp.tool("execute_script")
    def execute_script(code: str, cwd: Optional[str] = None) -> str:
        """Escape hatch: execute arbitrary Python code in Isaac Sim.

        PREFER named tools over this for: reading/setting joints (set_joint_positions,
        get_joint_positions), inspecting state (get_prim_info, get_physics_state,
        get_joint_config), stepping simulation (step_simulation), and checking logs
        (get_isaac_logs).

        USE this for: operations no named tool covers, such as creating Action Graphs,
        computing IK, setting up physics callbacks, or configuring advanced USD properties.

        For persistent controllers (>20 lines), write a .py file and load it with
        reload_script instead of pasting code here.

        Args:
            code: Python code to execute in the Isaac Sim context.
            cwd: Optional working directory to add to sys.path before execution.
        """
        try:
            conn = get_connection()
            params = {"code": code}
            if cwd is not None:
                params["cwd"] = cwd
            result = conn.send_command("simulation.execute_script", params)
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    @mcp.tool("reload_script")
    def reload_script(file_path: str, module_name: Optional[str] = None) -> str:
        """Load a Python controller or module into Isaac Sim from a file on disk.

        Use this instead of execute_script for persistent controllers, state machines,
        or any code longer than ~20 lines. Workflow:
          1. Write the controller as a .py file
          2. reload_script to load it into Isaac Sim
          3. step_simulation to debug the behavior
          4. Edit the file and reload_script again to iterate

        The file's directory is auto-added to sys.path.

        Args:
            file_path: Path to the Python file on disk.
            module_name: Optional module name to reload (e.g. 'my_controller').
        """
        try:
            conn = get_connection()
            params = {"file_path": file_path}
            if module_name is not None:
                params["module_name"] = module_name
            result = conn.send_command("simulation.reload_script", params)
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})
