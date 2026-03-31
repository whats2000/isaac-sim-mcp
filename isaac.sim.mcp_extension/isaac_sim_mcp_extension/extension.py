"""Isaac Sim MCP Extension — slim entry point.

Routes incoming socket commands to handler modules via a registry.
"""

import gc
import json
import socket
import threading
import time
import traceback

import carb
import omni.ext
import omni.usd

from .adapters import get_adapter
from .handlers import register_all_handlers


class MCPExtension(omni.ext.IExt):

    def __init__(self):
        super().__init__()
        self.ext_id = None
        self.running = False
        self.host = None
        self.port = None
        self._socket = None
        self._server_thread = None
        self._settings = carb.settings.get_settings()
        self._registry = {}
        self._adapter = None

    def on_startup(self, ext_id: str):
        print("trigger  on_startup for: ", ext_id)
        self.ext_id = ext_id
        self.port = self._settings.get("/exts/isaac.sim.mcp/server.port") or 8766
        self.host = self._settings.get("/exts/isaac.sim.mcp/server.host") or "localhost"

        # Initialize adapter and register handlers
        self._adapter = get_adapter()
        register_all_handlers(self._registry, self._adapter)
        print(f"Registered {len(self._registry)} command handlers")

        self._start_server()

    def on_shutdown(self):
        print("trigger  on_shutdown for: ", self.ext_id)
        self._stop_server()
        self._registry.clear()
        gc.collect()

    # ── Server lifecycle ───────────────────────────────────

    def _start_server(self):
        if self.running:
            return
        self.running = True
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._socket.bind((self.host, self.port))
            self._socket.listen(1)
            self._server_thread = threading.Thread(target=self._server_loop, daemon=True)
            self._server_thread.start()
            print(f"Isaac Sim MCP server started on {self.host}:{self.port}")
        except Exception as e:
            print(f"Failed to start server: {e}")
            self._stop_server()

    def _stop_server(self):
        self.running = False
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None
        if self._server_thread and self._server_thread.is_alive():
            self._server_thread.join(timeout=1.0)
        self._server_thread = None
        print("Isaac Sim MCP server stopped")

    # ── Connection handling ────────────────────────────────

    def _server_loop(self):
        self._socket.settimeout(1.0)
        while self.running:
            try:
                client, address = self._socket.accept()
                print(f"Connected to client: {address}")
                threading.Thread(target=self._handle_client, args=(client,), daemon=True).start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"Error accepting connection: {e}")
                    time.sleep(0.5)

    def _handle_client(self, client):
        client.settimeout(None)
        buffer = b""
        try:
            while self.running:
                data = client.recv(16384)
                if not data:
                    break
                buffer += data
                try:
                    command = json.loads(buffer.decode("utf-8"))
                    buffer = b""
                    self._dispatch_command(client, command)
                except json.JSONDecodeError:
                    continue
        except Exception as e:
            print(f"Error in client handler: {e}")
        finally:
            client.close()

    def _dispatch_command(self, client, command):
        async def execute_wrapper():
            try:
                response = self._execute_command(command)
                response_json = json.dumps(response)
                try:
                    client.sendall(response_json.encode("utf-8"))
                except Exception:
                    print("Failed to send response — client disconnected")
            except Exception as e:
                traceback.print_exc()
                try:
                    client.sendall(json.dumps({"status": "error", "message": str(e)}).encode("utf-8"))
                except Exception:
                    pass

        from omni.kit.async_engine import run_coroutine
        run_coroutine(execute_wrapper())

    # ── Command routing ────────────────────────────────────

    def _execute_command(self, command):
        cmd_type = command.get("type", "")
        params = command.get("params", {})
        handler = self._registry.get(cmd_type)
        if handler:
            try:
                result = handler(**params)
                if result and result.get("status") == "success":
                    return {"status": "success", "result": result}
                else:
                    return {"status": "error", "message": result.get("message", "Unknown error") if result else "No result"}
            except Exception as e:
                traceback.print_exc()
                return {"status": "error", "message": str(e)}
        return {"status": "error", "message": f"Unknown command: {cmd_type}"}
