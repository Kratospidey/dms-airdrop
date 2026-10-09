import QtQuick
import qs.Common
import qs.Widgets
import qs.Modules.Plugins

PluginComponent {
    id: root
    PluginGlobalVar { id: shared; varName: "controller"; defaultValue: null }
    readonly property var controller: shared.value
    readonly property bool working: controller && controller.busy
    readonly property bool warning: !controller || ["UNKNOWN", "UNAVAILABLE", "ERROR"].includes(controller.state)
    readonly property color tint: warning ? Theme.error : controller.active || working ? Theme.primary : Theme.surfaceVariantText
    readonly property string icon: warning ? "warning" : working ? "sync" : "wifi_tethering"
    readonly property bool showTime: controller && !controller.pref("iconOnly", true) && controller.pref("showTime", true) && controller.active
    popoutWidth: Math.min(400, (parentScreen?.width || 440) - 40)
    popoutContent: Component {
        Loader {
            id: content
            property var closePopout: null
            property var parentPopout: null
            // DMS cache-busts the widget entrypoint, not imported children.
            // Load the popout with its own URL so a plugin reload updates it.
            Component.onCompleted: setSource(Qt.resolvedUrl("AirDropPopout.qml").toString() + "?v=" + Date.now(), {
                controller: Qt.binding(() => root.controller),
                availableHeight: Qt.binding(() => Math.max(220, (root.parentScreen?.height || 900) - 140)),
                closePopout: Qt.binding(() => content.closePopout),
                parentPopout: Qt.binding(() => content.parentPopout)
            })
        }
    }
    pillRightClickAction: () => {
        if (!controller || !controller.pref("rightClickToggle", false) || !controller.canAct) return;
        if (controller.active) controller.stop(); else controller.receive();
    }
    horizontalBarPill: Component {
        Row {
            spacing: Theme.spacingS
            DankIcon {
                name: root.icon
                size: root.iconSize
                color: root.tint
                anchors.verticalCenter: parent.verticalCenter
                RotationAnimator on rotation { from: 0; to: 360; duration: 1600; loops: Animation.Infinite; running: root.working }
            }
            StyledText {
                visible: root.showTime
                text: root.controller?.timeLabel || ""
                color: root.tint
                font.pixelSize: Theme.fontSizeSmall
                anchors.verticalCenter: parent.verticalCenter
            }
        }
    }
    verticalBarPill: Component {
        DankIcon {
            name: root.icon
            size: root.iconSize
            color: root.tint
            RotationAnimator on rotation { from: 0; to: 360; duration: 1600; loops: Animation.Infinite; running: root.working }
        }
    }
    HoverHandler {
        id: hover
        onHoveredChanged: {
            if (!hovered) { hoverDelay.stop(); tooltip.hide(); }
            else hoverDelay.restart();
        }
    }
    Timer {
        id: hoverDelay
        interval: 450
        onTriggered: {
            const pos = root.mapToItem(null, root.width / 2, root.height);
            tooltip.show(root.controller?.tooltip || "AirDrop — Checking AirDrop status", pos.x, pos.y + 8, root.parentScreen);
        }
    }
    DankTooltip { id: tooltip }
}
