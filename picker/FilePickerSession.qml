import QtQuick
import QtQuick.Dialogs
import QtQuick.Controls as Controls
import Quickshell
import qs.Common
import qs.Widgets

FloatingWindow {
    id: root
    required property var coordinator
    required property int token
    property bool started: false
    property bool finished: false
    property alias dialog: chooser
    visible: false
    title: "Send with AirDrop"
    implicitWidth: Math.min(760, (screen?.width || 900) - 60)
    implicitHeight: Math.min(660, (screen?.height || 760) - 80)
    color: Theme.surface

    function start() { started = true; visible = true; Qt.callLater(openDialog); }
    function openDialog() {
        if (finished || !backingWindowVisible) return;
        try {
            chooser.open();
            present();
        } catch (_) { complete("failed", [], "The file picker could not open. Try again."); }
    }
    function present() {
        if (finished) return;
        minimized = false;
        visible = true;
        const window = contentItem.Window.window;
        if (window) { window.raise(); window.requestActivate(); }
    }
    function dispose() {
        finished = true;
        chooser.close();
        visible = false;
    }
    function complete(outcome, urls, message) {
        if (finished) return;
        finished = true;
        coordinator.finish(token, outcome, urls, message);
    }
    onBackingWindowVisibleChanged: if (started && backingWindowVisible && !chooser.visible) Qt.callLater(openDialog)
    onVisibleChanged: if (started && !visible && !finished) complete("cancelled", [], "")
    onClosed: complete("cancelled", [], "")
    Component.onDestruction: if (!finished && coordinator) coordinator.lost(token)

    Column {
        anchors.centerIn: parent
        width: Math.max(100, parent.width - 64)
        spacing: Theme.spacingM
        StyledText {
            width: parent.width
            text: "Choose files in the file picker"
            color: Theme.surfaceText
            font.pixelSize: Theme.fontSizeLarge
            wrapMode: Text.Wrap
        }
        StyledText {
            width: parent.width
            text: "You can close this window to cancel. If the picker did not appear, cancel and try again from AirDrop."
            color: Theme.surfaceVariantText
            wrapMode: Text.Wrap
        }
        DankButton { text: "Cancel file selection"; onClicked: root.complete("cancelled", [], "") }
    }
    FileDialog {
        id: chooser
        // A dedicated, controller-owned top-level survives popout dismissal.
        // Native dialogs remain preferred; Qt's fallback has a usable host too.
        parentWindow: root.contentItem.Window.window
        title: "Send with AirDrop"
        fileMode: FileDialog.OpenFiles
        // The Qt fallback stays inside its stable host instead of opening an
        // additional popup that can extend beyond a tiled Wayland window.
        popupType: Controls.Popup.Item
        onVisibleChanged: {
            if (visible) root.coordinator.opened(root.token);
            else Qt.callLater(() => { if (!root.finished) root.complete("cancelled", [], ""); });
        }
        onAccepted: {
            try {
                const urls = [];
                for (const url of chooser.selectedFiles) urls.push(url.toString());
                root.complete("accepted", urls, "");
            } catch (_) {
                root.complete("failed", [], "The selected files could not be read. Choose them again.");
            }
        }
        onRejected: root.complete("cancelled", [], "")
    }
}
