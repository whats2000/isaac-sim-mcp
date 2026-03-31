"""Shared type definitions for the Isaac Sim MCP extension.

Follows Isaac Sim's convention of plain Python classes for structured data.
"""

from typing import Any, Dict, List, Optional


class CommandResult(object):
    """Result returned by all command handlers."""

    def __init__(
        self,
        status: str = "success",
        message: str = "",
        **kwargs: Any,
    ) -> None:
        self.status = status
        self.message = message
        for key, value in kwargs.items():
            setattr(self, key, value)

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None}

    @staticmethod
    def success(message: str = "", **kwargs: Any) -> "CommandResult":
        return CommandResult(status="success", message=message, **kwargs)

    @staticmethod
    def error(message: str = "", error_type: str = "runtime_error") -> "CommandResult":
        return CommandResult(status="error", message=message, error_type=error_type)


class PrimInfo(object):
    """Information about a USD prim."""

    def __init__(
        self,
        path: str = "",
        prim_type: str = "",
        transform: Optional[Dict[str, Any]] = None,
        children: Optional[List[str]] = None,
    ) -> None:
        self.path = path
        self.prim_type = prim_type
        self.transform = transform
        self.children = children or []

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None}


class RobotInfo(object):
    """Information about a robot articulation."""

    def __init__(
        self,
        joint_names: Optional[List[str]] = None,
        num_dof: int = 0,
        joint_positions: Optional[List[float]] = None,
    ) -> None:
        self.joint_names = joint_names or []
        self.num_dof = num_dof
        self.joint_positions = joint_positions

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None}
