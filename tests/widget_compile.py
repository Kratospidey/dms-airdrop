#!/usr/bin/env python3
"""Compile the widget against installed DMS plugin base types without loading it."""
import os
from pathlib import Path
import subprocess

from preview import prepare, environment, write, link
from support import dms_source

shell = prepare()
dms = dms_source()
for name in ("PluginComponent", "PluginPopout", "BasePill"):
    link(dms / f"Modules/Plugins/{name}.qml", shell / f"Modules/Plugins/{name}.qml")
link(dms / "Common/SpringMotion.qml", shell / "Common/SpringMotion.qml")
link(dms / "Common/ElevationShadow.qml", shell / "Common/ElevationShadow.qml")
link(dms / "Common/DeferredAction.qml", shell / "Common/DeferredAction.qml")
link(dms / "Common/ConnectedSurfaceLease.qml", shell / "Common/ConnectedSurfaceLease.qml")
write(shell / "widget-compile.qml", '''import QtQuick
import Quickshell
import qs.Common
import qs.Widgets
import qs.Modules.Plugins
import "Plugin" as Plugin
ShellRoot {
    Component { id: widgetFactory; Plugin.AirDropWidget {} }
    Timer {
        interval: 100; running: true
        onTriggered: {
            const component = widgetFactory;
            if (component.status === Component.Ready) console.warn("WIDGET_COMPILE_OK");
            else console.warn("WIDGET_COMPILE_FAIL: " + component.errorString());
            Qt.quit();
        }
    }
}''')
env = environment()
# DMS's base class includes PanelWindow declarations, which require a Wayland
# backend even to compile. Only Component factories are created: no widget,
# panel, backend controller or live DMS configuration is instantiated.
display = os.environ.get("WAYLAND_DISPLAY", "")
if not display:
    raise SystemExit("A running Wayland session is needed for native base-type compilation.")
env["QT_QPA_PLATFORM"] = "wayland"
env.pop("QSG_RHI_BACKEND", None)
env["WAYLAND_DISPLAY"] = display if display.startswith("/") else str(Path(os.environ["XDG_RUNTIME_DIR"]) / display)
result = subprocess.run(["qs", "-p", str(shell / "widget-compile.qml"), "--no-color"], env=env, capture_output=True, text=True, timeout=15)
output = result.stdout + result.stderr
print(output)
raise SystemExit(0 if "WIDGET_COMPILE_OK" in output else 1)
