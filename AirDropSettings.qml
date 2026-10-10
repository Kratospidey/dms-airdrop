import QtQuick
import qs.Common
import qs.Widgets
import qs.Modules.Plugins
import "components"

PluginSettings {
    id: root
    pluginId: "dmsAirDrop"
    readonly property var controller: pluginService?.globalVars?.[pluginId]?.controller || null
    readonly property bool editable: controller && controller.canAct && !controller.active

    DetailText {
        text: "AirDrop uses your existing Omdrop installation. Enable the plugin to read its current configuration. Device settings can be changed only while AirDrop is off."
    }
    SelectionSetting {
        settingKey: "filePicker"
        label: "File picker"
        description: "Auto prefers the KDE thumbnail picker when available. Auto and KDE use Basic if the enhanced picker is unavailable or fails. Basic always uses the standard dialog."
        defaultValue: "auto"
        options: [{label: "Auto (recommended)", value: "auto"}, {label: "KDE enhanced picker", value: "kde"}, {label: "Basic picker", value: "basic"}]
    }
    SelectionSetting {
        settingKey: "duration"
        label: "Default receiving window"
        defaultValue: "10m"
        options: [{label: "10 minutes", value: "10m"}, {label: "Receive once", value: "once"}, {label: "30 minutes", value: "30m"}]
    }
    DankTextField {
        id: deviceName
        width: parent.width
        text: root.controller?.backend.name || ""
        labelText: "Device name"
        maximumLength: 63
        enabled: root.editable
    }
    DankButton {
        text: "Apply device name"
        enabled: root.editable && deviceName.text.trim().length > 0 && deviceName.text !== root.controller.backend.name
        onClicked: root.controller.act("name", {name: deviceName.text})
    }
    DetailText {
        text: "Download folder: " + (root.controller?.backend.dir || "Checking…")
            + "\nChanging the folder through Omdrop rewrites a receiver service drop-in. Folder changes are unavailable to preserve your existing service."
    }
    DankButton { text: "Open Downloads"; enabled: !!root.controller; onClicked: root.controller.openDownloads() }
    DetailText {
        text: "Visibility: " + (root.controller?.backend.visibility || "Checking…")
            + "\nEveryone is the verified mode for this self-signed identity. Contacts Only depends on Apple identity capabilities and is not offered here."
    }
    DankButton {
        text: "Use Everyone"
        enabled: root.editable && root.controller.backend.visibility !== "everyone"
        onClicked: root.controller.act("everyone")
    }
    DetailText {
        visible: !!root.controller?.error || root.controller?.job.state === "failed"
        color: Theme.error
        text: root.controller?.error || root.controller?.job.message || ""
    }
    ToggleSetting { settingKey: "iconOnly"; label: "Icon-only bar"; defaultValue: true }
    ToggleSetting { settingKey: "showTime"; label: "Show remaining time beside the icon"; description: "Used on horizontal bars when icon-only mode is off."; defaultValue: true }
    ToggleSetting { settingKey: "compact"; label: "Compact details"; defaultValue: false }
    ToggleSetting { settingKey: "rightClickToggle"; label: "Right-click toggles receiving"; description: "Off by default. Left-click always opens the popout."; defaultValue: false }
    ToggleSetting { settingKey: "notifyResults"; label: "Transfer and operation result notifications"; defaultValue: true }
    ToggleSetting { settingKey: "notifyExpiry"; label: "Notify when the receiving window closes"; defaultValue: false }
    DetailText { text: "Incoming-file notifications are already provided by Omdrop's receiver watcher. The plugin does not duplicate them or watch arbitrary files in Downloads." }
    SelectionSetting {
        settingKey: "openInterval"
        label: "Open popout status refresh"
        description: "Opening refreshes immediately. Receiving refreshes every 3 seconds while open, or 30 seconds in the background. Operations stay fast; closed and Off checks every 5 minutes."
        defaultValue: "15"
        options: [{label: "10 seconds", value: "10"}, {label: "15 seconds", value: "15"}, {label: "30 seconds", value: "30"}, {label: "60 seconds", value: "60"}]
    }
    DetailText { text: "Nearby devices refresh automatically every 5 seconds while files are selected. Device names are resolved only when requested." }
    DankButton { text: "Run read-only diagnostics"; enabled: !!root.controller; onClicked: root.controller.diagnose() }
    DetailText {
        visible: root.controller?.diagnostics !== null && root.controller?.diagnostics !== undefined
        text: root.controller?.diagnostics?.ok ? (root.controller.diagnostics.issues.join("\n") || "No prerequisite problem reported.") + "\n" + root.controller.diagnostics.note : root.controller?.diagnostics?.error || ""
    }
}
