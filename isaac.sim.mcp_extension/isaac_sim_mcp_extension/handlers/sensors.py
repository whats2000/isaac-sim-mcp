"""Sensor creation and data capture command handlers."""
from __future__ import annotations

import base64
import os
from typing import Any, Dict, Optional, Sequence

from ..adapters.base import IsaacAdapterBase


def register(registry: Dict[str, Any], adapter: IsaacAdapterBase) -> None:
    registry["sensors.create_camera"] = lambda **p: create_camera(adapter, **p)
    registry["sensors.capture_image"] = lambda **p: capture_image(adapter, **p)
    registry["sensors.create_lidar"] = lambda **p: create_lidar(adapter, **p)
    registry["sensors.get_point_cloud"] = lambda **p: get_point_cloud(adapter, **p)


def create_camera(adapter: IsaacAdapterBase, prim_path: str = "/World/Camera", position: Optional[Sequence[float]] = None, rotation: Optional[Sequence[float]] = None, resolution: Optional[Sequence[int]] = None) -> Dict[str, Any]:
    try:
        res = tuple(resolution) if resolution else (1280, 720)
        cam = adapter.create_camera(prim_path, resolution=res)
        if position or rotation:
            adapter.set_prim_transform(prim_path, position=position, rotation=rotation)
        return {"status": "success", "message": f"Camera created at {prim_path}", "prim_path": prim_path}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def capture_image(adapter: IsaacAdapterBase, prim_path: str = "/World/Camera", output_path: Optional[str] = None) -> Dict[str, Any]:
    try:
        image_data = adapter.capture_camera_image(prim_path)
        if output_path:
            import numpy as np
            from PIL import Image
            img = Image.fromarray(image_data)
            img.save(output_path)
            return {"status": "success", "message": f"Image saved to {output_path}", "output_path": output_path}
        return {"status": "success", "message": "Image captured", "shape": list(image_data.shape) if hasattr(image_data, "shape") else None}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def create_lidar(adapter: IsaacAdapterBase, prim_path: str = "/World/Lidar", position: Optional[Sequence[float]] = None, rotation: Optional[Sequence[float]] = None, config: Optional[str] = None) -> Dict[str, Any]:
    try:
        adapter.create_lidar(prim_path, config=config)
        if position or rotation:
            adapter.set_prim_transform(prim_path, position=position, rotation=rotation)
        return {"status": "success", "message": f"Lidar created at {prim_path}", "prim_path": prim_path}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_point_cloud(adapter: IsaacAdapterBase, prim_path: str = "/World/Lidar") -> Dict[str, Any]:
    try:
        pc = adapter.get_lidar_point_cloud(prim_path)
        point_count = len(pc) if pc is not None else 0
        return {"status": "success", "message": f"Got {point_count} points", "point_count": point_count}
    except Exception as e:
        return {"status": "error", "message": str(e)}
