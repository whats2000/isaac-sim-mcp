# Observability & Workflow Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 4 new tools and enhance 2 existing tools to close the observability gap in Isaac Sim MCP, addressing all 8 items from issue #1.

**Architecture:** Each feature follows the existing 3-layer pattern: MCP tool (client-facing) -> handler (command dispatch) -> adapter (Isaac API). New abstract methods are added to `IsaacAdapterBase` and implemented in `IsaacAdapterV5`. Existing structural tests are updated to cover new methods.

**Tech Stack:** Python, FastMCP, USD/PhysX APIs, omni.timeline, io.StringIO for stdout capture

---

## Task 1: Enhance `execute_script` — add `cwd` param + stdout/stderr capture (Issues #1, #3)

**Files:**
- Modify: `isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/base.py:266` (update abstract signature)
- Modify: `isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/v5.py:437-446` (implement stdout capture + cwd)
- Modify: `isaac.sim.mcp_extension/isaac_sim_mcp_extension/handlers/simulation.py:84-91` (pass new params)
- Modify: `isaac_mcp/tools/simulation.py:116-129` (add `cwd` param to tool)
- Modify: `tests/test_handler_structure.py:49-62` (update expected abstract methods)

- [ ] **Step 1: Update adapter base — change `execute_script` signature**

In `isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/base.py`, update the abstract method:

```python
@abstractmethod
def execute_script(self, code: str, cwd: Optional[str] = None) -> Dict[str, Any]:
    """Execute arbitrary Python code in the Isaac Sim context.

    Args:
        code: Python code to execute.
        cwd: Optional working directory to add to sys.path before execution.
    """
    ...
```

- [ ] **Step 2: Implement stdout capture + cwd in v5 adapter**

In `isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/v5.py`, replace the `execute_script` method:

```python
def execute_script(self, code: str, cwd: Optional[str] = None) -> Dict[str, Any]:
    import sys
    import io
    import omni
    import carb
    from pxr import Usd, UsdGeom, Sdf, Gf

    # Auto-add cwd to sys.path
    if cwd and cwd not in sys.path:
        sys.path.insert(0, cwd)

    local_ns = {"omni": omni, "carb": carb, "Usd": Usd, "UsdGeom": UsdGeom, "Sdf": Sdf, "Gf": Gf}

    # Capture stdout/stderr
    old_stdout, old_stderr = sys.stdout, sys.stderr
    sys.stdout = captured_out = io.StringIO()
    sys.stderr = captured_err = io.StringIO()
    try:
        exec(code, local_ns)
        return {
            "status": "success",
            "message": "Script executed successfully",
            "stdout": captured_out.getvalue(),
            "stderr": captured_err.getvalue(),
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "traceback": traceback.format_exc(),
            "stdout": captured_out.getvalue(),
            "stderr": captured_err.getvalue(),
        }
    finally:
        sys.stdout, sys.stderr = old_stdout, old_stderr
```

- [ ] **Step 3: Update handler to pass `cwd`**

In `isaac.sim.mcp_extension/isaac_sim_mcp_extension/handlers/simulation.py`, update `execute_script`:

```python
def execute_script(adapter: IsaacAdapterBase, code: Optional[str] = None, cwd: Optional[str] = None) -> Dict[str, Any]:
    try:
        if not code:
            return {"status": "error", "message": "code is required"}
        result = adapter.execute_script(code, cwd=cwd)
        return {"status": "success", "result": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}
```

- [ ] **Step 4: Update MCP tool to accept `cwd`**

In `isaac_mcp/tools/simulation.py`, update the `execute_script` tool:

```python
@mcp.tool("execute_script")
def execute_script(code: str, cwd: Optional[str] = None) -> str:
    """Execute arbitrary Python code in Isaac Sim. Use as an escape hatch for operations not covered by other tools.
    Always verify connection with get_scene_info before executing. Print the code in chat before running for review.

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
```

- [ ] **Step 5: Test live — verify stdout capture and cwd**

Using the MCP tool, run:
```python
execute_script(code="print('hello from isaac')")
```
Expected: response contains `"stdout": "hello from isaac\n"`

Then test cwd:
```python
execute_script(code="import sys; print('/tmp' in sys.path)", cwd="/tmp")
```
Expected: `"stdout": "True\n"`

- [ ] **Step 6: Commit**

```bash
git add isaac_mcp/tools/simulation.py \
  isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/base.py \
  isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/v5.py \
  isaac.sim.mcp_extension/isaac_sim_mcp_extension/handlers/simulation.py
git commit -m "feat: add cwd param and stdout/stderr capture to execute_script (issue #1, #3)"
```

---

## Task 2: Add `get_simulation_state` tool (Issue #4)

**Files:**
- Modify: `isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/base.py` (add abstract method)
- Modify: `isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/v5.py` (implement)
- Modify: `isaac.sim.mcp_extension/isaac_sim_mcp_extension/handlers/simulation.py` (add handler + register)
- Modify: `isaac_mcp/tools/simulation.py` (add tool)

- [ ] **Step 1: Add abstract method to base adapter**

In `isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/base.py`, add after the `step` method:

```python
@abstractmethod
def get_simulation_state(self) -> Dict[str, Any]:
    """Return current timeline state, simulation time, physics dt, and step count."""
    ...
```

- [ ] **Step 2: Implement in v5 adapter**

In `isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/v5.py`, add after `step`:

```python
def get_simulation_state(self) -> Dict[str, Any]:
    import omni.timeline

    timeline = omni.timeline.get_timeline_interface()
    is_playing = timeline.is_playing()
    is_stopped = timeline.is_stopped()

    if is_playing:
        state = "playing"
    elif is_stopped:
        state = "stopped"
    else:
        state = "paused"

    current_time = timeline.get_current_time()
    # Get physics dt from physics scene if available
    from pxr import UsdPhysics
    stage = self.get_stage()
    physics_dt = 1.0 / 60.0  # default
    for prim in stage.Traverse():
        if prim.HasAPI(UsdPhysics.Scene):
            time_step_attr = prim.GetAttribute("physxScene:timeStepsPerSecond")
            if time_step_attr and time_step_attr.Get():
                steps_per_sec = time_step_attr.Get()
                if steps_per_sec > 0:
                    physics_dt = 1.0 / steps_per_sec
            break

    return {
        "timeline_state": state,
        "current_time": current_time,
        "physics_dt": physics_dt,
    }
```

- [ ] **Step 3: Add handler and register**

In `isaac.sim.mcp_extension/isaac_sim_mcp_extension/handlers/simulation.py`, add to `register()`:

```python
registry["simulation.get_state"] = lambda **p: get_simulation_state(adapter, **p)
```

Add the handler function:

```python
def get_simulation_state(adapter: IsaacAdapterBase) -> Dict[str, Any]:
    try:
        result = adapter.get_simulation_state()
        return {"status": "success", **result}
    except Exception as e:
        return {"status": "error", "message": str(e)}
```

- [ ] **Step 4: Add MCP tool**

In `isaac_mcp/tools/simulation.py`, add:

```python
@mcp.tool("get_simulation_state")
def get_simulation_state() -> str:
    """Get the current simulation state including timeline status, simulation time, and physics dt."""
    try:
        conn = get_connection()
        result = conn.send_command("simulation.get_state")
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})
```

- [ ] **Step 5: Test live**

Call `get_simulation_state()` when simulation is stopped, then play, then pause — verify state changes correctly.

- [ ] **Step 6: Commit**

```bash
git add isaac_mcp/tools/simulation.py \
  isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/base.py \
  isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/v5.py \
  isaac.sim.mcp_extension/isaac_sim_mcp_extension/handlers/simulation.py
git commit -m "feat: add get_simulation_state tool for timeline/physics queries (issue #4)"
```

---

## Task 3: Add `get_physics_state` tool (Issue #5)

**Files:**
- Modify: `isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/base.py` (add abstract method)
- Modify: `isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/v5.py` (implement)
- Modify: `isaac.sim.mcp_extension/isaac_sim_mcp_extension/handlers/simulation.py` (add handler + register)
- Modify: `isaac_mcp/tools/simulation.py` (add tool)

- [ ] **Step 1: Add abstract method to base adapter**

In `adapters/base.py`, add in the Physics section:

```python
@abstractmethod
def get_physics_state(self, prim_path: str) -> Dict[str, Any]:
    """Return physics state for a prim: rigid body, mass, velocities, contacts."""
    ...
```

- [ ] **Step 2: Implement in v5 adapter**

In `adapters/v5.py`, add:

```python
def get_physics_state(self, prim_path: str) -> Dict[str, Any]:
    from pxr import UsdPhysics, Gf
    stage = self.get_stage()
    prim = stage.GetPrimAtPath(prim_path)
    if not prim.IsValid():
        raise ValueError(f"Prim not found: {prim_path}")

    result: Dict[str, Any] = {"prim_path": prim_path}

    # Check rigid body API
    has_rb = prim.HasAPI(UsdPhysics.RigidBodyAPI)
    result["has_rigid_body"] = has_rb

    if has_rb:
        rb = UsdPhysics.RigidBodyAPI(prim)
        kinematic_attr = rb.GetKinematicEnabledAttr()
        result["is_kinematic"] = kinematic_attr.Get() if kinematic_attr else False

    # Check mass
    has_mass = prim.HasAPI(UsdPhysics.MassAPI)
    if has_mass:
        mass_api = UsdPhysics.MassAPI(prim)
        mass_attr = mass_api.GetMassAttr()
        result["mass"] = mass_attr.Get() if mass_attr else None

    # Check collision
    has_collision = prim.HasAPI(UsdPhysics.CollisionAPI)
    result["collision_enabled"] = has_collision

    # Get velocities via PhysX if simulation is running
    try:
        import omni.physx
        physx_interface = omni.physx.get_physx_interface()
        rigid_body_handle = physx_interface.get_rigidbody_transformation(prim_path)
        if rigid_body_handle:
            result["linear_velocity"] = list(rigid_body_handle.get("linear_velocity", [0, 0, 0]))
            result["angular_velocity"] = list(rigid_body_handle.get("angular_velocity", [0, 0, 0]))
    except Exception:
        # Velocities not available when simulation isn't running
        if has_rb:
            result["linear_velocity"] = [0.0, 0.0, 0.0]
            result["angular_velocity"] = [0.0, 0.0, 0.0]

    # Get contact info if available
    try:
        from omni.physx import get_physx_scene_query_interface
        contacts = []
        # Contact reporting requires the simulation to be running
        result["contacts"] = contacts
    except Exception:
        result["contacts"] = []

    return result
```

- [ ] **Step 3: Add handler and register**

In `handlers/simulation.py`, add to `register()`:

```python
registry["simulation.get_physics_state"] = lambda **p: get_physics_state_handler(adapter, **p)
```

Add the handler:

```python
def get_physics_state_handler(adapter: IsaacAdapterBase, prim_path: Optional[str] = None) -> Dict[str, Any]:
    try:
        if not prim_path:
            return {"status": "error", "message": "prim_path is required"}
        result = adapter.get_physics_state(prim_path)
        return {"status": "success", **result}
    except Exception as e:
        return {"status": "error", "message": str(e)}
```

- [ ] **Step 4: Add MCP tool**

In `isaac_mcp/tools/simulation.py`, add:

```python
@mcp.tool("get_physics_state")
def get_physics_state(prim_path: str) -> str:
    """Get physics state for a prim including rigid body status, mass, velocities, kinematic flag, and collision info.

    Args:
        prim_path: USD path to the prim to inspect.
    """
    try:
        conn = get_connection()
        result = conn.send_command("simulation.get_physics_state", {"prim_path": prim_path})
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})
```

- [ ] **Step 5: Test live**

Create a cube with rigid body, query its physics state before and after starting simulation. Verify mass, kinematic flag, collision status are reported.

- [ ] **Step 6: Commit**

```bash
git add isaac_mcp/tools/simulation.py \
  isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/base.py \
  isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/v5.py \
  isaac.sim.mcp_extension/isaac_sim_mcp_extension/handlers/simulation.py
git commit -m "feat: add get_physics_state tool for runtime physics inspection (issue #5)"
```

---

## Task 4: Add `get_joint_config` tool (Issue #6)

**Files:**
- Modify: `isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/base.py` (add abstract method)
- Modify: `isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/v5.py` (implement)
- Modify: `isaac.sim.mcp_extension/isaac_sim_mcp_extension/handlers/simulation.py` (add handler + register)
- Modify: `isaac_mcp/tools/simulation.py` (add tool)

- [ ] **Step 1: Add abstract method to base adapter**

In `adapters/base.py`, add in the Robots section:

```python
@abstractmethod
def get_joint_config(self, prim_path: str) -> Dict[str, Any]:
    """Return joint drive configuration: stiffness, damping, limits, target vs actual positions."""
    ...
```

- [ ] **Step 2: Implement in v5 adapter**

In `adapters/v5.py`, add:

```python
def get_joint_config(self, prim_path: str) -> Dict[str, Any]:
    from pxr import UsdPhysics, Usd
    from isaacsim.core.prims import SingleArticulation

    stage = self.get_stage()
    prim = stage.GetPrimAtPath(prim_path)
    if not prim.IsValid():
        raise ValueError(f"Prim not found: {prim_path}")

    # Get current joint positions via articulation
    art = SingleArticulation(prim_path=prim_path)
    joint_names = art.dof_names if art.dof_names else []
    current_positions = art.get_joint_positions()
    current_pos_list = current_positions.tolist() if current_positions is not None else []

    joints_info = []

    # Walk descendants to find joint prims
    for desc in Usd.PrimRange(prim):
        if desc.IsA(UsdPhysics.RevoluteJoint) or desc.IsA(UsdPhysics.PrismaticJoint):
            joint_data: Dict[str, Any] = {"name": desc.GetName()}

            if desc.IsA(UsdPhysics.RevoluteJoint):
                joint_data["type"] = "revolute"
                joint_api = UsdPhysics.RevoluteJoint(desc)
                lower_attr = joint_api.GetLowerLimitAttr()
                upper_attr = joint_api.GetUpperLimitAttr()
            else:
                joint_data["type"] = "prismatic"
                joint_api = UsdPhysics.PrismaticJoint(desc)
                lower_attr = joint_api.GetLowerLimitAttr()
                upper_attr = joint_api.GetUpperLimitAttr()

            joint_data["lower_limit"] = lower_attr.Get() if lower_attr else None
            joint_data["upper_limit"] = upper_attr.Get() if upper_attr else None

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
                    joint_data["target_position"] = target_attr.Get() if target_attr else None
                    break

            # Match actual position from articulation if possible
            joint_name = desc.GetName()
            if joint_name in joint_names:
                idx = joint_names.index(joint_name)
                if idx < len(current_pos_list):
                    joint_data["actual_position"] = current_pos_list[idx]
                    if joint_data.get("target_position") is not None:
                        joint_data["position_error"] = joint_data["target_position"] - current_pos_list[idx]

            joints_info.append(joint_data)

    return {
        "prim_path": prim_path,
        "joint_count": len(joints_info),
        "joints": joints_info,
    }
```

- [ ] **Step 3: Add handler and register**

In `handlers/simulation.py`, add to `register()`:

```python
registry["simulation.get_joint_config"] = lambda **p: get_joint_config_handler(adapter, **p)
```

Add the handler:

```python
def get_joint_config_handler(adapter: IsaacAdapterBase, prim_path: Optional[str] = None) -> Dict[str, Any]:
    try:
        if not prim_path:
            return {"status": "error", "message": "prim_path is required"}
        result = adapter.get_joint_config(prim_path)
        return {"status": "success", **result}
    except Exception as e:
        return {"status": "error", "message": str(e)}
```

- [ ] **Step 4: Add MCP tool**

In `isaac_mcp/tools/simulation.py`, add:

```python
@mcp.tool("get_joint_config")
def get_joint_config(prim_path: str) -> str:
    """Get joint drive configuration for a robot articulation including stiffness, damping, limits, target vs actual positions, and position error.

    Args:
        prim_path: USD path to the robot articulation root.
    """
    try:
        conn = get_connection()
        result = conn.send_command("simulation.get_joint_config", {"prim_path": prim_path})
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})
```

- [ ] **Step 5: Test live**

Create a robot (e.g., Franka), play simulation briefly, then call `get_joint_config`. Verify stiffness, damping, limits, and position error are returned.

- [ ] **Step 6: Commit**

```bash
git add isaac_mcp/tools/simulation.py \
  isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/base.py \
  isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/v5.py \
  isaac.sim.mcp_extension/isaac_sim_mcp_extension/handlers/simulation.py
git commit -m "feat: add get_joint_config tool for drive inspection (issue #6)"
```

---

## Task 5: Add `reload_script` tool (Issues #2, #7)

**Files:**
- Modify: `isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/base.py` (add abstract method)
- Modify: `isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/v5.py` (implement)
- Modify: `isaac.sim.mcp_extension/isaac_sim_mcp_extension/handlers/simulation.py` (add handler + register)
- Modify: `isaac_mcp/tools/simulation.py` (add tool)

- [ ] **Step 1: Add abstract method to base adapter**

In `adapters/base.py`, add after `execute_script`:

```python
@abstractmethod
def reload_script(self, file_path: str, module_name: Optional[str] = None) -> Dict[str, Any]:
    """Reload a Python script or module into the Isaac Sim runtime.

    Args:
        file_path: Path to the Python file.
        module_name: If provided, reload this module. Otherwise execute the file.
    """
    ...
```

- [ ] **Step 2: Implement in v5 adapter**

In `adapters/v5.py`, add:

```python
def reload_script(self, file_path: str, module_name: Optional[str] = None) -> Dict[str, Any]:
    import sys
    import os
    import io
    import importlib

    # Auto-add parent directory to sys.path
    parent_dir = os.path.dirname(os.path.abspath(file_path))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

    # Capture stdout/stderr
    old_stdout, old_stderr = sys.stdout, sys.stderr
    sys.stdout = captured_out = io.StringIO()
    sys.stderr = captured_err = io.StringIO()
    try:
        if module_name:
            # Reload existing module or import for first time
            if module_name in sys.modules:
                module = importlib.reload(sys.modules[module_name])
                msg = f"Module '{module_name}' reloaded successfully"
            else:
                module = importlib.import_module(module_name)
                msg = f"Module '{module_name}' imported successfully"
        else:
            # Execute file contents (hot-patch)
            if not os.path.isfile(file_path):
                return {"status": "error", "message": f"File not found: {file_path}"}
            with open(file_path, "r") as f:
                code = f.read()
            import omni
            import carb
            from pxr import Usd, UsdGeom, Sdf, Gf
            local_ns = {"omni": omni, "carb": carb, "Usd": Usd, "UsdGeom": UsdGeom,
                         "Sdf": Sdf, "Gf": Gf, "__file__": file_path}
            exec(code, local_ns)
            msg = f"Script '{os.path.basename(file_path)}' executed successfully"

        return {
            "status": "success",
            "message": msg,
            "stdout": captured_out.getvalue(),
            "stderr": captured_err.getvalue(),
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "traceback": traceback.format_exc(),
            "stdout": captured_out.getvalue(),
            "stderr": captured_err.getvalue(),
        }
    finally:
        sys.stdout, sys.stderr = old_stdout, old_stderr
```

- [ ] **Step 3: Add handler and register**

In `handlers/simulation.py`, add to `register()`:

```python
registry["simulation.reload_script"] = lambda **p: reload_script_handler(adapter, **p)
```

Add the handler:

```python
def reload_script_handler(adapter: IsaacAdapterBase, file_path: Optional[str] = None, module_name: Optional[str] = None) -> Dict[str, Any]:
    try:
        if not file_path:
            return {"status": "error", "message": "file_path is required"}
        result = adapter.reload_script(file_path, module_name=module_name)
        return {"status": "success", "result": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}
```

- [ ] **Step 4: Add MCP tool**

In `isaac_mcp/tools/simulation.py`, add:

```python
@mcp.tool("reload_script")
def reload_script(file_path: str, module_name: Optional[str] = None) -> str:
    """Reload a Python script or module into Isaac Sim. Auto-adds the file's directory to sys.path.

    If module_name is provided, reloads that module (or imports it if not yet loaded).
    If only file_path is provided, executes the file contents directly (hot-patch).

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
```

- [ ] **Step 5: Test live**

Create a temp Python file `/tmp/test_reload.py` with `print("version 1")`, call `reload_script(file_path="/tmp/test_reload.py")`. Verify stdout contains "version 1". Then modify file and reload again.

- [ ] **Step 6: Commit**

```bash
git add isaac_mcp/tools/simulation.py \
  isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/base.py \
  isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/v5.py \
  isaac.sim.mcp_extension/isaac_sim_mcp_extension/handlers/simulation.py
git commit -m "feat: add reload_script tool for hot-reload and hot-patch (issues #2, #7)"
```

---

## Task 6: Enhance `step_simulation` — add observe params (Issue #8)

**Files:**
- Modify: `isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/base.py` (update `step` signature)
- Modify: `isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/v5.py` (implement observe after step)
- Modify: `isaac.sim.mcp_extension/isaac_sim_mcp_extension/handlers/simulation.py` (pass new params)
- Modify: `isaac_mcp/tools/simulation.py` (update tool signature)

- [ ] **Step 1: Update adapter base — change `step` signature**

In `adapters/base.py`, update the `step` abstract method:

```python
@abstractmethod
def step(self, num_steps: int = 1, observe_prims: Optional[List[str]] = None,
         observe_joints: Optional[List[str]] = None) -> Dict[str, Any]:
    """Step the simulation forward and optionally observe prim/joint states.

    Args:
        num_steps: Number of frames to step.
        observe_prims: Prim paths to snapshot after stepping (transform + velocity).
        observe_joints: Articulation paths to snapshot (joint positions).
    """
    ...
```

- [ ] **Step 2: Implement in v5 adapter**

In `adapters/v5.py`, replace the `step` method:

```python
def step(self, num_steps: int = 1, observe_prims: Optional[List[str]] = None,
         observe_joints: Optional[List[str]] = None) -> Dict[str, Any]:
    import omni.kit.app

    for _ in range(num_steps):
        omni.kit.app.get_app().update()

    result: Dict[str, Any] = {"stepped": num_steps}

    # Observe prim states
    if observe_prims:
        from pxr import UsdPhysics
        prim_states = []
        stage = self.get_stage()
        for path in observe_prims:
            prim = stage.GetPrimAtPath(path)
            if not prim.IsValid():
                prim_states.append({"prim_path": path, "error": "Prim not found"})
                continue
            state: Dict[str, Any] = {"prim_path": path}
            transform = self.get_prim_transform(path)
            state["position"] = transform.get("position", [0, 0, 0])
            # Add velocity if rigid body
            if prim.HasAPI(UsdPhysics.RigidBodyAPI):
                try:
                    physics_state = self.get_physics_state(path)
                    state["linear_velocity"] = physics_state.get("linear_velocity", [0, 0, 0])
                    state["angular_velocity"] = physics_state.get("angular_velocity", [0, 0, 0])
                except Exception:
                    pass
            prim_states.append(state)
        result["prim_states"] = prim_states

    # Observe joint states
    if observe_joints:
        joint_states = []
        for path in observe_joints:
            try:
                positions = self.get_joint_positions(path)
                from isaacsim.core.prims import SingleArticulation
                art = SingleArticulation(prim_path=path)
                names = art.dof_names if art.dof_names else []
                joints_dict = dict(zip(names, positions)) if names else {"positions": positions}
                joint_states.append({"prim_path": path, "joints": joints_dict})
            except Exception as e:
                joint_states.append({"prim_path": path, "error": str(e)})
        result["joint_states"] = joint_states

    return result
```

- [ ] **Step 3: Update handler to pass observe params**

In `handlers/simulation.py`, update the `step` function:

```python
def step(adapter: IsaacAdapterBase, num_steps: int = 1,
         observe_prims: Optional[Sequence[str]] = None,
         observe_joints: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    try:
        result = adapter.step(num_steps=num_steps, observe_prims=observe_prims,
                              observe_joints=observe_joints)
        return {"status": "success", "message": f"Stepped {num_steps} frames", **result}
    except Exception as e:
        return {"status": "error", "message": str(e)}
```

- [ ] **Step 4: Update MCP tool**

In `isaac_mcp/tools/simulation.py`, update the `step_simulation` tool:

```python
@mcp.tool("step_simulation")
def step_simulation(num_steps: int = 1, observe_prims: Optional[List[str]] = None,
                    observe_joints: Optional[List[str]] = None) -> str:
    """Step the simulation forward by N frames, optionally observing prim and joint states after stepping.

    Args:
        num_steps: Number of simulation frames to step.
        observe_prims: Optional list of prim paths to observe (returns position + velocity).
        observe_joints: Optional list of articulation prim paths to observe (returns joint positions).
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
```

- [ ] **Step 5: Test live**

Create a cube with rigid body at height 2.0, play simulation, then call:
```python
step_simulation(num_steps=10, observe_prims=["/World/Cube"])
```
Verify the response includes the cube's updated position (falling due to gravity).

- [ ] **Step 6: Commit**

```bash
git add isaac_mcp/tools/simulation.py \
  isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/base.py \
  isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/v5.py \
  isaac.sim.mcp_extension/isaac_sim_mcp_extension/handlers/simulation.py
git commit -m "feat: add observe params to step_simulation for step-and-observe (issue #8)"
```

---

## Task 7: Update structural tests

**Files:**
- Modify: `tests/test_handler_structure.py:49-62` (update expected abstract methods)

- [ ] **Step 1: Update expected abstract methods set**

In `tests/test_handler_structure.py`, update the `expected` set in `test_adapter_base_has_all_abstract_methods`:

```python
expected = {
    "get_stage", "get_assets_root_path", "discover_environments", "load_environment",
    "create_prim", "delete_prim", "add_reference_to_stage",
    "set_prim_transform", "get_prim_transform", "list_prims", "get_prim_info",
    "create_xform_prim", "create_articulation",
    "discover_robots", "get_robot_joint_info", "set_joint_positions", "get_joint_positions",
    "create_world", "create_simulation_context", "create_physics_scene",
    "create_camera", "capture_camera_image", "create_lidar", "get_lidar_point_cloud",
    "create_pbr_material", "create_physics_material", "apply_material",
    "create_light", "modify_light",
    "clone_prim", "import_urdf",
    "play", "pause", "stop", "step", "execute_script",
    # New observability methods
    "get_simulation_state", "get_physics_state", "get_joint_config", "reload_script",
}
```

- [ ] **Step 2: Run structural tests**

```bash
cd /home/user/Documents/GitHub/isaac-sim-mcp && python -m pytest tests/test_handler_structure.py tests/test_tool_registration.py -v
```
Expected: all tests pass.

- [ ] **Step 3: Commit**

```bash
git add tests/test_handler_structure.py
git commit -m "test: update structural tests for new observability methods"
```

---

## Task 8: Live integration testing

**Files:**
- No file changes — uses existing MCP tools against running Isaac Sim instance

- [ ] **Step 1: Test `execute_script` stdout capture**

Call `execute_script(code="print('hello'); print('world')")` and verify `stdout` contains both lines.

- [ ] **Step 2: Test `execute_script` with cwd**

Call `execute_script(code="import sys; print('/tmp' in sys.path)", cwd="/tmp")` and verify stdout is `"True\n"`.

- [ ] **Step 3: Test `get_simulation_state` across states**

Call `get_simulation_state()` — verify `"stopped"`. Then `play_simulation()`, call again — verify `"playing"`. Then `pause_simulation()`, call again — verify `"paused"`. Then `stop_simulation()`.

- [ ] **Step 4: Test `get_physics_state`**

Create a cube at `/World/TestCube` with `create_object(object_type="Cube", prim_path="/World/TestCube", position=[0,0,2])`. Create physics scene. Call `get_physics_state(prim_path="/World/TestCube")` — verify rigid body info is returned.

- [ ] **Step 5: Test `get_joint_config` with a robot**

Create a robot (e.g., Franka). Play simulation briefly. Call `get_joint_config(prim_path="/World/Franka")` — verify joints array with stiffness/damping.

- [ ] **Step 6: Test `reload_script`**

Create `/tmp/test_mcp_reload.py` with `print("v1")`. Call `reload_script(file_path="/tmp/test_mcp_reload.py")` — verify stdout has `"v1"`.

- [ ] **Step 7: Test `step_simulation` with observe**

With a physics object in the scene, play simulation, then call `step_simulation(num_steps=5, observe_prims=["/World/TestCube"])` — verify position data in response.

- [ ] **Step 8: Clean up test scene**

Call `clear_scene()` to reset.
