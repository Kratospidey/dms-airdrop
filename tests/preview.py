#!/usr/bin/env python3
"""Offscreen preview using installed DMS controls and mock session services.

This never loads the live DMS shell or starts the plugin backend. The Theme
facade supplies a stock light/dark palette; buttons call a mock controller.
"""
import os
from pathlib import Path
import subprocess
import sys
from support import dms_source

ROOT = Path(__file__).resolve().parents[1]
QA = ROOT / ".qa/preview"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def link(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink(): target.unlink()
    target.symlink_to(source)


def prepare():
    dms = dms_source()
    shell = QA / "shell"
    for name in ("home", "runtime", "cache", "config", "data"):
        (QA / name).mkdir(parents=True, exist_ok=True)
    (QA / "runtime").chmod(0o700)
    link(dms / "DankCommon", shell / "DankCommon")
    link(dms / "Widgets", shell / "Widgets")
    link(ROOT, shell / "Plugin")
    for name in ("PopoutComponent", "PluginSettings", "ToggleSetting", "SelectionSetting"):
        link(dms / f"Modules/Plugins/{name}.qml", shell / f"Modules/Plugins/{name}.qml")
    link(dms / "Common/QmlUtils.js", shell / "Common/QmlUtils.js")
    write(shell / "Common/Theme.qml", '''pragma Singleton
import QtQuick
import Quickshell
import qs.DankCommon.Common
Singleton {
    property bool isLightMode: false
    property color primary: isLightMode ? "#6750a4" : "#d0bcff"
    property color primaryText: isLightMode ? "#ffffff" : "#381e72"
    property color surface: isLightMode ? "#fffbfe" : "#141218"
    property color surfaceText: isLightMode ? "#1c1b1f" : "#e6e0e9"
    property color surfaceVariantText: isLightMode ? "#49454f" : "#cac4cf"
    property color surfaceVariant: isLightMode ? "#e7e0ec" : "#49454e"
    property color surfaceContainer: isLightMode ? "#f3edf7" : "#211f24"
    property color surfaceContainerHigh: isLightMode ? "#ece6f0" : "#2b292f"
    property color surfaceContainerHighest: surfaceContainerHigh
    property color outline: isLightMode ? "#79747e" : "#948f99"
    property color error: isLightMode ? "#b3261e" : "#f2b8b5"
    property color errorHover: withAlpha(error, 0.12)
    property int spacingS: 8
    property int spacingXS: 4
    property int spacingM: 12
    property int spacingL: 16
    property int cornerRadius: 16
    property int iconSize: 24
    property int fontSizeSmall: 12
    property int fontSizeMedium: 14
    property int fontSizeLarge: 16
    property int shortDuration: 150
    property int standardEasing: Easing.OutCubic
    property real popupTransparency: 1
    function withAlpha(c, a) { return Qt.rgba(c.r, c.g, c.b, a); }
}''')
    write(shell / "Common/Log.qml", '''pragma Singleton
import Quickshell
Singleton { function scoped(name) { return {warn: function() {}, info: function() {}, error: function() {}}; } }
''')
    write(shell / "Common/I18n.qml", '''pragma Singleton
import Quickshell
Singleton { function tr(s) { return s; } }
''')
    write(shell / "Services/PluginService.qml", '''pragma Singleton
import Quickshell
Singleton {
    property var globalVars: ({})
    property var preferences: ({})
    property var states: ({})
    property var availablePlugins: ({dmsAirDrop: {type: "composite", permissions: ["settings_write"]}})
    signal pluginDataChanged(string pluginId)
    function getPluginVariants(id) { return []; }
    function loadPluginData(id, key, fallback) { return preferences[key] ?? fallback; }
    function savePluginData(id, key, value) { preferences = Object.assign({}, preferences, {[key]: value}); pluginDataChanged(id); }
    function loadPluginState(id, key, fallback) { return states[key] ?? fallback; }
    function savePluginState(id, key, value) { states[key] = value; }
    function getGlobalVar(id, name, fallback) { return globalVars[id]?.[name] ?? fallback; }
    function setGlobalVar(id, name, value) { globalVars = {[id]: {[name]: value}}; }
}''')
    write(shell / "Services/ToastService.qml", '''pragma Singleton
import Quickshell
Singleton {
    property string currentCategory: ""
    property bool toastVisible: false
    property var toastQueue: []
    function stopTimer() {}
    function dismissCategory(c) { if (currentCategory === c) { currentCategory = ""; toastVisible = false; } }
    function showInfo(a, b, command, category) { currentCategory = category || ""; toastVisible = true; console.log("Mock toast", a); }
    function showError(a, b) { console.log("Mock error toast", a); }
}''')
    write(shell / "shell.qml", '''import QtQuick
import Quickshell
import qs.Common
import qs.Services
import qs.DankCommon.Common as Native
import "Plugin" as Plugin
ShellRoot {
    Item {
        id: mock
        property var backend: ({receiving: true, visible: true, remaining: 480, mode: "timed", name: "Demo Laptop", dir: "~/Downloads", visibility: "everyone"})
        property var snapshot: ({ok: true, status: backend, busy: false})
        property var job: ({})
        property string error: ""
        property string state: "RECEIVING"
        property string statusLabel: "Discoverable"
        property string timeLabel: "8m remaining"
        property bool active: true
        property bool busy: false
        property bool canAct: true
        property bool canPickFiles: true
        property bool pickerActive: false
        property bool selecting: false
        property string pickerState: "idle"
        property string selectionSummary: "2 files selected · 2.4 MiB"
        property bool temporarySession: true
        property string sessionMessage: ""
        property bool canSend: true
        property bool scanning: false
        property bool showResult: false
        property var selectedFiles: ["/mock/photo.jpg", "/mock/other.jpg"]
        property string selectedPeer: "aa:bb:cc:dd:ee:ff"
        property var peers: [{mac: "aa:bb:cc:dd:ee:ff", name: "", label: "Apple device · dd:ee:ff"}, {mac: "11:22:33:44:55:66", name: "Test iPhone", label: "Test iPhone"}]
        property double peersAt: Date.now()
        property double now: Date.now()
        property double lastNames: 0
        property string peerMessage: ""
        property var diagnostics: null
        property string dismissedId: ""
        function pref(k, d) { return d; }
        function refresh() {}
        function receive(d) {}
        function stop() {}
        function pickFiles() {}
        function useBasicPicker() {}
        function cancelPicker() {}
        function startDiscovery() {}
        function openDownloads() {}
        function discover() {}
        function resolveNames() {}
        function clearSelection() {}
        function send() {}
        function diagnose() {}
        function act(a, b) {}
    }
    FloatingWindow {
        id: win
        visible: true
        implicitWidth: 840
        implicitHeight: 900
        color: Theme.surface
        Rectangle {
            id: canvas
            anchors.fill: parent
            color: Theme.surface
            Plugin.AirDropPopout { id: popout; x: 20; y: 20; width: 380; availableHeight: 850; controller: mock }
            Flickable {
                x: 430; y: 20; width: 390; height: 860; clip: true
                contentHeight: settings.height
                Plugin.AirDropSettings { id: settings; width: parent.width; pluginService: PluginService }
            }
        }
    }
    Component.onCompleted: {
        Native.Style.theme = Theme;
        PluginService.setGlobalVar("dmsAirDrop", "controller", mock);
    }
    Timer {
        interval: 1200; running: true
        onTriggered: canvas.grabToImage(result => { result.saveToFile("''' + str(QA / 'dark.png') + '''"); Theme.isLightMode = true; lightTimer.start(); })
    }
    Timer {
        id: lightTimer; interval: 600
        onTriggered: canvas.grabToImage(result => { result.saveToFile("''' + str(QA / 'light.png') + '''"); console.warn("PREVIEW_OK"); Qt.quit(); })
    }
}''')
    return shell


def environment():
    return dict(os.environ, HOME=str(QA / "home"), XDG_RUNTIME_DIR=str(QA / "runtime"),
        XDG_CACHE_HOME=str(QA / "cache"), XDG_CONFIG_HOME=str(QA / "config"), XDG_DATA_HOME=str(QA / "data"),
        DBUS_SESSION_BUS_ADDRESS="unix:path=" + str(QA / "no-session-bus"),
        QT_QPA_PLATFORM="offscreen", QT_QPA_PLATFORMTHEME="", QSG_RHI_BACKEND="software")


if __name__ == "__main__":
    shell = prepare()
    result = subprocess.run(["qs", "-p", str(shell), "--no-color"], env=environment(), capture_output=True, text=True, timeout=20)
    print(result.stdout + result.stderr)
    sys.exit(result.returncode if "PREVIEW_OK" in result.stdout + result.stderr else 1)
