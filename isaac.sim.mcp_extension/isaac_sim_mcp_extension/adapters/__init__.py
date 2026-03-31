"""Isaac Sim version adapters."""


def get_adapter():
    """Return the appropriate adapter for the current Isaac Sim version.

    Currently only supports Isaac Sim 5.1.0.
    Future versions will detect the runtime version and return the matching adapter.
    """
    from .v5 import IsaacAdapterV5
    return IsaacAdapterV5()
