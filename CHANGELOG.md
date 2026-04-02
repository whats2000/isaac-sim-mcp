# Changelog

All notable changes to the isaacsim-mcp-server project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Updated package name and version in extension.toml
- Added new application icon and social badge image

## [0.4.1] - 2026-04-02

### Changed
- Added MCP registry metadata (`server.json`) for marketplace listing
- Fixed demo GIF URL in README to use absolute GitHub raw URL

## [0.4.0] - 2026-04-02

### Added
- **Observability tools**: `get_simulation_state`, `get_physics_state`, `get_joint_config`, `get_isaac_logs`, `reload_script`
- **Step-and-observe**: `observe` parameters on `step_simulation` for combined stepping and inspection (issue #8)
- `cwd` parameter and stdout/stderr capture for `execute_script`
- Franka pick-and-place demo scene and USD file
- Development wrapper for MCP server with hot-reloading support
- Environment discovery and loading tools
- Dynamic robot discovery from Isaac Sim asset server
- PyPI packaging via `pyproject.toml` — installable with `pip install isaacsim-mcp-server`
- Tag-triggered PyPI publish and GitHub Release CD pipeline
- Smithery registry manifest
- CI lint and format checks on PRs (ruff)
- Desktop launcher instructions and scripts
- Documentation for running multiple Isaac Sim instances with MCP

### Changed
- **Renamed package** from `isaac-sim-mcp` to `isaacsim-mcp-server` across all references
- Complete modular architecture rewrite:
  - Extracted `IsaacConnection` into dedicated connection module
  - Added adapter layer with base ABC and v5 implementation
  - Split into 8 handler modules with 31+ command handlers
  - Split into 8 MCP tool modules with 31+ tools
  - Rewrote `server.py` as slim entry point using modular tools
  - Rewrote `extension.py` as slim registry-based command router
  - Extracted socket server from `extension.py`
- Added type hints across all handler, adapter, and connection modules
- Migrated all imports from `omni.isaac.*` to `isaacsim.*` for Isaac Sim 5.1.0 compatibility
- Refreshed project documentation to reflect the current Isaac Sim `5.1.0`-focused architecture
- Reworked the README with a clearer quickstart, architecture overview, and example prompting workflow
- Updated build scripts to use installed `isaacsim-mcp-server` CLI
- Added MIT License to all source files; updated copyright headers for fork continuation
- Now documents `39` MCP tools across `8` categories

### Fixed
- Correct argument order in `set_channel_enabled` (issue #2 bug 1)
- Use PhysX velocity API for accurate runtime readings (issue #2 bug 2)
- Read runtime joint targets from articulation controller (issue #2 bug 3)
- Flatten `execute_script` and `reload_script` response structure (issue #2 bug 4)
- Use `add_message_consumer` API for Isaac Sim 5.1 log listener
- Compare log level enum by value for Isaac Sim 5.1 compatibility
- Use USD `RigidBodyAPI` velocity attrs instead of missing PhysX methods
- Initialize `SingleArticulation` before accessing controller APIs
- `scene.clear` now removes all user prims including root-level ones
- Fix transform precision conflict and URDF file validation
- Remove dead code and fix adapter bypass in handlers

### Tests
- Added 43 integration tests for all tool categories
- Updated structural tests for new observability methods

## [0.3.0] - 2025-04-22

### Added
- USD asset search integration with `search_3d_usd_by_text` tool
- Ability to search and load pre-existing 3D models from USD libraries
- Support for custom positioning and scaling of USD models
- Direct model transformation capabilities with the improved `transform` tool
- Enhanced scene management with multi-object placement

### Improved
- Scene object manipulation with precise positioning controls
- Asset loading performance and reliability
- Error handling for model search and placement
- Integration with existing physics scene management

### Technical Details
- Advanced USD model retrieval system
- Optimized asset loading pipeline
- Position and scale customization for USD models
- Better compatibility with Isaac Sim's native USD handling

## [0.2.1] - 2025-04-15

### Added
- Beaver3D integration for 3D model generation from text prompts and images
- Asynchronous model loading with asyncio support
- Task caching system to prevent duplicate model generation
- New MCP tools:
  - `generate_3d_from_text_or_image` for AI-powered 3D asset creation
  - `transform` for manipulating generated 3D models in the scene
- Texture and material binding for generated 3D models

### Improved
- Asynchronous command execution with `run_coroutine`
- Error handling and reporting for 3D generation tasks
- Performance optimizations for model loading

### Technical Details
- Integration with Beaver3D API for 3D generation
- Task monitoring with callback support
- Position and scale customization for generated models

## [0.1.0] - 2025-04-02

### Added
- Initial implementation of Isaac Sim MCP Extension
- Natural language control interface for Isaac Sim through MCP framework
- Core robot manipulation capabilities:
  - Dynamic placement and positioning of robots (Franka, G1, Go1, Jetbot)
  - Robot movement controls with position updates
  - Multi-robot grid creation (3x3 arrangement support)
- Advanced simulation features:
  - Quadruped robot walking simulation with waypoint navigation
  - Physics-based interactions between robots and environment
  - Custom lighting controls for better scene visualization
- Environment enrichment:
  - Various obstacle types: boxes, spheres, cylinders, cones
  - Wall creation for maze-like environments
  - Dynamic obstacle placement with customizable properties
- Development tools:
  - MCP server integration with Cursor AI
  - Debug interface accessible via local web server
  - Connection status verification with `get_scene_info`
- Documentation:
  - Installation instructions
  - Example prompts for common simulation scenarios
  - Configuration guidelines

### Technical Details
- Extension server running on localhost:8766
- Compatible with NVIDIA Isaac Sim 4.2.0
- Support for Python 3.9+
- MIT License for open development 
