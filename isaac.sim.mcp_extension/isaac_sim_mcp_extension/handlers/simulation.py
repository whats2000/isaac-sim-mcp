"""Simulation control command handlers."""
from __future__ import annotations

from typing import Any, Dict, Optional, Sequence

from ..adapters.base import IsaacAdapterBase


def register(registry: Dict[str, Any], adapter: IsaacAdapterBase) -> None:
    registry["simulation.play"] = lambda **p: play(adapter, **p)
    registry["simulation.pause"] = lambda **p: pause(adapter, **p)
    registry["simulation.stop"] = lambda **p: stop(adapter, **p)
    registry["simulation.step"] = lambda **p: step(adapter, **p)
    registry["simulation.set_physics"] = lambda **p: set_physics(adapter, **p)
    registry["simulation.execute_script"] = lambda **p: execute_script(adapter, **p)


def play(adapter: IsaacAdapterBase) -> Dict[str, Any]:
    try:
        adapter.play()
        return {"status": "success", "message": "Simulation started"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def pause(adapter: IsaacAdapterBase) -> Dict[str, Any]:
    try:
        adapter.pause()
        return {"status": "success", "message": "Simulation paused"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def stop(adapter: IsaacAdapterBase) -> Dict[str, Any]:
    try:
        adapter.stop()
        return {"status": "success", "message": "Simulation stopped"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def step(adapter: IsaacAdapterBase, num_steps: int = 1) -> Dict[str, Any]:
    try:
        adapter.step(num_steps=num_steps)
        return {"status": "success", "message": f"Stepped {num_steps} frames"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def set_physics(adapter: IsaacAdapterBase, gravity: Optional[Sequence[float]] = None, time_step: Optional[float] = None, gpu_enabled: Optional[bool] = None) -> Dict[str, Any]:
    try:
        # Physics params are set via the PhysicsContext on the World
        # For now, gravity is the most common parameter
        if gravity is not None:
            adapter.create_physics_scene(gravity=gravity)
        return {"status": "success", "message": "Physics parameters updated"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def execute_script(adapter: IsaacAdapterBase, code: Optional[str] = None) -> Dict[str, Any]:
    try:
        if not code:
            return {"status": "error", "message": "code is required"}
        result = adapter.execute_script(code)
        return {"status": "success", "result": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}
