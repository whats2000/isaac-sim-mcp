# Tool Instructions & Response Enhancements Design

**Date:** 2026-04-06

## Problem

AI clients using the Isaac Sim MCP server lack guidance on when to use which tool. The server `instructions` field is a single line with no workflow guidance. Tool docstrings describe *what* each tool does but not *when* or *why* to use it. This leads to:

1. **Overuse of `execute_script`** — AI writes raw Python for operations that named tools handle (reading joints, checking physics state, inspecting prims).
2. **Ignoring the debug loop** — AI uses `play_simulation` + `sleep` + `execute_script` instead of the purpose-built `step_simulation` with `observe_prims`/`observe_joints`.
3. **Missing diagnostic tools** — `get_joint_config`, `get_physics_state`, and `get_isaac_logs` are never called, so drive misconfigurations, physics issues, and console errors go undetected.
4. **MCP vs Script scope confusion** — AI tries to build real-time controllers through MCP tool calls instead of writing scripts and loading them via `reload_script`.
5. **Insufficient response data** — `create_object` doesn't return actual dimensions (USD default size * scale), forcing manual calculation. `create_robot` doesn't return joint info, requiring a follow-up call. `get_prim_info` doesn't return size for geometric prims.

## Approach

Enhance existing tool instructions and response data across three layers. No new tools.

## Changes

### 1. Server-level instructions (`isaac_mcp/server.py`)

Replace the one-line `instructions` string with a comprehensive guide covering:

**MCP scope vs Script/Action Graph scope:**
- MCP tools are for editor-level operations: scene setup, inspection, stepping, debugging, reading/writing joint state.
- Scripts and Action Graphs are for runtime-level operations: real-time control loops, IK solvers, state machines, physics callbacks.
- `reload_script` is the bridge: write a controller as a Python file, load it into Isaac Sim, then use `step_simulation` to debug it.

**Debug loop pattern:**
```
set_joint_positions → step_simulation (with observe) → get_joint_config → get_physics_state → adjust
```
Not: `play_simulation → sleep → execute_script`

**Tool priority:**
- Always use named tools before falling back to `execute_script`.
- `execute_script` is the escape hatch for operations no named tool covers.

**Diagnostic trio:**
- `get_joint_config` — when drives misbehave (wrong stiffness, position error, spinning joints).
- `get_physics_state` — when objects don't behave as expected (missing rigid body, wrong mass, no collision).
- `get_isaac_logs` — after any error or unexpected behavior.

**Replace `asset_creation_strategy` prompt** with the new instructions content (the prompt required explicit invocation and was rarely used).

### 2. Tool docstring enhancements (`isaac_mcp/tools/*.py`)

#### simulation.py

**`step_simulation`** — Add workflow guidance:
```
Step the simulation forward by N frames, then observe prim and joint states.

This is the primary tool for debugging robot behavior. Use it instead of
play_simulation + sleep + execute_script. The observe parameters let you
inspect positions, velocities, and joint states in a single call.

Typical debug loop:
  1. set_joint_positions to command the robot
  2. step_simulation with observe_prims and observe_joints to advance and read state
  3. get_joint_config if drives are not tracking correctly
  4. get_physics_state if objects are not behaving as expected
  5. Adjust and repeat
```

**`set_joint_positions`** (in robots.py, but simulation-adjacent) — Clarify units:
```
Set target joint positions on a robot via ArticulationAction.

Units: radians for revolute joints, meters for prismatic joints (e.g. gripper fingers).
Use get_robot_info to discover joint names, types, and limits first.
After calling this, use step_simulation to advance the simulation and observe the result.
```

**`get_joint_config`** — Add diagnostic guidance:
```
Diagnostic tool: get joint drive configuration for a robot.

Returns stiffness, damping, limits, target vs actual positions, and position error
for each joint. Call this when:
- Joint drives are not tracking targets (check position_error)
- Joints are oscillating or unstable (check stiffness/damping ratio)
- Joints hit limits unexpectedly (check lower_limit/upper_limit)
```

**`get_physics_state`** — Add diagnostic guidance:
```
Diagnostic tool: get physics state for a prim.

Returns rigid body status, mass, velocities, kinematic flag, and collision info.
Call this when:
- Objects fall through the ground (check collision enabled)
- Objects don't move when expected (check is_kinematic, mass)
- Grasping fails (check collision on gripper fingers and target object)
```

**`get_isaac_logs`** — Add diagnostic guidance:
```
Diagnostic tool: get recent warnings and errors from Isaac Sim console.

Call this after:
- Any tool returns an error
- Simulation behavior is unexpected
- execute_script or reload_script fails
```

**`execute_script`** — Strengthen escape-hatch framing:
```
Escape hatch: execute arbitrary Python code in Isaac Sim.

PREFER named tools over this for: reading/setting joints (set_joint_positions,
get_joint_positions), inspecting state (get_prim_info, get_physics_state,
get_joint_config), stepping simulation (step_simulation), and checking logs
(get_isaac_logs).

USE this for: operations no named tool covers, such as creating Action Graphs,
computing IK, setting up physics callbacks, or configuring advanced properties.

For persistent controllers, write a Python file and load it with reload_script
instead of pasting large code blocks here.
```

**`reload_script`** — Position as controller loading tool:
```
Load a Python controller or module into Isaac Sim from a file on disk.

Use this instead of execute_script for persistent controllers, state machines,
or any code longer than ~20 lines. Write the controller as a .py file, then:
  1. reload_script to load it into Isaac Sim
  2. step_simulation to debug the behavior
  3. Edit the file and reload_script again to iterate

The file's directory is auto-added to sys.path.
```

#### robots.py

**`get_robot_info`** — Note enriched response:
```
Get robot joint information including names, DOF count, joint types, and limits.

Call this after create_robot to understand the robot's kinematic structure.
Returns joint names ordered by DOF index, joint types (revolute/prismatic),
and joint limits (radians for revolute, meters for prismatic).
```

**`create_robot`** — Note enriched response:
```
Create a robot in the scene from the Isaac Sim asset library.

Supports fuzzy matching — e.g. "franka", "spot", "go1".
Call list_available_robots first to see available robots.
Requires create_physics_scene to be called first.

Returns the prim_path, robot_key, joint_names, and dof_count so you don't need
a follow-up get_robot_info call.
```

**`get_joint_positions`** — Add units note:
```
Read current joint positions from a robot.

Units: radians for revolute joints, meters for prismatic joints.
Joint order matches the joint_names from get_robot_info.
For a combined step-and-read, prefer step_simulation with observe_joints.
```

#### objects.py

**`create_object`** — Note enriched response:
```
Create a primitive object (Cube, Sphere, Cylinder, Cone, Capsule, Plane).

The scale parameter multiplies the primitive's default size (2.0 for Cube,
meaning a Cube with scale [0.5, 0.5, 0.5] is 1.0m on each side).

Returns prim_path plus actual_size [x, y, z] in meters and bounding_box
(min/max corners in world coordinates) so you can accurately place other
objects relative to this one (e.g. placing a cube on top of a table).
```

#### scene.py

**`get_prim_info`** — Note enriched response:
```
Get detailed information about a specific prim.

Returns type, world-space position, children, and — for geometric prims
(Cube, Sphere, Cylinder, etc.) — the actual_size in meters accounting
for scale and default primitive dimensions.
```

### 3. Extension response enhancements

#### `objects.create` handler (`handlers/objects.py`)

After creating the prim, compute and return actual dimensions:

```python
# After successful creation, compute actual size
actual_size, bbox = adapter.get_prim_actual_size(prim_path)
return {
    "status": "success",
    "message": f"Created {object_type}",
    "prim_path": prim_path,
    "actual_size": actual_size,        # [x, y, z] in meters
    "bounding_box": {
        "min": bbox[0],               # [x, y, z]
        "max": bbox[1],               # [x, y, z]
    },
}
```

#### `robots.create` handler (`handlers/robots.py`)

After creating the robot, fetch and return joint info:

```python
# After successful creation, get joint info
try:
    info = adapter.get_robot_joint_info(prim_path)
except Exception:
    info = {}
return {
    "status": "success",
    "message": f"Created {match['description']} robot",
    "prim_path": prim_path,
    "robot_key": match["key"],
    "joint_names": info.get("joint_names", []),
    "num_dof": info.get("num_dof", 0),
}
```

#### `robots.get_info` handler (`adapters/v5.py`)

Enhance `get_robot_joint_info` to include joint limits:

```python
return {
    "joint_names": [...],
    "num_dof": int,
    "joint_limits": [
        {
            "name": "panda_joint1",
            "type": "revolute",          # or "prismatic"
            "lower": -2.8973,
            "upper": 2.8973,
            "units": "radians",          # or "meters"
        },
        ...
    ],
}
```

This requires traversing the articulation's joints in the USD stage and reading `UsdPhysics.RevoluteJoint` / `UsdPhysics.PrismaticJoint` limit attributes.

#### `scene.get_prim_info` handler (`adapters/v5.py`)

Enhance `get_prim_info` to include actual_size for geometric prims:

```python
info = {
    "path": prim_path,
    "type": prim.GetTypeName(),
    "transform": transform,
    "children": children,
}
# Add actual_size for geometric prims
if prim.GetTypeName() in ("Cube", "Sphere", "Cylinder", "Cone", "Capsule"):
    actual_size, _ = self.get_prim_actual_size(prim_path)
    info["actual_size"] = actual_size
return info
```

#### New adapter helper: `get_prim_actual_size` (`adapters/v5.py` + `adapters/base.py`)

Add to `base.py` as abstract method, implement in `v5.py`:

```python
def get_prim_actual_size(self, prim_path: str) -> Tuple[List[float], Tuple[List[float], List[float]]]:
    """Return (actual_size, (bbox_min, bbox_max)) for a geometric prim."""
```

Implementation computes the axis-aligned bounding dimensions for each prim type:
- **Cube**: `size * scale` per axis (default size = 2.0)
- **Sphere**: `2 * radius * scale` per axis (default radius = 1.0)
- **Cylinder**: `[2*radius*sx, 2*radius*sy, height*sz]` (default radius = 1.0, height = 2.0)
- **Cone**: same as Cylinder
- **Capsule**: `[2*radius*sx, 2*radius*sy, (height+2*radius)*sz]` (default radius = 0.5, height = 1.0)

Bounding box is computed as `[position - actual_size/2, position + actual_size/2]`.

## Files to modify

| File | Changes |
|------|---------|
| `isaac_mcp/server.py` | Replace `instructions`, replace `asset_creation_strategy` prompt |
| `isaac_mcp/tools/simulation.py` | Docstrings for `step_simulation`, `get_joint_config`, `get_physics_state`, `get_isaac_logs`, `execute_script`, `reload_script` |
| `isaac_mcp/tools/robots.py` | Docstrings for `create_robot`, `get_robot_info`, `set_joint_positions`, `get_joint_positions` |
| `isaac_mcp/tools/objects.py` | Docstring for `create_object` |
| `isaac_mcp/tools/scene.py` | Docstring for `get_prim_info` |
| `isaac.sim.mcp_extension/.../handlers/objects.py` | Add actual_size + bounding_box to create response |
| `isaac.sim.mcp_extension/.../handlers/robots.py` | Add joint_names + num_dof to create response |
| `isaac.sim.mcp_extension/.../handlers/scene.py` | No handler change needed (adapter change flows through) |
| `isaac.sim.mcp_extension/.../adapters/base.py` | Add `get_prim_actual_size` abstract method |
| `isaac.sim.mcp_extension/.../adapters/v5.py` | Implement `get_prim_actual_size`, enhance `get_prim_info`, enhance `get_robot_joint_info` |

## Out of scope

- No new MCP tools (IK, gripper control, etc. belong in scripts)
- No changes to `step_simulation` handler behavior (only docstring)
- No changes to simulation lifecycle tools (`play`/`pause`/`stop`)
