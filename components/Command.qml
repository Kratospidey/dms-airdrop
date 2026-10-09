import QtQuick
import Quickshell.Io

// Each invocation owns its own Process and timer. Late stream/exit signals
// from a timed-out invocation cannot be mistaken for a later request.
Item {
    id: root
    property var request: null
    property int timeoutMs: 45000
    readonly property bool busy: request !== null
    signal completed(var result)

    function start(argv) {
        if (busy) return false;
        request = requestFactory.createObject(root, {argv: argv});
        if (!request) {
            completed({ok: false, error: "AirDrop helper could not be created.", code: "helper"});
            return false;
        }
        request.launch();
        return true;
    }
    function finish(sender, result) {
        if (request !== sender) return;
        request = null;
        sender.destroy();
        completed(result);
    }
    Component {
        id: requestFactory
        Item {
            id: invocation
            required property var argv
            property bool outDone: false
            property bool errDone: false
            property bool exitDone: false
            property int exitCode: -1
            property string output: ""
            function launch() {
                process.command = argv;
                process.running = true;
                watchdog.start();
            }
            function collect() {
                if (!outDone || !errDone || !exitDone) return;
                watchdog.stop();
                let result;
                try {
                    result = JSON.parse(output);
                    if (typeof result !== "object" || result === null || typeof result.ok !== "boolean")
                        throw new Error("schema");
                    if (exitCode !== 0 && result.ok) throw new Error("exit");
                } catch (_) {
                    result = {ok: false, error: "AirDrop helper did not return a valid response.", code: "helper"};
                }
                root.finish(invocation, result);
            }
            // Only read/submit helpers live here. This never owns or kills a
            // transfer: each transfer belongs to a finite systemd user service.
            Timer {
                id: watchdog
                interval: root.timeoutMs
                onTriggered: {
                    process.running = false;
                    root.finish(invocation, {ok: false, error: "AirDrop helper timed out. Refresh status before retrying.", code: "timeout"});
                }
            }
            Process {
                id: process
                stdout: StdioCollector {
                    onStreamFinished: {
                        invocation.output = text;
                        invocation.outDone = true;
                        invocation.collect();
                    }
                }
                stderr: StdioCollector {
                    onStreamFinished: {
                        invocation.errDone = true;
                        invocation.collect();
                    }
                }
                onExited: (code, status) => {
                    invocation.exitCode = code;
                    invocation.exitDone = true;
                    invocation.collect();
                }
            }
        }
    }
}
