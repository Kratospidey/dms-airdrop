import QtQuick
import qs.Common
import qs.Widgets
import qs.Modules.Plugins
import "components"

PopoutComponent {
    id: root
    required property var controller
    property real availableHeight: 700
    property string duration: controller ? controller.pref("duration", "10m") : "10m"
    property bool customDuration: false
    property bool receiveOptions: false
    readonly property bool stackActions: width - Theme.spacingS * 2 < Theme.fontSizeMedium * 23 + Theme.spacingL * 2
    readonly property bool ready: controller !== null && controller !== undefined
    readonly property bool popoutOpen: visible && parentPopout !== null && parentPopout.shouldBeVisible === true
    property var observedController: null
    function syncVisibility() {
        if (observedController && observedController !== controller)
            observedController.setPopoutVisible(root, false);
        observedController = controller && typeof controller.setPopoutVisible === "function" ? controller : null;
        if (observedController) observedController.setPopoutVisible(root, popoutOpen);
    }
    onPopoutOpenChanged: syncVisibility()
    onControllerChanged: syncVisibility()
    headerText: "AirDrop"
    detailsText: "Share files with nearby Apple devices"
    showCloseButton: true
    Component.onCompleted: syncVisibility()
    Component.onDestruction: { if (observedController) observedController.setPopoutVisible(root, false); }

    DankFlickable {
        id: scroll
        objectName: "airDropScroll"
        width: parent.width
        height: Math.min(body.implicitHeight + Theme.spacingM, Math.max(Theme.iconSizeLarge, root.availableHeight - root.headerHeight - root.detailsHeight))
        contentWidth: width
        contentHeight: body.implicitHeight + Theme.spacingM
        clip: true
        Column {
            id: body
            width: parent.width - Theme.spacingS * 2
            x: Theme.spacingS
            spacing: Theme.spacingM

            Rectangle {
                width: parent.width
                height: statusRow.implicitHeight + Theme.spacingM * 2
                radius: Theme.cornerRadius
                color: Theme.surfaceContainer
                Row {
                    id: statusRow
                    x: Theme.spacingM
                    y: Theme.spacingM
                    width: parent.width - Theme.spacingM * 2
                    spacing: Theme.spacingM
                    DankIcon {
                        id: statusIcon
                        name: root.ready && controller.active ? "wifi_tethering" : "wifi_tethering"
                        size: Theme.iconSizeLarge
                        color: root.ready && controller.active ? Theme.primary : Theme.surfaceVariantText
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Column {
                        width: parent.width - statusIcon.width - parent.spacing
                        StyledText {
                            text: root.ready ? controller.statusLabel : "Checking AirDrop status"
                            width: parent.width
                            wrapMode: Text.Wrap
                            font.pixelSize: Theme.fontSizeMedium
                            font.weight: Font.Medium
                            color: Theme.surfaceText
                        }
                        DetailText {
                            text: !root.ready ? "Checking backend availability"
                                : controller.state === "UNAVAILABLE" ? "Set up Omdrop and a compatible radio backend"
                                : controller.active ? controller.timeLabel
                                : controller.state === "OFF" ? "Ready to send or receive"
                                : "Check status before starting a transfer"
                        }
                    }
                }
            }
            DetailText {
                visible: root.ready && (!controller.snapshot.ok || controller.error !== "" || controller.state === "ERROR")
                text: controller?.error || controller?.snapshot.error || "The receiver and radio disagree. Refresh status or check diagnostics."
                color: Theme.error
            }
            DankButton {
                visible: root.ready && ((!controller.snapshot.ok && !!controller.snapshot.error) || controller.error.indexOf("picker") >= 0)
                text: "Setup guide"
                iconName: "help_outline"
                onClicked: Qt.openUrlExternally("https://github.com/Kratospidey/dms-airdrop/blob/main/docs/MARKETPLACE.md")
            }
            Flow {
                width: parent.width
                spacing: Theme.spacingS
                DankButton {
                    width: root.stackActions ? parent.width : (parent.width - parent.spacing) / 2
                    text: controller?.pickerState === "opening" ? "Opening picker…" : controller?.pickerActive ? "Show file picker" : controller?.selecting ? "Checking files…" : controller?.selectedFiles.length > 0 ? "Change Files" : "Send Files"
                    iconName: "upload"
                    enabled: root.ready && controller.canPickFiles
                    onClicked: controller.pickFiles()
                }
                DankButton {
                    width: root.stackActions ? parent.width : (parent.width - parent.spacing) / 2
                    text: root.ready && controller.active ? "Turn Off" : "Receive Files"
                    iconName: root.ready && controller.active ? "stop" : "download"
                    enabled: root.ready && controller.canAct
                    onClicked: {
                        if (controller.active) controller.stop();
                        else controller.receive(root.customDuration ? customMinutes.text + "m" : root.duration);
                    }
                }
            }
            DetailText {
                visible: root.ready && controller.pickerActive
                text: "Choose files in the separate window. If it is hidden, use Show file picker, or cancel and try again."
            }
            DankButton {
                visible: root.ready && controller.pickerActive
                text: "Cancel file selection"
                onClicked: controller.cancelPicker()
            }
            DetailText {
                visible: root.ready && !controller.canPickFiles && controller.state !== "SENDING"
                text: controller.selecting ? "Checking the selected files…" : "Wait for the current AirDrop operation before choosing files."
            }
            DetailText {
                visible: root.ready && controller.state === "SENDING"
                text: controller.snapshot.external_send && !controller.snapshot.busy ? "A transfer started outside this plugin is running. Stop is unavailable until it finishes." : "You can close this popout. The transfer will continue."
            }
            Flow {
                width: parent.width
                spacing: Theme.spacingS
                DankButton {
                    width: root.stackActions ? parent.width : (parent.width - parent.spacing) / 2
                    text: "Receiving options"
                    backgroundColor: Theme.surfaceContainerHigh
                    textColor: Theme.surfaceText
                    onClicked: root.receiveOptions = !root.receiveOptions
                }
                DankButton {
                    width: root.stackActions ? parent.width : (parent.width - parent.spacing) / 2
                    text: "Downloads"
                    iconName: "folder_open"
                    backgroundColor: Theme.surfaceContainerHigh
                    textColor: Theme.surfaceText
                    enabled: root.ready && !!controller.backend.dir
                    onClicked: controller.openDownloads()
                }
            }
            DetailText {
                visible: root.receiveOptions && root.stackActions
                text: "Receiving window"
            }
            DankDropdown {
                visible: root.receiveOptions
                width: parent.width
                text: root.stackActions ? "" : "Receiving window"
                dropdownWidth: root.stackActions ? width : Theme.iconSize * 8 + Theme.spacingS
                options: ["10 minutes", "Receive once", "30 minutes", "Custom duration"]
                currentValue: root.customDuration ? "Custom duration" : root.duration === "once" ? "Receive once" : root.duration === "30m" ? "30 minutes" : "10 minutes"
                enabled: root.ready && controller.canAct
                onValueChanged: value => {
                    root.customDuration = value === "Custom duration";
                    root.duration = value === "Receive once" ? "once" : value === "30 minutes" ? "30m" : "10m";
                }
            }
            DankTextField {
                id: customMinutes
                width: parent.width
                visible: root.receiveOptions && root.customDuration
                text: "10"
                labelText: "Minutes (1–60)"
                maximumLength: 2
                validator: IntValidator { bottom: 1; top: 60 }
            }
            DankButton {
                visible: root.receiveOptions && root.ready && controller.active && !controller.busy
                text: "Start selected window"
                iconName: "more_time"
                enabled: root.ready && controller.canAct
                onClicked: controller.receive(root.customDuration ? customMinutes.text + "m" : root.duration)
            }
            DetailText {
                visible: root.ready && controller.active
                text: (controller?.backend.visible ? "Visible as " : "Device name: ") + (controller?.backend.name || "name unavailable") + "\n"
                    + (controller?.backend.visibility === "everyone" ? (controller?.backend.visible ? "Everyone nearby can send" : "Visibility setting: Everyone") : "Contacts Only · not verified with this identity")
                    + (controller?.backend.receiving && !controller?.backend.visible ? "\nReceiver is listening, but this device is not discoverable." : "")
            }
            DetailText {
                visible: root.receiveOptions && root.ready && !!controller.backend.dir && !controller.pref("compact", false)
                text: "Downloads: " + (controller?.backend.dir || "Unknown")
                elide: Text.ElideMiddle
                maximumLineCount: 2
            }
            Rectangle { width: parent.width; height: 1; color: Theme.outline; opacity: 0.25 }
            StyledText {
                text: "Nearby devices"
                font.pixelSize: Theme.fontSizeMedium
                font.weight: Font.Medium
                color: Theme.surfaceText
            }
            DetailText {
                visible: root.ready && controller.selectedFiles.length > 0
                text: controller?.selectionSummary || ""
                color: Theme.primary
            }
            DetailText {
                visible: root.ready && controller.selectedFiles.length === 0
                text: "Choose files first, then select a nearby device and send."
            }
            DankButton {
                visible: root.ready && controller.selectedFiles.length > 0 && !controller.backend.visible
                text: "Retry discovery"
                enabled: root.ready && controller.canAct
                onClicked: controller.startDiscovery()
            }
            DetailText {
                visible: root.ready && controller.temporarySession
                text: "Temporarily visible while sending. Nearby devices can also send to this computer."
            }
            DetailText {
                visible: root.ready && controller.sessionMessage !== ""
                text: controller?.sessionMessage || ""
                color: Theme.error
            }
            DankButton {
                visible: root.ready && controller.error.indexOf("picker") >= 0 && !controller.pickerActive
                text: "Use basic file picker"
                enabled: root.ready && controller.canPickFiles
                onClicked: controller.useBasicPicker()
            }
            DetailText {
                visible: root.ready && controller.error.indexOf("picker") >= 0 && !controller.pickerActive
                text: "The optional KDE picker is unavailable. Use the basic picker, or open the setup guide to enable thumbnails."
            }
            DetailText {
                visible: !root.ready || !controller.active || controller.peerMessage !== "" || (!controller.peers.length && !controller.scanning)
                text: !root.ready || !controller.active ? "Choose files to find nearby devices automatically."
                    : controller.peerMessage || "Open AirDrop on the receiving device, then refresh."
            }
            DetailText {
                visible: root.ready && controller.scanning
                text: "Looking for nearby devices…"
            }
            Flow {
                spacing: Theme.spacingS
                width: parent.width
                DankButton {
                    width: root.stackActions ? parent.width : (parent.width - parent.spacing) / 2
                    text: "Refresh"
                    iconName: "refresh"
                    enabled: root.ready && controller.canAct && controller.backend.visible === true && !controller.scanning
                    onClicked: controller.discover()
                }
                DankButton {
                    width: root.stackActions ? parent.width : (parent.width - parent.spacing) / 2
                    text: "Resolve names"
                    enabled: root.ready && controller.canAct && controller.backend.visible === true && !controller.scanning && controller.now - controller.lastNames >= 30000
                    onClicked: controller.resolveNames()
                }
            }
            DetailText {
                visible: root.ready && controller.active && !controller.pref("compact", false)
                text: "Can't identify your iPhone? Resolve names, or open its AirDrop sharing screen."
            }
            Repeater {
                model: root.ready ? controller.peers : []
                DeviceRow {
                    required property var modelData
                    peer: modelData
                    selected: root.ready && controller.selectedPeer === peer.mac
                    enabled: root.ready && controller.canAct && controller.now - controller.peersAt < 15000
                    onChosen: controller.selectedPeer = peer.mac
                }
            }
            DetailText {
                visible: root.ready && controller.peers.length > 0 && controller.now - controller.peersAt >= 15000
                text: "This device list is stale. Refresh before selecting a recipient."
            }
            Flow {
                width: parent.width
                visible: root.ready && controller.selectedFiles.length > 0
                spacing: Theme.spacingS
                DankButton {
                    text: "Send to device"
                    iconName: "send"
                    enabled: root.ready && controller.canSend
                    onClicked: controller.send()
                }
                DankButton { text: "Cancel"; enabled: !controller.busy; onClicked: controller.clearSelection() }
            }
            DetailText {
                visible: root.ready && controller.selectedFiles.length > 0
                text: controller?.backend.mode === "once" ? "Receive Once must finish or be turned off before sending."
                    : controller?.temporarySession ? "Your selection expires after 5 minutes. Transfers must finish before the displayed window expires."
                    : "Your current receiving window is preserved. Its expiry can interrupt a long transfer."
            }
            Rectangle {
                visible: root.ready && (controller.busy || controller.showResult)
                width: parent.width
                height: transfer.implicitHeight + Theme.spacingM * 2
                radius: Theme.cornerRadius
                color: Theme.surfaceContainer
                Column {
                    id: transfer
                    x: Theme.spacingM
                    y: Theme.spacingM
                    width: parent.width - Theme.spacingM * 2
                    spacing: Theme.spacingS
                    DetailText {
                        color: Theme.primary
                        text: controller?.pending || controller?.state === "CLEANING" ? controller.statusLabel : controller?.job.phase || controller?.statusLabel || "Working"
                        font.weight: Font.Medium
                    }
                    DetailText {
                        visible: !controller?.pending && (controller?.job.count || 0) > 0
                        text: (controller?.job.count || 0) + " file(s) · " + (controller?.job.destination || "Selected device")
                    }
                    Rectangle {
                        width: parent.width
                        height: Theme.spacingXS
                        radius: Math.min(Theme.cornerRadius, height / 2)
                        visible: root.ready && controller.busy
                        color: Theme.surfaceContainerHigh
                        clip: true
                        Rectangle {
                            width: parent.width / 3
                            height: parent.height
                            color: Theme.primary
                            SequentialAnimation on x {
                                running: root.ready && controller.busy && root.popoutOpen
                                loops: Animation.Infinite
                                NumberAnimation { from: 0; to: transfer.width * 2 / 3; duration: 850; easing.type: Easing.InOutQuad }
                                NumberAnimation { from: transfer.width * 2 / 3; to: 0; duration: 850; easing.type: Easing.InOutQuad }
                            }
                        }
                    }
                    DetailText {
                        visible: root.ready && !controller.busy
                        text: controller?.job.message || ""
                        color: controller?.job.state === "complete" ? Theme.surfaceText : Theme.error
                    }
                    Flow {
                        width: parent.width
                        visible: root.ready && !controller.busy
                        spacing: Theme.spacingS
                        DankButton {
                            text: "Dismiss"
                            onClicked: controller.dismissedId = controller.job.id
                        }
                        DankButton {
                            visible: controller?.job.action === "send" && controller?.job.state !== "complete"
                            text: "Choose files again"
                            enabled: root.ready && controller.canPickFiles
                            onClicked: controller.pickFiles()
                        }
                    }
                }
            }
            Flow {
                width: parent.width
                spacing: Theme.spacingS
                DankButton { text: "Check status"; enabled: root.ready; onClicked: controller.refresh() }
                DankButton { text: "Diagnostics"; enabled: root.ready; onClicked: controller.diagnose() }
            }
            DetailText {
                visible: root.ready && controller.diagnostics !== null
                text: !controller?.diagnostics?.ok ? controller?.diagnostics?.error || "" : "Backend: " + controller.diagnostics.backend + "\n"
                    + (controller.diagnostics.issues.length ? controller.diagnostics.issues.join("\n") : "No prerequisite problem reported.") + "\n" + controller.diagnostics.note
            }
        }
    }
}
