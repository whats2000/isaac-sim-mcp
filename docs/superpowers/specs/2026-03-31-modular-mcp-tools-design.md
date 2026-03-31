# Isaac Sim MCP Extension — Modular Tools Redesign

**Date:** 2026-03-31  
**Status:** Approved  
**Target:** Isaac Sim 5.1.0 (with adapter architecture for future versions)

## Goals

1. Reorganize the monolithic extension into modular, domain-specific tool categories
2. Introduce an adapter layer to isolate Isaac Sim version-specific APIs
3. Expand from 7 tools to 31 tools covering common robotics workflows
4. Make the project contributor-friendly with clear structure and separation of concerns

## Architecture

### Directory Structure

```
isaac_mcp/
├── __init__.py
├── server.py                  # MCP server entry point (slim, registers tools)
├── connection.py              # IsaacConnection class (socket communication)
├── tools/
│   ├── __init__.py            # Exports register_all_tools(mcp, get_connection)
│   ├── scene.py               # Scene management tools
│   ├── objects.py             # Primitive creation & transform
│   ├── lighting.py            # Light creation & control
│   ├── robots.py              # Robot creation & joint control
│   ├── sensors.py             # Camera, lidar
│   ├── materials.py           # PBR & physics materials
│   ├── assets.py              # URDF import, USD loading, search, gen3d
│   └── simulation.py          # Play/pause/stop, physics params

isaac.sim.mcp_extension/
├── config/extension.toml
├── isaac_sim_mcp_extension/
│   ├── __init__.py
│   ├── extension.py           # Slim entry point, routes commands via registry
│   ├── adapters/
│   │   ├── __init__.py        # Exports get_adapter() factory function
│   │   ├── base.py            # Abstract adapter interface (ABC)
│   │   └── v5.py              # Isaac Sim 5.1.0 implementation
│   ├── handlers/
│   │   ├── __init__.py        # Exports register_all_handlers(registry, adapter)
│   │   ├── scene.py           # Scene command handlers
│   │   ├── objects.py         # Object command handlers
│   │   ├── lighting.py        # Light command handlers
│   │   ├── robots.py         # Robot command handlers
│   │   ├── sensors.py         # Sensor command handlers
│   │   ├── materials.py       # Material command handlers
│   │   ├── assets.py          # Asset import handlers
│   │   └── simulation.py      # Simulation control handlers
│   ├── gen3d.py               # Beaver3D integration (unchanged)
│   └── usd.py                 # USD utilities (unchanged)
```

### Package Wiring

**MCP server side** — `server.py` creates the FastMCP instance and connection getter, then calls `register_all_tools(mcp, get_connection)` from `tools/__init__.py`. Each tool module receives the connection getter so it can send commands.

**Extension side** — `extension.py` calls `get_adapter()` from `adapters/__init__.py` (which returns `IsaacAdapterV5()` for now), then calls `register_all_handlers(registry, adapter)` from `handlers/__init__.py`. Each handler module registers its command types into the shared registry dict.

### Design Principles

- **Adapter pattern** — All Isaac Sim API calls go through `adapters/base.py`. Only the adapter imports `isaacsim.*` directly. Currently only `v5.py` exists; future versions add a new file without touching tool/handler code.
- **Mirrored structure** — MCP tools in `tools/` map 1:1 to extension handlers in `handlers/`. Each tool sends a JSON command, the matching handler executes it inside Isaac Sim.
- **Self-registering handlers** — Each handler module exposes a `register(registry, adapter)` function. The extension routes commands via a dict lookup instead of a giant if/else chain.
- **Slim entry points** — `server.py` and `extension.py` stay under 100 lines each. All logic lives in the tool/handler modules.

## Adapter Layer

The adapter abstracts all version-specific Isaac Sim APIs behind a stable interface. Handler code never imports `isaacsim.*` directly.

The adapter lives on the **extension side only** (inside Isaac Sim). The MCP server side does not need it — it sends JSON commands over the socket.

### Abstract Interface (`adapters/base.py`)

```python
class IsaacAdapterBase(ABC):
    # Scene
    @abstractmethod
    def get_stage(self): ...
    @abstractmethod
    def get_assets_root_path(self) -> str: ...

    # Prims
    @abstractmethod
    def create_prim(self, prim_path, prim_type, **kwargs): ...
    @abstractmethod
    def add_reference_to_stage(self, usd_path, prim_path): ...
    @abstractmethod
    def set_prim_transform(self, prim_path, position, rotation, scale): ...

    # Robots
    @abstractmethod
    def create_xform_prim(self, prim_path): ...
    @abstractmethod
    def create_articulation(self, prim_path, name): ...

    # Physics
    @abstractmethod
    def create_world(self, **kwargs): ...
    @abstractmethod
    def create_simulation_context(self, **kwargs): ...

    # Sensors
    @abstractmethod
    def create_camera(self, prim_path, resolution, **kwargs): ...

    # Materials
    @abstractmethod
    def create_pbr_material(self, prim_path, **kwargs): ...

    # Lighting
    @abstractmethod
    def create_light(self, light_type, prim_path, **kwargs): ...

    # Assets
    @abstractmethod
    def import_urdf(self, urdf_path, prim_path, **kwargs): ...
```

### Isaac Sim 5.1.0 Implementation (`adapters/v5.py`)

Implements the abstract interface using `isaacsim.*` imports:

- `isaacsim.core.api` — World, SimulationContext, PhysicsContext
- `isaacsim.core.prims` — SingleXFormPrim, SingleArticulation
- `isaacsim.core.utils.stage` — add_reference_to_stage
- `isaacsim.core.utils.prims` — create_prim
- `isaacsim.core.utils.types` — ArticulationAction
- `isaacsim.storage.native` — get_assets_root_path
- `isaacsim.core.api.objects` — DynamicCuboid, etc.
- `isaacsim.core.api.robots` — Robot
- `isaacsim.core.experimental.objects` — DistantLight, DomeLight, etc.
- `isaacsim.core.experimental.materials` — OmniPBR, PreviewSurface
- `isaacsim.sensors.camera` — Camera
- `isaacsim.sensors.rtx` — LidarRTX
- `isaacsim.asset.importer.urdf` — URDFParseFile, URDFImportRobot

Version detection happens at extension startup from the Kit environment. For now only v5 is loaded.

## Communication Protocol

JSON over TCP socket on port 8766 (unchanged).

### Command Format (MCP server -> Extension)

```json
{
    "type": "category.action",
    "params": { ... }
}
```

Dot notation matches the modular structure: `scene.get_info`, `robots.create`, `lighting.create`, `sensors.capture_image`, etc.

### Response Format (Extension -> MCP server)

Success:
```json
{
    "status": "success",
    "result": { ... }
}
```

Error:
```json
{
    "status": "error",
    "message": "Human-readable error description",
    "error_type": "connection_error | invalid_params | runtime_error | not_found"
}
```

### Handler Registration

```python
# extension.py
class MCPExtension(omni.ext.IExt):
    def on_startup(self, ext_id):
        self.adapter = IsaacAdapterV5()
        self.registry = {}
        from .handlers import scene, objects, lighting, robots, sensors, materials, assets, simulation
        for module in [scene, objects, lighting, robots, sensors, materials, assets, simulation]:
            module.register(self.registry, self.adapter)

    def execute_command(self, command):
        handler = self.registry.get(command["type"])
        if handler:
            return handler(**command.get("params", {}))
        return {"status": "error", "message": f"Unknown command: {command['type']}"}
```

```python
# handlers/lighting.py (example)
def register(registry, adapter):
    registry["lighting.create"] = lambda **p: create_light(adapter, **p)
    registry["lighting.modify"] = lambda **p: modify_light(adapter, **p)

def create_light(adapter, light_type="DistantLight", position=None, intensity=1000, color=None, rotation=None):
    ...
```

## Tool Catalog

### Scene Tools (`tools/scene.py` / `handlers/scene.py`)

| Tool | Command Type | Params | Description |
|------|-------------|--------|-------------|
| `get_scene_info` | `scene.get_info` | — | Ping server, return stage path, assets root, prim count |
| `create_physics_scene` | `scene.create_physics` | `gravity?, scene_name?` | Create physics scene with ground plane |
| `clear_scene` | `scene.clear` | `keep_physics?` | Remove all prims from stage |
| `list_prims` | `scene.list_prims` | `root_path?, prim_type?` | List prims in scene, optionally filtered |
| `get_prim_info` | `scene.get_prim_info` | `prim_path` | Get transform, type, properties of a prim |

### Object Tools (`tools/objects.py` / `handlers/objects.py`)

| Tool | Command Type | Params | Description |
|------|-------------|--------|-------------|
| `create_object` | `objects.create` | `object_type, position?, rotation?, scale?, color?, physics_enabled?` | Create primitive (Cube, Sphere, Cylinder, Cone, Capsule, Plane) |
| `delete_object` | `objects.delete` | `prim_path` | Remove a prim from stage |
| `transform_object` | `objects.transform` | `prim_path, position?, rotation?, scale?` | Set transform on existing prim |
| `clone_object` | `objects.clone` | `source_path, target_path, position?` | Duplicate a prim |

### Lighting Tools (`tools/lighting.py` / `handlers/lighting.py`)

| Tool | Command Type | Params | Description |
|------|-------------|--------|-------------|
| `create_light` | `lighting.create` | `light_type, position?, intensity?, color?, rotation?` | Create light (Distant, Dome, Sphere, Rect, Disk, Cylinder) |
| `modify_light` | `lighting.modify` | `prim_path, intensity?, color?` | Adjust existing light properties |

### Robot Tools (`tools/robots.py` / `handlers/robots.py`)

| Tool | Command Type | Params | Description |
|------|-------------|--------|-------------|
| `create_robot` | `robots.create` | `robot_type, position?, name?` | Create robot from built-in library |
| `list_available_robots` | `robots.list` | — | Return supported robot types with descriptions |
| `get_robot_info` | `robots.get_info` | `prim_path` | Get joint names, DOF count, current positions |
| `set_joint_positions` | `robots.set_joints` | `prim_path, joint_positions, joint_indices?` | Set target joint positions |
| `get_joint_positions` | `robots.get_joints` | `prim_path` | Read current joint positions |

Available built-in robots: franka, jetbot, carter, g1, go1.

### Sensor Tools (`tools/sensors.py` / `handlers/sensors.py`)

| Tool | Command Type | Params | Description |
|------|-------------|--------|-------------|
| `create_camera` | `sensors.create_camera` | `prim_path, position?, rotation?, resolution?` | Add camera to scene |
| `capture_image` | `sensors.capture_image` | `prim_path, output_path?` | Capture RGB image from camera |
| `create_lidar` | `sensors.create_lidar` | `prim_path, position?, rotation?, config?` | Add lidar sensor |
| `get_lidar_point_cloud` | `sensors.get_point_cloud` | `prim_path` | Get point cloud data |

### Material Tools (`tools/materials.py` / `handlers/materials.py`)

| Tool | Command Type | Params | Description |
|------|-------------|--------|-------------|
| `create_material` | `materials.create` | `material_type, prim_path, color?, roughness?, metallic?` | Create PBR or physics material |
| `apply_material` | `materials.apply` | `material_path, target_prim_path` | Bind material to a prim |

### Asset Tools (`tools/assets.py` / `handlers/assets.py`)

| Tool | Command Type | Params | Description |
|------|-------------|--------|-------------|
| `import_urdf` | `assets.import_urdf` | `urdf_path, prim_path?, position?` | Import robot from URDF file |
| `load_usd` | `assets.load_usd` | `usd_url, prim_path?, position?, scale?` | Load USD asset from URL/path |
| `search_usd` | `assets.search_usd` | `text_prompt, target_path?, position?, scale?` | Search NVIDIA USD library |
| `generate_3d` | `assets.generate_3d` | `text_prompt?, image_url?, position?, scale?` | Generate 3D from text/image (Beaver3D) |

### Simulation Tools (`tools/simulation.py` / `handlers/simulation.py`)

| Tool | Command Type | Params | Description |
|------|-------------|--------|-------------|
| `play` | `simulation.play` | — | Start simulation |
| `pause` | `simulation.pause` | — | Pause simulation |
| `stop` | `simulation.stop` | — | Stop simulation |
| `step` | `simulation.step` | `num_steps?` | Step simulation N frames |
| `set_physics_params` | `simulation.set_physics` | `gravity?, time_step?, gpu_enabled?` | Configure physics engine |
| `execute_script` | `simulation.execute_script` | `code` | Execute arbitrary Python (escape hatch) |

## Migration from Current Code

### What moves where

| Current Location | New Location |
|-----------------|-------------|
| `server.py` IsaacConnection class | `connection.py` |
| `server.py` MCP tool functions | `tools/*.py` (split by category) |
| `server.py` asset_creation_strategy prompt | `server.py` (stays, updated references) |
| `extension.py` MCPExtension._execute_command_internal | `extension.py` registry lookup |
| `extension.py` get_scene_info, create_robot, etc. | `handlers/*.py` (split by category) |
| `extension.py` all `isaacsim.*` imports | `adapters/v5.py` |
| `gen3d.py` | unchanged |
| `usd.py` | unchanged (used by `handlers/assets.py`) |

### Backward Compatibility

The command type format changes from flat strings (`get_scene_info`) to dot notation (`scene.get_info`). This is a breaking change, but since the MCP server and extension are always deployed together, this is acceptable.

## Deferred to Future Versions

- Motion planning (RmpFlow, Lula)
- MJCF import
- Data recording / replay (DataLogger)
- Domain randomization
- Additional Isaac Sim version adapters (4.x, 6.x)
- Heightmap/terrain generation
