import QtQuick
import "FileSelection.js" as Selection

Item {
    id: root
    property Component sessionComponent: Component { FilePickerSession {} }
    property var session: null
    property int serial: 0
    property string state: "idle"
    property bool shuttingDown: false
    property int launchTimeout: 6000
    readonly property bool active: state !== "idle"
    signal selected(var paths)
    signal failed(string message)

    function open() {
        if (session) {
            try { session.present(); }
            catch (_) { finish(serial, "failed", [], "The file picker is unavailable. Try again."); }
            return;
        }
        serial++;
        state = "opening";
        try {
            session = sessionComponent.createObject(root, {coordinator: root, token: serial});
            if (!session) throw new Error("creation");
            launchGuard.restart();
            session.start();
        } catch (_) {
            finish(serial, "failed", [], "The file picker could not open. Try again.");
        }
    }
    function opened(token) {
        if (token !== serial || !session || state === "idle") return;
        state = "open";
        launchGuard.stop();
    }
    function finish(token, outcome, urls, message) {
        if (token !== serial || state === "idle" || shuttingDown) return;
        const previous = session;
        state = "idle";
        session = null;
        launchGuard.stop();
        // Detach state before closing: visibility/rejected/destruction can all
        // occur in one event loop. A late callback may never close a new picker.
        if (previous) {
            // Qt's accepted/rejected handler is still on the stack. Closing
            // its host synchronously can interrupt that signal's delivery.
            Qt.callLater(() => {
                try { previous.dispose(); } catch (_) {}
                if (previous) previous.destroy();
            });
        }
        if (outcome === "accepted") {
            try { selected(Selection.localPaths(urls)); }
            catch (error) { failed(error.message); }
        } else if (outcome === "failed") failed(message);
    }
    function lost(token) {
        if (token !== serial || state === "idle" || shuttingDown) return;
        state = "idle";
        session = null;
        launchGuard.stop();
        failed("The file picker closed unexpectedly. You can open it again.");
    }
    function cancel() { finish(serial, "cancelled", [], ""); }
    Timer {
        id: launchGuard
        interval: root.launchTimeout
        onTriggered: root.finish(root.serial, "failed", [], "The file picker did not open. Try again.")
    }
    Component.onDestruction: {
        shuttingDown = true;
        if (session) session.dispose();
    }
}
