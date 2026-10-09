import QtQuick
import qs.Common
import qs.Widgets

Rectangle {
    id: root
    required property var peer
    property bool selected: false
    signal chosen
    width: parent.width
    height: 58
    radius: Theme.cornerRadius
    color: selected ? Theme.withAlpha(Theme.primary, 0.16) : area.containsMouse ? Theme.surfaceContainerHigh : Theme.surfaceContainer
    border.width: selected || activeFocus ? 1 : 0
    border.color: Theme.primary
    opacity: enabled ? 1 : 0.5
    activeFocusOnTab: enabled
    Accessible.role: Accessible.RadioButton
    Accessible.name: peer.label
    Accessible.checked: selected
    Accessible.onPressAction: chosen()
    Keys.onSpacePressed: chosen()
    Keys.onReturnPressed: chosen()
    DankIcon {
        anchors.left: parent.left
        anchors.leftMargin: Theme.spacingM
        anchors.verticalCenter: parent.verticalCenter
        name: "devices"
        color: root.selected ? Theme.primary : Theme.surfaceVariantText
        size: 24
    }
    Column {
        x: 52
        anchors.verticalCenter: parent.verticalCenter
        width: parent.width - 92
        StyledText {
            width: parent.width
            text: root.peer.label
            textFormat: Text.PlainText
            elide: Text.ElideRight
            color: Theme.surfaceText
            font.pixelSize: Theme.fontSizeMedium
        }
        StyledText {
            width: parent.width
            text: root.peer.name ? "Nearby · " + root.peer.mac.slice(-8) : "Nearby · name not requested"
            textFormat: Text.PlainText
            elide: Text.ElideRight
            font.pixelSize: Theme.fontSizeSmall
            color: Theme.surfaceVariantText
        }
    }
    DankIcon {
        anchors.right: parent.right
        anchors.rightMargin: Theme.spacingM
        anchors.verticalCenter: parent.verticalCenter
        name: root.selected ? "radio_button_checked" : "radio_button_unchecked"
        color: root.selected ? Theme.primary : Theme.surfaceVariantText
        size: 20
    }
    MouseArea {
        id: area
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.chosen()
    }
}
