"""Lighting command handlers."""
from __future__ import annotations

from typing import Any, Dict, Optional, Sequence

from ..adapters.base import IsaacAdapterBase


def register(registry: Dict[str, Any], adapter: IsaacAdapterBase) -> None:
    registry["lighting.create"] = lambda **p: create(adapter, **p)
    registry["lighting.modify"] = lambda **p: modify(adapter, **p)


def create(adapter: IsaacAdapterBase, light_type: str = "DistantLight", position: Optional[Sequence[float]] = None, intensity: float = 1000.0, color: Optional[Sequence[float]] = None, rotation: Optional[Sequence[float]] = None, prim_path: Optional[str] = None) -> Dict[str, Any]:
    try:
        if not prim_path:
            stage = adapter.get_stage()
            count = len(list(stage.TraverseAll()))
            prim_path = f"/World/{light_type}_{count}"
        adapter.create_light(light_type, prim_path, intensity=intensity, color=color, position=position, rotation=rotation)
        return {"status": "success", "message": f"Created {light_type}", "prim_path": prim_path}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def modify(adapter: IsaacAdapterBase, prim_path: Optional[str] = None, intensity: Optional[float] = None, color: Optional[Sequence[float]] = None) -> Dict[str, Any]:
    try:
        if not prim_path:
            return {"status": "error", "message": "prim_path is required"}
        adapter.modify_light(prim_path, intensity=intensity, color=color)
        return {"status": "success", "message": f"Modified light at {prim_path}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
