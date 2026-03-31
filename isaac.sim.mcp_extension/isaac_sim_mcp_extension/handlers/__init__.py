"""Command handler modules for the Isaac Sim extension."""
from __future__ import annotations

from typing import Any, Dict

from ..adapters.base import IsaacAdapterBase


def register_all_handlers(registry: Dict[str, Any], adapter: IsaacAdapterBase) -> None:
    """Register all command handlers from submodules.

    Args:
        registry: Dict mapping command type strings to handler callables.
        adapter: IsaacAdapterBase instance for version-specific API calls.
    """
    from . import scene, objects, lighting, robots, sensors, materials, assets, simulation

    for module in [scene, objects, lighting, robots, sensors, materials, assets, simulation]:
        module.register(registry, adapter)
