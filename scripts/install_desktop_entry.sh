#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ISAACSIM_ROOT="${ISAACSIM_ROOT:-$HOME/isaacsim}"
DESKTOP_FILE="$HOME/.local/share/applications/IsaacSimMCP.desktop"
LAUNCHER="$REPO_ROOT/scripts/launch_isaac_sim_mcp.sh"
ICON="$ISAACSIM_ROOT/exts/isaacsim.app.setup/data/omni.isaac.sim.png"

# --- Validate ---
if [[ ! -x "$LAUNCHER" ]]; then
  echo "Error: Launcher script not found at: $LAUNCHER" >&2
  exit 1
fi

if [[ ! -f "$ICON" ]]; then
  echo "Warning: Icon not found at: $ICON — using default." >&2
  ICON="application-x-executable"
fi

# --- Write desktop entry ---
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Version=1.0
Name=Isaac Sim MCP
Comment=Launch Isaac Sim with MCP extension and server
Exec=$LAUNCHER
Icon=$ICON
Terminal=false
Type=Application
Categories=Development;Simulation;
EOF

echo "Desktop entry installed: $DESKTOP_FILE"
echo ""
echo "You now have two application icons:"
echo "  - Isaac Sim       (original, unchanged)"
echo "  - Isaac Sim MCP   (launches with MCP extension + server)"
echo ""
echo "To uninstall: rm $DESKTOP_FILE"
