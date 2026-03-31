"""Isaac Sim MCP Extension — slim entry point.

Routes incoming socket commands to handler modules via a registry.
"""

from __future__ import annotations

import gc
import traceback
from typing import Any, Dict

import carb
import omni.ext
import omni.usd

from .adapters import get_adapter
from .handlers import register_all_handlers
from .socket_server import SocketServer


class MCPExtension(omni.ext.IExt):

    def __init__(self):
        super().__init__()
        self.ext_id = None
        self._settings = carb.settings.get_settings()
        self._registry: Dict[str, Any] = {}
        self._adapter = None
        self._server: SocketServer | None = None

    def on_startup(self, ext_id: str) -> None:
        print("trigger  on_startup for: ", ext_id)
        self.ext_id = ext_id
        port = self._settings.get("/exts/isaac.sim.mcp/server.port") or 8766
        host = self._settings.get("/exts/isaac.sim.mcp/server.host") or "localhost"

        self._adapter = get_adapter()
        register_all_handlers(self._registry, self._adapter)
        print(f"Registered {len(self._registry)} command handlers")

        self._server = SocketServer(host, port, self._execute_command)
        self._server.start()

    def on_shutdown(self) -> None:
        print("trigger  on_shutdown for: ", self.ext_id)
        if self._server:
            self._server.stop()
        self._registry.clear()
        gc.collect()

    # ── Command routing ────────────────────────────────────────────────────────

    def _execute_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        cmd_type = command.get("type", "")
        params = command.get("params", {})
        handler = self._registry.get(cmd_type)
        if handler:
            try:
                result = handler(**params)
                if result and result.get("status") == "success":
                    return {"status": "success", "result": result}
                else:
                    return {
                        "status": "error",
                        "message": result.get("message", "Unknown error") if result else "No result",
                    }
            except Exception as e:
                traceback.print_exc()
                return {"status": "error", "message": str(e)}
        return {"status": "error", "message": f"Unknown command: {cmd_type}"}
