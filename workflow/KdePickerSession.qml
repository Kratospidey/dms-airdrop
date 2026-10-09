import QtQuick
import Quickshell.Io
import qs.Common

Item {
    id: root
    required property var coordinator
    required property int token
    property bool finished: false
    property bool receivedResult: false
    property string executable: decodeURIComponent(Qt.resolvedUrl("../.build/picker/dms-airdrop-picker").toString().substring(7))
    function start() {
        process.command = [executable, JSON.stringify({palette: {
            surface: Theme.surface.toString(), base: Theme.surfaceContainer.toString(),
            text: Theme.surfaceText.toString(), primary: Theme.primary.toString(),
            onPrimary: Theme.primaryText.toString()
        }})];
        process.running = true;
    }
    function present() { if (!finished && process.running) process.write("focus\n"); }
    function dispose() {
        finished = true;
        if (process.running) process.write("cancel\n");
        process.running = false;
    }
    function complete(outcome, urls, message) {
        if (finished) return;
        finished = true;
        coordinator.finish(token, outcome, urls, message);
    }
    Process {
        id: process
        stdinEnabled: true
        stdout: SplitParser {
            onRead: line => {
                if (root.finished) return;
                try {
                    const result = JSON.parse(line);
                    if (result.event === "opened") root.coordinator.opened(root.token);
                    else if (result.event === "result" && typeof result.accepted === "boolean" && Array.isArray(result.urls)) {
                        root.receivedResult = true;
                        root.complete(result.accepted ? "accepted" : "cancelled", result.urls, "");
                    } else throw new Error("schema");
                } catch (_) { root.complete("failed", [], "The KDE file picker returned an invalid selection. Try again."); }
            }
        }
        stderr: StdioCollector {}
        onExited: (code, status) => Qt.callLater(() => {
            if (!root.finished) root.complete("failed", [], "The KDE file picker closed unexpectedly. Try again or use the basic picker.");
        })
        onStarted: {}
    }
    Component.onDestruction: {
        if (!finished && coordinator) coordinator.lost(token);
    }
}
