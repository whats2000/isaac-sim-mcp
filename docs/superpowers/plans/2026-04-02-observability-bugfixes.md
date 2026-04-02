# Observability Bug Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 4 bugs discovered during observability testing (whats2000/isaac-sim-mcp#2): broken log retrieval, zero-velocity readings, static joint targets, and double-nested execute_script response.

**Architecture:** All fixes are in 2 files — `handlers/simulation.py` for Bugs 1 & 4, `adapters/v5.py` for Bugs 2 & 3. Fixes are independent and can be committed separately. The `step()` method in v5.py calls `get_physics_state()` and `get_joint_config()` internally, so Bugs 2 & 3 also fix the step-and-observe flow.

**Tech Stack:** Python, omni.log, omni.physx, UsdPhysics, Isaac Sim dynamic control interface

**Spec:** `docs/superpowers/specs/2026-04-02-observability-bugfixes-design.md`

---

### Task 1: Fix argument order in log handler (Bug 1 — Critical)

**Files:**
- Modify: `isaac.sim.mcp_extension/isaac_sim_mcp_extension/handlers/simulation.py:165`

- [ ] **Step 1: Fix the argument order**

In `simulation.py` line 165, swap the 2nd and 3rd arguments to `set_channel_enabled`:

```python
# Before:
logger.set_channel_enabled("*", omni.log.SettingBehavior.OVERRIDE, True)

# After:
logger.set_channel_enabled("*", True, omni.log.SettingBehavior.OVERRIDE)
```

- [ ] **Step 2: Verify via MCP**

Call the `get_isaac_logs` tool via the dev MCP server:
```
Tool: get_isaac_logs
```
Expected: returns `{"status": "success", "log_count": N, "logs": [...]}` instead of failing.

- [ ] **Step 3: Commit**

```bash
git add isaac.sim.mcp_extension/isaac_sim_mcp_extension/handlers/simulation.py
git commit -m "fix: correct argument order in set_channel_enabled (issue #2 bug 1)"
```

---

### Task 2: Fix execute_script double-nested response (Bug 4 — Minor)

**Files:**
- Modify: `isaac.sim.mcp_extension/isaac_sim_mcp_extension/handlers/simulation.py:95-96`

- [ ] **Step 1: Fix the response wrapping**

In `simulation.py` line 96, spread the adapter result instead of nesting it:

```python
# Before (line 91-98):
def execute_script(adapter: IsaacAdapterBase, code: Optional[str] = None, cwd: Optional[str] = None) -> Dict[str, Any]:
    try:
        if not code:
            return {"status": "error", "message": "code is required"}
        result = adapter.execute_script(code, cwd=cwd)
        return {"status": "success", "result": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# After:
def execute_script(adapter: IsaacAdapterBase, code: Optional[str] = None, cwd: Optional[str] = None) -> Dict[str, Any]:
    try:
        if not code:
            return {"status": "error", "message": "code is required"}
        result = adapter.execute_script(code, cwd=cwd)
        return {"status": "success", **result}
    except Exception as e:
        return {"status": "error", "message": str(e)}
```

Note: The adapter's `execute_script` already returns `{"status": "success", "message": ..., "stdout": ..., "stderr": ...}`. Spreading it will create a duplicate `status` key — the outer `"status": "success"` will be overridden by the adapter's identical value, which is fine. This matches the pattern used by `get_simulation_state`, `get_physics_state_handler`, and `get_joint_config_handler`.

- [ ] **Step 2: Also fix reload_script_handler which has the same pattern**

In `simulation.py` line 134, the same nesting issue exists:

```python
# Before (line 134):
        return {"status": "success", "result": result}

# After:
        return {"status": "success", **result}
```

- [ ] **Step 3: Verify via MCP**

Call the `execute_script` tool:
```
Tool: execute_script
code: "print('hello')"
```
Expected: response has `stdout` at top level: `{"status": "success", "message": "Script executed successfully", "stdout": "hello\n", "stderr": ""}` — not nested under `result`.

- [ ] **Step 4: Commit**

```bash
git add isaac.sim.mcp_extension/isaac_sim_mcp_extension/handlers/simulation.py
git commit -m "fix: flatten execute_script and reload_script response structure (issue #2 bug 4)"
```

---

### Task 3: Fix velocity data returning zeros (Bug 2 — Medium)

**Files:**
- Modify: `isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/v5.py:378-390`

- [ ] **Step 1: Replace velocity retrieval with PhysX velocity API**

In `v5.py`, replace lines 378-390 with dedicated PhysX velocity methods:

```python
        # Get velocities via PhysX if simulation is running
        try:
            import omni.physx
            physx_interface = omni.physx.get_physx_interface()
            linear_vel = physx_interface.get_rigidbody_linear_velocity(prim_path)
            angular_vel = physx_interface.get_rigidbody_angular_velocity(prim_path)
            result["linear_velocity"] = list(linear_vel) if linear_vel else [0.0, 0.0, 0.0]
            result["angular_velocity"] = list(angular_vel) if angular_vel else [0.0, 0.0, 0.0]
        except Exception:
            # Velocities not available when simulation isn't running
            if has_rb:
                result["linear_velocity"] = [0.0, 0.0, 0.0]
                result["angular_velocity"] = [0.0, 0.0, 0.0]
```

This removes the `get_rigidbody_transformation` call which was only used here for (broken) velocity extraction.

- [ ] **Step 2: Verify via MCP — set up test scene**

Create a physics scene and a falling cube:
```
Tool: create_physics_scene
Tool: create_object (type: "Cube", prim_path: "/World/FallingCube", position: [0, 0, 2])
Tool: play_simulation
Tool: step_simulation (num_steps: 10)
```

- [ ] **Step 3: Verify velocity readings**

```
Tool: get_physics_state (prim_path: "/World/FallingCube")
```
Expected: `linear_velocity` should show non-zero Z component (negative, due to gravity) — not `[0, 0, 0]`.

- [ ] **Step 4: Verify step-and-observe also works**

```
Tool: step_simulation (num_steps: 5, observe_prims: ["/World/FallingCube"])
```
Expected: `prim_states[0].linear_velocity` shows non-zero values (this calls `get_physics_state` internally).

- [ ] **Step 5: Commit**

```bash
git add isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/v5.py
git commit -m "fix: use PhysX velocity API for accurate runtime readings (issue #2 bug 2)"
```

---

### Task 4: Fix joint target showing static USD value (Bug 3 — High)

**Files:**
- Modify: `isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/v5.py:267-331`

- [ ] **Step 1: Retrieve runtime targets at the top of the method**

In `v5.py`, after `current_pos_list` (line 280), add runtime target retrieval. `SingleArticulation` is already imported and instantiated at line 269:

```python
        # Get runtime target positions (from applied actions, not USD defaults)
        runtime_targets = []
        try:
            applied_action = art.get_applied_action()
            if applied_action and applied_action.joint_positions is not None:
                runtime_targets = applied_action.joint_positions.tolist()
        except Exception:
            pass  # Fall back to USD values if articulation controller unavailable
```

- [ ] **Step 2: Update the drive config + position matching section to use runtime targets**

Replace the drive config + position matching section (lines 303-325) with:

```python
                # Get drive config
                for drive_type in ["angular", "linear"]:
                    drive_api = UsdPhysics.DriveAPI.Get(desc, drive_type)
                    if drive_api:
                        joint_data["drive_type"] = drive_type
                        stiffness_attr = drive_api.GetStiffnessAttr()
                        damping_attr = drive_api.GetDampingAttr()
                        target_attr = drive_api.GetTargetPositionAttr()
                        joint_data["stiffness"] = stiffness_attr.Get() if stiffness_attr else None
                        joint_data["damping"] = damping_attr.Get() if damping_attr else None
                        # USD default as fallback
                        joint_data["target_position"] = target_attr.Get() if target_attr else None
                        break

                # Match actual position from articulation if possible
                joint_name = desc.GetName()
                if joint_name in joint_names:
                    idx = joint_names.index(joint_name)
                    if idx < len(current_pos_list):
                        joint_data["actual_position"] = current_pos_list[idx]

                    # Override target_position with runtime value if available
                    if idx < len(runtime_targets):
                        joint_data["target_position"] = float(runtime_targets[idx])

                    # Calculate position_error using (possibly runtime) target
                    if joint_data.get("target_position") is not None and "actual_position" in joint_data:
                        joint_data["position_error"] = joint_data["target_position"] - joint_data["actual_position"]
```

- [ ] **Step 3: Verify via MCP — load robot and set targets**

```
Tool: create_physics_scene
Tool: list_available_robots
```
Pick a robot (e.g., Franka), then:
```
Tool: create_robot (robot_name: "franka", prim_path: "/World/Franka")
Tool: play_simulation
Tool: set_joint_positions (prim_path: "/World/Franka", positions: [0.5, -0.3, 0.2, -1.0, 0.1, 0.8, 0.4])
Tool: step_simulation (num_steps: 10)
```

- [ ] **Step 4: Verify target positions reflect runtime values**

```
Tool: get_joint_config (prim_path: "/World/Franka")
```
Expected: `target_position` for each joint should reflect the values set in Step 3 (e.g., 0.5, -0.3, etc.), not 0.0.
Expected: `position_error` should be the difference between `target_position` and `actual_position`.

- [ ] **Step 5: Verify step-and-observe joint flow**

```
Tool: step_simulation (num_steps: 5, observe_joints: ["/World/Franka"])
```
Expected: joint states reflect runtime targets in the observation data.

- [ ] **Step 6: Commit**

```bash
git add isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/v5.py
git commit -m "fix: read runtime joint targets from articulation controller (issue #2 bug 3)"
```

---

### Task 5: Run tests and final verification

**Files:**
- Test: `tests/test_handler_structure.py`

- [ ] **Step 1: Run existing structural tests**

```bash
cd /home/user/Documents/GitHub/isaac-sim-mcp && python -m pytest tests/test_handler_structure.py -v
```
Expected: all 3 tests pass (adapter base methods, v5 implementation, handler register functions).

- [ ] **Step 2: Run full test suite**

```bash
cd /home/user/Documents/GitHub/isaac-sim-mcp && python -m pytest tests/ -v
```
Expected: all tests pass. If any tests reference the old `result` nesting from `execute_script`, update them.

- [ ] **Step 3: End-to-end MCP verification**

Run a full workflow against the dev MCP server:
1. `get_isaac_logs` — confirms Bug 1 fix
2. `execute_script` with `code: "print('test')"` — confirms Bug 4 fix (flat response)
3. Create physics scene + falling cube + play + step + `get_physics_state` — confirms Bug 2 fix (non-zero velocity)
4. Create robot + play + set joint positions + step + `get_joint_config` — confirms Bug 3 fix (runtime targets)

- [ ] **Step 4: Commit any test fixes if needed**

```bash
git add tests/
git commit -m "test: update tests for bugfix response changes"
```
