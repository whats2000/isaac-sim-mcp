# Tool Instructions & Response Enhancements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enhance MCP tool instructions and response data so AI clients use the debug loop correctly, prefer named tools over execute_script, and get actionable dimensional data from create/inspect responses.

**Architecture:** Changes span three layers: (1) server-level instructions in `isaac_mcp/server.py`, (2) tool docstrings in `isaac_mcp/tools/*.py`, (3) extension-side response data in `isaac.sim.mcp_extension/.../handlers/*.py` and `adapters/v5.py`. No new tools are added.

**Tech Stack:** Python, MCP FastMCP, USD (pxr), Isaac Sim 5.1 API

---

### Task 1: Add `get_prim_actual_size` to adapter base and v5 implementation

**Files:**
- Modify: `isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/base.py:104-107`
- Modify: `isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/v5.py:170-182`
- Modify: `tests/test_handler_structure.py:48-91`

- [ ] **Step 1: Add abstract method to base adapter**

In `isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/base.py`, add after the `get_prim_info` abstract method (after line 107):

```python
    @abstractmethod
    def get_prim_actual_size(self, prim_path: str) -> Tuple[List[float], Tuple[List[float], List[float]]]:
        """Return actual dimensions and bounding box for a geometric prim.

        Returns:
            A tuple of (actual_size, (bbox_min, bbox_max)) where:
            - actual_size: [x, y, z] dimensions in meters (default_size * scale)
            - bbox_min: [x, y, z] world-space minimum corner
            - bbox_max: [x, y, z] world-space maximum corner
        """
        ...
```

- [ ] **Step 2: Update the test expectation for abstract methods**

In `tests/test_handler_structure.py`, add `"get_prim_actual_size"` to the `expected` set in `test_adapter_base_has_all_abstract_methods` (line 48-91):

```python
    expected = {
        "get_stage",
        "get_assets_root_path",
        "discover_environments",
        "load_environment",
        "create_prim",
        "delete_prim",
        "add_reference_to_stage",
        "set_prim_transform",
        "get_prim_transform",
        "list_prims",
        "get_prim_info",
        "get_prim_actual_size",
        "create_xform_prim",
        "create_articulation",
        "discover_robots",
        "get_robot_joint_info",
        "set_joint_positions",
        "get_joint_positions",
        "create_world",
        "create_simulation_context",
        "create_physics_scene",
        "create_camera",
        "capture_camera_image",
        "create_lidar",
        "get_lidar_point_cloud",
        "create_pbr_material",
        "create_physics_material",
        "apply_material",
        "create_light",
        "modify_light",
        "clone_prim",
        "import_urdf",
        "play",
        "pause",
        "stop",
        "step",
        "execute_script",
        # Observability methods (issue #1)
        "get_simulation_state",
        "get_physics_state",
        "get_joint_config",
        "reload_script",
    }
```

- [ ] **Step 3: Implement `get_prim_actual_size` in v5 adapter**

In `isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/v5.py`, add after the existing `get_prim_info` method (after line 182):

```python
    def get_prim_actual_size(self, prim_path: str) -> Tuple[List[float], Tuple[List[float], List[float]]]:
        from pxr import UsdGeom

        stage = self.get_stage()
        prim = stage.GetPrimAtPath(prim_path)
        if not prim.IsValid():
            raise ValueError(f"Prim not found: {prim_path}")

        prim_type = prim.GetTypeName()
        xformable = UsdGeom.Xformable(prim)

        # Get scale from xform ops
        scale = [1.0, 1.0, 1.0]
        for op in xformable.GetOrderedXformOps():
            if op.GetOpType() == UsdGeom.XformOp.TypeScale:
                s = op.Get()
                scale = [float(s[0]), float(s[1]), float(s[2])]
                break

        # Get position from world transform
        world_tf = xformable.ComputeLocalToWorldTransform(0)
        pos = world_tf.ExtractTranslation()
        position = [float(pos[0]), float(pos[1]), float(pos[2])]

        # Read actual dimensions from USD attributes (not hardcoded defaults —
        # these values can vary across Isaac Sim versions)
        if prim_type == "Cube":
            cube = UsdGeom.Cube(prim)
            size = cube.GetSizeAttr().Get()
            if size is None:
                size = 2.0
            dims = [size * scale[0], size * scale[1], size * scale[2]]
        elif prim_type == "Sphere":
            sphere = UsdGeom.Sphere(prim)
            radius = sphere.GetRadiusAttr().Get()
            if radius is None:
                radius = 1.0
            dims = [2 * radius * scale[0], 2 * radius * scale[1], 2 * radius * scale[2]]
        elif prim_type in ("Cylinder", "Cone"):
            gprim = UsdGeom.Cylinder(prim) if prim_type == "Cylinder" else UsdGeom.Cone(prim)
            radius = gprim.GetRadiusAttr().Get()
            height = gprim.GetHeightAttr().Get()
            if radius is None:
                radius = 1.0
            if height is None:
                height = 2.0
            dims = [2 * radius * scale[0], 2 * radius * scale[1], height * scale[2]]
        elif prim_type == "Capsule":
            capsule = UsdGeom.Capsule(prim)
            radius = capsule.GetRadiusAttr().Get()
            height = capsule.GetHeightAttr().Get()
            if radius is None:
                radius = 0.5
            if height is None:
                height = 1.0
            dims = [2 * radius * scale[0], 2 * radius * scale[1], (height + 2 * radius) * scale[2]]
        else:
            return [0.0, 0.0, 0.0], ([0.0, 0.0, 0.0], [0.0, 0.0, 0.0])

        bbox_min = [position[i] - dims[i] / 2 for i in range(3)]
        bbox_max = [position[i] + dims[i] / 2 for i in range(3)]
        return dims, (bbox_min, bbox_max)
```

- [ ] **Step 4: Run tests to verify structure checks pass**

Run: `cd /home/user/Documents/GitHub/isaac-sim-mcp && python -m pytest tests/test_handler_structure.py -v`
Expected: PASS (all 3 tests)

- [ ] **Step 5: Commit**

```bash
git add isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/base.py isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/v5.py tests/test_handler_structure.py
git commit -m "feat: add get_prim_actual_size adapter method for dimensional data"
```

---

### Task 2: Enhance `create_object` response with actual_size and bounding_box

**Files:**
- Modify: `isaac.sim.mcp_extension/isaac_sim_mcp_extension/handlers/objects.py:50-58`

- [ ] **Step 1: Update the create handler to return size data**

In `isaac.sim.mcp_extension/isaac_sim_mcp_extension/handlers/objects.py`, replace the success return block (lines 55-58) with:

```python
        _prim = adapter.create_prim(prim_path, prim_type=object_type)
        if position or rotation or scale:
            adapter.set_prim_transform(prim_path, position=position, rotation=rotation, scale=scale)
        result = {"status": "success", "message": f"Created {object_type}", "prim_path": prim_path}
        try:
            actual_size, (bbox_min, bbox_max) = adapter.get_prim_actual_size(prim_path)
            result["actual_size"] = actual_size
            result["bounding_box"] = {"min": bbox_min, "max": bbox_max}
        except Exception:
            pass
        return result
```

- [ ] **Step 2: Commit**

```bash
git add isaac.sim.mcp_extension/isaac_sim_mcp_extension/handlers/objects.py
git commit -m "feat: return actual_size and bounding_box from create_object"
```

---

### Task 3: Enhance `get_prim_info` response with actual_size

**Files:**
- Modify: `isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/v5.py:170-182`

- [ ] **Step 1: Update get_prim_info to include actual_size for geometric prims**

In `isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/v5.py`, replace the `get_prim_info` method (lines 170-182) with:

```python
    def get_prim_info(self, prim_path: str) -> Dict[str, Any]:
        stage = self.get_stage()
        prim = stage.GetPrimAtPath(prim_path)
        if not prim.IsValid():
            raise ValueError(f"Prim not found: {prim_path}")
        transform = self.get_prim_transform(prim_path)
        children = [str(c.GetPath()) for c in prim.GetAllChildren()]
        info: Dict[str, Any] = {
            "path": prim_path,
            "type": prim.GetTypeName(),
            "transform": transform,
            "children": children,
        }
        if prim.GetTypeName() in ("Cube", "Sphere", "Cylinder", "Cone", "Capsule"):
            try:
                actual_size, _ = self.get_prim_actual_size(prim_path)
                info["actual_size"] = actual_size
            except Exception:
                pass
        return info
```

- [ ] **Step 2: Commit**

```bash
git add isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/v5.py
git commit -m "feat: return actual_size from get_prim_info for geometric prims"
```

---

### Task 4: Enhance `create_robot` response with joint info

**Files:**
- Modify: `isaac.sim.mcp_extension/isaac_sim_mcp_extension/handlers/robots.py:151-156`

- [ ] **Step 1: Update create handler to return joint info**

In `isaac.sim.mcp_extension/isaac_sim_mcp_extension/handlers/robots.py`, replace lines 151-156 with:

```python
        result = {
            "status": "success",
            "message": f"Created {match['description']} robot",
            "prim_path": prim_path,
            "robot_key": match["key"],
        }
        try:
            info = adapter.get_robot_joint_info(prim_path)
            result["joint_names"] = info.get("joint_names", [])
            result["num_dof"] = info.get("num_dof", 0)
        except Exception:
            pass
        return result
```

- [ ] **Step 2: Commit**

```bash
git add isaac.sim.mcp_extension/isaac_sim_mcp_extension/handlers/robots.py
git commit -m "feat: return joint_names and num_dof from create_robot"
```

---

### Task 5: Enhance `get_robot_info` response with joint limits

**Files:**
- Modify: `isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/v5.py:249-256`

- [ ] **Step 1: Enhance `get_robot_joint_info` to include joint limits**

In `isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/v5.py`, replace the `get_robot_joint_info` method (lines 249-256) with:

```python
    def get_robot_joint_info(self, prim_path: str) -> Dict[str, Any]:
        from isaacsim.core.prims import SingleArticulation
        from pxr import UsdPhysics

        art = SingleArticulation(prim_path=prim_path)
        joint_names = art.dof_names if art.dof_names else []
        num_dof = art.num_dof if art.num_dof else 0

        # Traverse stage to find joint limits
        stage = self.get_stage()
        joint_limits = []
        for jname in joint_names:
            limit_entry: Dict[str, Any] = {"name": jname}
            # Search for matching joint prim under the robot
            for prim in stage.Traverse():
                if not str(prim.GetPath()).startswith(prim_path):
                    continue
                if prim.GetName() != jname:
                    continue
                rev = UsdPhysics.RevoluteJoint(prim)
                if rev and rev.GetAxisAttr().Get() is not None:
                    lo = rev.GetLowerLimitAttr().Get()
                    hi = rev.GetUpperLimitAttr().Get()
                    limit_entry["type"] = "revolute"
                    limit_entry["lower"] = float(lo) if lo is not None else None
                    limit_entry["upper"] = float(hi) if hi is not None else None
                    limit_entry["units"] = "degrees"
                    break
                pris = UsdPhysics.PrismaticJoint(prim)
                if pris and pris.GetAxisAttr().Get() is not None:
                    lo = pris.GetLowerLimitAttr().Get()
                    hi = pris.GetUpperLimitAttr().Get()
                    limit_entry["type"] = "prismatic"
                    limit_entry["lower"] = float(lo) if lo is not None else None
                    limit_entry["upper"] = float(hi) if hi is not None else None
                    limit_entry["units"] = "meters"
                    break
            joint_limits.append(limit_entry)

        return {
            "joint_names": joint_names,
            "num_dof": num_dof,
            "joint_limits": joint_limits,
        }
```

- [ ] **Step 2: Commit**

```bash
git add isaac.sim.mcp_extension/isaac_sim_mcp_extension/adapters/v5.py
git commit -m "feat: return joint limits from get_robot_joint_info"
```

---

### Task 6: Enhance server instructions

**Files:**
- Modify: `isaac_mcp/server.py:58-78`

- [ ] **Step 1: Replace instructions and asset_creation_strategy prompt**

In `isaac_mcp/server.py`, replace lines 58-78 with:

```python
_INSTRUCTIONS = """\
Isaac Sim integration through the Model Context Protocol.

## MCP Tools vs Scripts / Action Graphs

MCP tools operate BETWEEN simulation frames (editor-level):
- Scene setup: create_physics_scene, create_object, create_robot, load_environment
- Inspection: get_prim_info, get_robot_info, get_physics_state, get_joint_config
- Stepping: step_simulation (advance N frames and observe state)
- Joint control: set_joint_positions, get_joint_positions
- Diagnostics: get_isaac_logs, get_simulation_state

Scripts and Action Graphs operate WITHIN simulation frames (runtime-level):
- Real-time control loops and physics callbacks
- IK solvers, trajectory planners, state machines
- Sensor data processing pipelines
Use execute_script for one-off setup, or write a .py file and load it with reload_script.

## Workflow

### Scene Setup
1. get_scene_info — verify connection
2. create_physics_scene — physics + ground plane
3. create_robot / create_object / load_environment — populate scene
4. get_prim_info — verify positions and actual sizes

### Debug Loop (step-and-observe)
1. set_joint_positions — command the robot
2. step_simulation with observe_prims and observe_joints — advance and read state
3. If drives misbehave → get_joint_config (check stiffness, damping, position error)
4. If objects misbehave → get_physics_state (check collision, mass, rigid body)
5. If anything errors → get_isaac_logs
6. Adjust and repeat

Do NOT use play_simulation + sleep + execute_script as a debug loop.
Use step_simulation for controlled, observable stepping.

### Controller Development
1. Write controller as a .py file (state machine, IK, physics callbacks)
2. reload_script to load it into Isaac Sim
3. step_simulation to debug the behavior step-by-step
4. Edit the file, reload_script again to iterate
5. play_simulation once the controller works correctly

### Tool Priority
Always prefer named tools over execute_script:
- Reading joints → get_joint_positions (not execute_script)
- Inspecting prims → get_prim_info (not execute_script)
- Checking physics → get_physics_state (not execute_script)
- Checking drives → get_joint_config (not execute_script)
- Checking logs → get_isaac_logs (not execute_script)

execute_script is the escape hatch for operations no named tool covers.
"""

mcp = FastMCP(
    "IsaacSimMCP",
    instructions=_INSTRUCTIONS,
    lifespan=server_lifespan,
)

register_all_tools(mcp, get_isaac_connection)
```

Remove the `asset_creation_strategy` prompt function (lines 67-78 of original) — its content is now part of `_INSTRUCTIONS`.

- [ ] **Step 2: Run tests to verify server still loads**

Run: `cd /home/user/Documents/GitHub/isaac-sim-mcp && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add isaac_mcp/server.py
git commit -m "feat: replace minimal instructions with comprehensive workflow guide"
```

---

### Task 7: Enhance simulation tool docstrings

**Files:**
- Modify: `isaac_mcp/tools/simulation.py:67-77,115-129,131-139,141-153,155-167,169-186,188-207`

- [ ] **Step 1: Update all simulation tool docstrings**

In `isaac_mcp/tools/simulation.py`, replace the docstrings for the following tools:

**`step_simulation`** (line 72-77) — replace docstring with:
```python
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
```

**`get_isaac_logs`** (lines 117-123) — replace docstring with:
```python
        """Diagnostic tool: get recent warnings and errors from the Isaac Sim console.

        Call this after any tool returns an error, after simulation behavior is unexpected,
        or after execute_script / reload_script fails. Helps diagnose physics warnings,
        collision issues, and script errors that are not surfaced in tool responses.

        Args:
            clear: Clear the log buffer after reading. Default True.
            count: Maximum number of log entries to return.
        """
```

**`get_simulation_state`** (line 133) — replace docstring with:
```python
        """Get the current simulation state including timeline status (playing/stopped/paused),
        simulation time, and physics dt. Call this to verify the simulation is running before
        using step_simulation."""
```

**`get_physics_state`** (lines 142-148) — replace docstring with:
```python
        """Diagnostic tool: get physics state for a prim.

        Returns rigid body status, mass, velocities, kinematic flag, and collision info.
        Call this when:
        - Objects fall through the ground (check collision enabled)
        - Objects don't move when expected (check is_kinematic, mass)
        - Grasping fails (check collision on gripper fingers and target object)

        Args:
            prim_path: USD path to the prim to inspect.
        """
```

**`get_joint_config`** (lines 156-162) — replace docstring with:
```python
        """Diagnostic tool: get joint drive configuration for a robot articulation.

        Returns stiffness, damping, limits, target vs actual positions, and position error
        for each joint. Call this when:
        - Joint drives are not tracking targets (check position_error)
        - Joints are oscillating or unstable (check stiffness/damping ratio)
        - Joints hit limits unexpectedly (check lower_limit/upper_limit)

        Args:
            prim_path: USD path to the robot articulation root.
        """
```

**`execute_script`** (lines 170-177) — replace docstring with:
```python
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
```

**`reload_script`** (lines 189-196) — replace docstring with:
```python
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
```

- [ ] **Step 2: Run tests**

Run: `cd /home/user/Documents/GitHub/isaac-sim-mcp && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add isaac_mcp/tools/simulation.py
git commit -m "docs: enhance simulation tool docstrings with workflow guidance"
```

---

### Task 8: Enhance robot tool docstrings

**Files:**
- Modify: `isaac_mcp/tools/robots.py:41-49,86-90,98-107,119-125`

- [ ] **Step 1: Update all robot tool docstrings**

In `isaac_mcp/tools/robots.py`, replace the following docstrings:

**`create_robot`** (lines 41-49) — replace docstring with:
```python
        """Create a robot in the scene from the Isaac Sim asset library.

        Supports fuzzy matching — e.g. "franka", "spot", "g1", "go1".
        Call list_available_robots first to see all available robots.
        Call create_physics_scene before creating robots.

        Returns prim_path, robot_key, joint_names, and num_dof so you can
        immediately use set_joint_positions without a follow-up get_robot_info call.

        Args:
            robot_type: Robot name or search term. Fuzzy matched against available robots.
            position: [x, y, z] world position.
            name: Custom name for the robot prim.
        """
```

**`get_robot_info`** (lines 86-90) — replace docstring with:
```python
        """Get robot joint information including names, DOF count, joint types, and limits.

        Call this after create_robot to understand the robot's kinematic structure.
        Returns joint names ordered by DOF index, joint types (revolute/prismatic),
        and joint limits (degrees for revolute, meters for prismatic).

        Args:
            prim_path: The prim path of the robot.
        """
```

**`set_joint_positions`** (lines 102-107) — replace docstring with:
```python
        """Set target joint positions on a robot via ArticulationAction.

        Units: radians for revolute joints, meters for prismatic joints (e.g. gripper fingers).
        Use get_robot_info to discover joint names, types, and limits first.
        After calling this, use step_simulation to advance and observe the result —
        do not use play_simulation + sleep.

        Args:
            prim_path: The prim path of the robot.
            joint_positions: List of target joint position values.
            joint_indices: Optional list of joint indices to set. Sets all joints if not provided.
        """
```

**`get_joint_positions`** (lines 120-125) — replace docstring with:
```python
        """Read current joint positions from a robot.

        Units: radians for revolute joints, meters for prismatic joints.
        Joint order matches the joint_names from get_robot_info.
        For a combined step-and-read, prefer step_simulation with observe_joints.

        Args:
            prim_path: The prim path of the robot.
        """
```

- [ ] **Step 2: Commit**

```bash
git add isaac_mcp/tools/robots.py
git commit -m "docs: enhance robot tool docstrings with units and workflow guidance"
```

---

### Task 9: Enhance object and scene tool docstrings

**Files:**
- Modify: `isaac_mcp/tools/objects.py:47-57`
- Modify: `isaac_mcp/tools/scene.py:98-103`

- [ ] **Step 1: Update create_object docstring**

In `isaac_mcp/tools/objects.py`, replace the docstring (lines 47-57) with:

```python
        """Create a primitive object (Cube, Sphere, Cylinder, Cone, Capsule, Plane).

        The scale parameter multiplies the primitive's default size. For example,
        a Cube has default size 2.0, so scale=[0.5, 0.5, 0.5] creates a 1.0m cube.

        Returns prim_path, actual_size [x, y, z] in meters, and bounding_box
        (min/max corners in world coordinates) so you can accurately place other
        objects relative to this one (e.g. placing a cube on top of a table).

        Args:
            object_type: Type of primitive — Cube, Sphere, Cylinder, Cone, Capsule, or Plane.
            position: [x, y, z] world position.
            rotation: [rx, ry, rz] rotation in degrees.
            scale: [sx, sy, sz] scale factors.
            color: [r, g, b] color values (0-1).
            physics_enabled: Enable physics on this object.
            prim_path: Custom prim path. Auto-generated if not provided.
        """
```

- [ ] **Step 2: Update get_prim_info docstring**

In `isaac_mcp/tools/scene.py`, replace the docstring (lines 99-103) with:

```python
        """Get detailed information about a specific prim.

        Returns type, world-space position, and children. For geometric prims
        (Cube, Sphere, Cylinder, Cone, Capsule), also returns actual_size [x, y, z]
        in meters accounting for scale and default primitive dimensions.

        Args:
            prim_path: The USD prim path to inspect.
        """
```

- [ ] **Step 3: Run all tests**

Run: `cd /home/user/Documents/GitHub/isaac-sim-mcp && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add isaac_mcp/tools/objects.py isaac_mcp/tools/scene.py
git commit -m "docs: enhance create_object and get_prim_info docstrings with size info"
```

---

### Task 10: Final lint check and verification

**Files:**
- All modified files

- [ ] **Step 1: Run linter**

Run: `cd /home/user/Documents/GitHub/isaac-sim-mcp && python -m ruff check isaac_mcp/ isaac.sim.mcp_extension/ tests/`
Expected: No errors (or only pre-existing ones)

- [ ] **Step 2: Run full test suite**

Run: `cd /home/user/Documents/GitHub/isaac-sim-mcp && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 3: Verify server imports cleanly**

Run: `cd /home/user/Documents/GitHub/isaac-sim-mcp && python -c "from isaac_mcp.server import mcp; print(f'Server instructions length: {len(mcp.settings.instructions)} chars'); print('OK')"`
Expected: Prints instructions length and "OK"

- [ ] **Step 4: Commit any lint fixes**

```bash
git add -A
git commit -m "style: fix lint issues from tool instruction enhancements"
```
