"""Command handler modules for the Isaac Sim extension."""


def register_all_handlers(registry, adapter):
    """Register all command handlers from submodules.

    Args:
        registry: Dict mapping command type strings to handler callables.
        adapter: IsaacAdapterBase instance for version-specific API calls.
    """
    from . import scene, objects, lighting, robots, sensors, materials, assets, simulation

    for module in [scene, objects, lighting, robots, sensors, materials, assets, simulation]:
        module.register(registry, adapter)
