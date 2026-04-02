# Observability & Workflow Improvements Design

**Issue:** [#1 — MCP Developer Experience: Observability & Workflow Improvements](https://github.com/whats2000/isaac-sim-mcp/issues/1)
**Date:** 2026-04-02

## Problem

Developers using Isaac Sim MCP tools can push code into simulations via `execute_script`, but lack visibility into runtime behavior. Debugging is essentially blind — no access to print output, physics state, joint configurations, or simulation timeline. Common workflows like reloading modified scripts require manual boilerplate.

## Approach

**Approach A (Minimal New Tools):** Add 4 new tools and enhance 2 existing ones. Keeps tool surface small (35 -> 39 tools) to minimize impact on model context performance.

## Changes

### Enhanced Existing Tools

#### 1. `execute_script` — add `cwd` param + stdout capture (Issues #1, #3)

**MCP tool signature:**
```python
execute_script(code: str, cwd: str = None) -> str
```

**Changes:**
- New `cwd` parameter: if provided, auto-adds to `sys.path` before execution
- Redirect `sys.stdout` and `sys.stderr` via `io.StringIO` during `exec()`, capture output
- Return captured output in response

**Response shape:**
```json
{
  "status": "success",
  "message": "Script executed successfully",
  "stdout": "captured print output...",
  "stderr": ""
}
```

**Files touched:**
- `isaac_mcp/tools/simulation.py` — add `cwd` param to tool definition
- `isaac.sim.mcp_extension/.../handlers/simulation.py` — pass `cwd` to adapter
- `isaac.sim.mcp_extension/.../adapters/base.py` — update abstract method signature
- `isaac.sim.mcp_extension/.../adapters/v5.py` — implement sys.path insertion + stdout/stderr capture

#### 2. `step_simulation` — add observe params (Issue #8)

**MCP tool signature:**
```python
step_simulation(num_steps: int = 1, observe_prims: list[str] = None, observe_joints: list[str] = None) -> str
```

**Changes:**
- New `observe_prims`: list of prim paths to snapshot after stepping (returns transform + physics state)
- New `observe_joints`: list of articulation prim paths to snapshot (returns joint positions)
- Steps N frames first, then collects observations

**Response shape:**
```json
{
  "status": "success",
  "message": "Stepped 10 frames",
  "prim_states": [
    {
      "prim_path": "/World/Cube",
      "position": [0, 0, 1],
      "rotation": [0, 0, 0, 1],
      "linear_velocity": [0, 0, -0.1],
      "angular_velocity": [0, 0, 0]
    }
  ],
  "joint_states": [
    {
      "prim_path": "/World/Robot",
      "joints": {"joint1": 0.5, "joint2": -0.3}
    }
  ]
}
```

**Files touched:**
- `isaac_mcp/tools/simulation.py` — add optional params
- `isaac.sim.mcp_extension/.../handlers/simulation.py` — pass to adapter
- `isaac.sim.mcp_extension/.../adapters/base.py` — update abstract method
- `isaac.sim.mcp_extension/.../adapters/v5.py` — implement observe after step

### New Tools

#### 3. `get_simulation_state` (Issue #4)

**MCP tool signature:**
```python
get_simulation_state() -> str
```

No parameters. Returns current timeline and physics state.

**Response shape:**
```json
{
  "status": "success",
  "timeline_state": "playing",
  "current_time": 2.35,
  "physics_dt": 0.01667,
  "physics_step_count": 141
}
```

**Implementation:**
- Use `omni.timeline.get_timeline_interface()` for state/time
- Use physics scene prim for dt
- Step count from timeline current frame or physics API

**Files touched:**
- `isaac_mcp/tools/simulation.py` — new tool definition
- `isaac.sim.mcp_extension/.../handlers/simulation.py` — new handler
- `isaac.sim.mcp_extension/.../adapters/base.py` — new abstract method
- `isaac.sim.mcp_extension/.../adapters/v5.py` — implementation

#### 4. `get_physics_state(prim_path)` (Issue #5)

**MCP tool signature:**
```python
get_physics_state(prim_path: str) -> str
```

**Response shape:**
```json
{
  "status": "success",
  "prim_path": "/World/Cube",
  "has_rigid_body": true,
  "mass": 1.0,
  "linear_velocity": [0, 0, -9.8],
  "angular_velocity": [0, 0, 0],
  "is_kinematic": false,
  "collision_enabled": true,
  "contact_count": 1,
  "contacts": [
    {
      "other_prim": "/World/Ground",
      "normal": [0, 0, 1],
      "impulse": 9.8
    }
  ]
}
```

**Implementation:**
- `UsdPhysics.RigidBodyAPI` for rigid body check + kinematic flag
- `UsdPhysics.MassAPI` for mass
- `PhysxSchema.PhysxRigidBodyAPI` or simulation view for velocities
- Contact report API for contacts (capped at 20)
- Graceful handling: if prim has no rigid body, return `has_rigid_body: false` with available info only

**Files touched:**
- `isaac_mcp/tools/simulation.py` — new tool
- `isaac.sim.mcp_extension/.../handlers/simulation.py` — new handler
- `isaac.sim.mcp_extension/.../adapters/base.py` — new abstract method
- `isaac.sim.mcp_extension/.../adapters/v5.py` — implementation

#### 5. `get_joint_config(prim_path)` (Issue #6)

**MCP tool signature:**
```python
get_joint_config(prim_path: str) -> str
```

**Response shape:**
```json
{
  "status": "success",
  "prim_path": "/World/Robot",
  "joint_count": 6,
  "joints": [
    {
      "name": "joint_lift",
      "type": "prismatic",
      "drive_type": "force",
      "stiffness": 1000.0,
      "damping": 100.0,
      "lower_limit": 0.0,
      "upper_limit": 1.1,
      "target_position": 0.5,
      "actual_position": 0.48,
      "position_error": 0.02
    }
  ]
}
```

**Implementation:**
- Get articulation via existing adapter pattern (same as `get_robot_info`)
- `UsdPhysics.DriveAPI` for stiffness, damping, target
- `UsdPhysics.RevoluteJoint` / `PrismaticJoint` for limits and type
- Current position from articulation controller
- Compute error as `target - actual`

**Files touched:**
- `isaac_mcp/tools/simulation.py` — new tool
- `isaac.sim.mcp_extension/.../handlers/simulation.py` — new handler
- `isaac.sim.mcp_extension/.../adapters/base.py` — new abstract method
- `isaac.sim.mcp_extension/.../adapters/v5.py` — implementation

#### 6. `reload_script(file_path, module_name)` (Issues #2, #7)

**MCP tool signature:**
```python
reload_script(file_path: str, module_name: str = None) -> str
```

**Behavior:**
- Always adds `os.path.dirname(file_path)` to `sys.path` if not present
- If `module_name` provided: `importlib.reload(sys.modules[module_name])` — or import if not yet loaded
- If only `file_path`: read and execute file contents (hot-patch, like Omniverse "Run")
- Captures stdout/stderr during execution

**Response shape:**
```json
{
  "status": "success",
  "message": "Module 'my_controller' reloaded successfully",
  "stdout": "",
  "stderr": ""
}
```

**Files touched:**
- `isaac_mcp/tools/simulation.py` — new tool
- `isaac.sim.mcp_extension/.../handlers/simulation.py` — new handler
- `isaac.sim.mcp_extension/.../adapters/base.py` — new abstract method
- `isaac.sim.mcp_extension/.../adapters/v5.py` — implementation with importlib + sys.path logic

## Testing Strategy

All features will be tested against a live Isaac Sim instance. Test sequence:

1. **`get_simulation_state`** — verify timeline state before/after play/pause
2. **`execute_script` with `cwd`** — run script that imports from a local module, verify stdout capture
3. **`reload_script`** — create a script, execute it, modify it, reload, verify new behavior
4. **`get_physics_state`** — create a cube with rigid body, step simulation, check velocities
5. **`get_joint_config`** — create a robot, inspect joint drives, verify stiffness/damping/positions
6. **`step_simulation` with observe** — step N frames with prim/joint observation, verify snapshots
7. **Integration test** — full workflow: create robot, play, step+observe, inspect joints, reload controller

## Architecture Notes

- All new code follows existing patterns: tool -> handler -> adapter
- Adapter abstract methods ensure version isolation for future Isaac Sim versions
- Response shapes follow existing `{status, message, ...}` convention
- Error handling follows existing try-catch -> JSON error pattern
- No new dependencies required
