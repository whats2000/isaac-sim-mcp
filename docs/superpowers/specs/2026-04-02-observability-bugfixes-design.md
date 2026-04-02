# Observability Bug Fixes Design

**Date:** 2026-04-02
**Issue:** whats2000/isaac-sim-mcp#2
**Scope:** 4 bug fixes discovered during observability testing

---

## Bug 1: Argument Order Error in Log Handler

**Severity:** Critical (blocks all log retrieval)
**File:** `isaac.sim.mcp_extension/isaac_sim_mcp_extension/handlers/simulation.py`, line 165
**Tool affected:** `get_isaac_logs`

### Problem

`set_channel_enabled()` receives arguments in wrong order. The `omni.log` API signature expects `(channel, enabled, setting_behavior)`, but the current code passes `(channel, setting_behavior, enabled)`:

```python
# Current (broken):
logger.set_channel_enabled("*", omni.log.SettingBehavior.OVERRIDE, True)
```

### Fix

Swap the 2nd and 3rd arguments:

```python
logger.set_channel_enabled("*", True, omni.log.SettingBehavior.OVERRIDE)
```

### Verification

Call `get_isaac_logs` via MCP after fix. Should return collected warning/error logs instead of failing.

---

## Bug 2: Velocity Data Returns Zeros

**Severity:** Medium
**File:** `isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/v5.py`, lines 378-390
**Tool affected:** `get_physics_state`

### Problem

`physx_interface.get_rigidbody_transformation(prim_path)` returns a transformation dict that does not contain `linear_velocity` or `angular_velocity` keys. The code uses `.get("linear_velocity", [0, 0, 0])` which silently falls back to zeros.

### Fix

Replace with dedicated PhysX velocity API methods:

```python
linear_vel = physx_interface.get_rigidbody_linear_velocity(prim_path)
angular_vel = physx_interface.get_rigidbody_angular_velocity(prim_path)
result["linear_velocity"] = list(linear_vel) if linear_vel else [0.0, 0.0, 0.0]
result["angular_velocity"] = list(angular_vel) if angular_vel else [0.0, 0.0, 0.0]
```

The existing `get_rigidbody_transformation` call at line 382 can be removed since it's only used for velocity extraction in this block. Position and rotation are already read from USD xform attributes earlier in the function.

### Verification

1. Create a physics scene with a falling object
2. Start simulation
3. Call `get_physics_state` on the falling object
4. Confirm `linear_velocity` shows non-zero values (gravity should produce downward velocity)

---

## Bug 3: Joint Target Shows Static USD Value

**Severity:** High (impacts debugging workflow)
**File:** `isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/v5.py`, lines 310-313
**Tool affected:** `get_joint_config`

### Problem

`DriveAPI.GetTargetPositionAttr().Get()` returns the authored USD default (typically 0.0), not the runtime target position set via `ArticulationAction`. This causes incorrect `position_error` calculations at line 323.

### Fix

After reading the USD default as a fallback, attempt to read the runtime target from the dynamic control interface:

```python
# Keep USD read as fallback
target_attr = drive_api.GetTargetPositionAttr()
joint_data["target_position"] = target_attr.Get() if target_attr else None

# Override with runtime target if articulation is active
try:
    import omni.isaac.dynamic_control as dc_mod
    dc = dc_mod.acquire_dynamic_control_interface()
    art_handle = dc.get_articulation(prim_path)
    if art_handle != dc.INVALID_HANDLE:
        dof_count = dc.get_articulation_dof_count(art_handle)
        targets = dc.get_articulation_dof_position_targets(art_handle)
        # Map joint name to DOF index and read runtime target
        ...
except Exception:
    pass  # Fall back to USD value
```

The exact DOF-to-joint mapping will be determined during implementation by inspecting the articulation's DOF names.

### Verification

1. Load a robot (e.g., Franka)
2. Start simulation
3. Set joint targets via `set_joint_positions`
4. Call `get_joint_config` and confirm `target_position` reflects the runtime value, not 0.0
5. Confirm `position_error` is calculated correctly

---

## Bug 4: execute_script Double-Nested Response

**Severity:** Minor (response structure inconsistency)
**File:** `isaac.sim.mcp_extension/isaac_sim_mcp_extension/handlers/simulation.py`, lines 95-96
**Tool affected:** `execute_script`

### Problem

The adapter's `execute_script` already returns `{"status": "success", "message": ..., "stdout": ..., "stderr": ...}`. The handler wraps this inside another dict: `{"status": "success", "result": {"status": "success", ...}}`, creating redundant nesting.

All other handlers (e.g., `get_physics_state_handler`, `get_simulation_state`) spread the adapter result with `**result`.

### Fix

```python
# Before:
return {"status": "success", "result": result}

# After:
return {"status": "success", **result}
```

### Verification

Call `execute_script` with a simple script (e.g., `print("hello")`) and verify the response has `stdout` at the top level, not nested under `result`.

---

## Implementation Priority

1. **Bug 1** — one-line fix, maximum impact
2. **Bug 4** — one-line fix, consistency improvement
3. **Bug 3** — moderate complexity, high debugging impact
4. **Bug 2** — moderate complexity, runtime velocity accuracy

## Testing Strategy

All fixes will be verified against the running dev MCP server using the corresponding MCP tools. No unit test changes expected for Bugs 1 and 4. Bugs 2 and 3 may require updates to existing structural tests if the response shape changes.
