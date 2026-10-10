import QtQuick
import "FileSelection.js" as Selection

Item {
    id: root
    property Component sessionComponent: Component { FilePickerSession {} }
    property var sessionProperties: ({})
    property Component fallbackComponent: null
    property bool usingFallback: false
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
        if (active) return; // A failed session is being disposed before recovery.
        usingFallback = false;
        launch(sessionComponent, sessionProperties);
    }
    function launch(component, properties) {
        serial++;
        state = "opening";
        try {
            session = component.createObject(root, Object.assign({}, properties, {coordinator: root, token: serial}));
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
        const recovery = outcome === "failed" && !usingFallback ? fallbackComponent : null;
        // Invalidate all callbacks from the failed native attempt before closing
        // it. Recovery stays active, so rapid clicks cannot launch another dialog.
        const recoveryToken = recovery ? ++serial : serial;
        if (recovery) usingFallback = true;
        state = recovery ? "opening" : "idle";
        session = null;
        launchGuard.stop();
        // Detach state before closing: visibility/rejected/destruction can all
        // occur in one event loop. A late callback may never close a new picker.
        if (previous || recovery) {
            // Qt's accepted/rejected handler is still on the stack. Closing
            // its host synchronously can interrupt that signal's delivery.
            Qt.callLater(() => {
                try { if (previous) previous.dispose(); } catch (_) {}
                if (previous) previous.destroy();
                if (recovery && serial === recoveryToken && state === "opening" && !shuttingDown)
                    launch(recovery, {});
            });
        }
        if (recovery) return;
        if (outcome === "accepted") {
            try { selected(Selection.localPaths(urls)); }
            catch (error) { failed(error.message); }
        } else if (outcome === "failed") failed(message);
    }
    function lost(token) {
        finish(token, "failed", [], "The file picker closed unexpectedly. You can open it again.");
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
