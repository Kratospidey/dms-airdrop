#!/usr/bin/env python3
"""Exercise native chooser through the actual QML coordinator/Process adapter."""
import subprocess
from preview import prepare, environment, write

shell = prepare()
write(shell / "kde-adapter.qml", '''import QtQuick
import Quickshell
import "Plugin/picker" as Plugin
import "Plugin/workflow" as Native
ShellRoot {
    id: test
    property int ticks: 0
    property int count: 0
    property int stage: 0
    property int failures: 0
    function check(ok, message) { if (!ok) { console.error("KDE_FAIL", message); Qt.quit(); throw new Error(message); } }
    Plugin.FilePicker {
        id: picker
        sessionComponent: Component { Native.KdePickerSession {} }
        onFailed: message => { test.failures++; }
    }
    Component { id: missing; Native.KdePickerSession { executable: "/nonexistent/dms-airdrop-picker" } }
    Component { id: working; Native.KdePickerSession {} }
    Timer {
        interval: 50; running: true; repeat: true
        onTriggered: {
            test.check(++test.ticks < 500, "timeout stage=" + test.stage + " count=" + test.count);
            if (test.stage === 0) { picker.open(); test.stage = 1; }
            else if (test.stage === 1 && picker.state === "open") {
                const session = picker.session;
                for (let i = 0; i < 8; i++) picker.open();
                test.check(picker.session === session, "duplicate chooser");
                picker.cancel();
                test.stage = 2;
            } else if (test.stage === 2 && !picker.active) {
                if (++test.count < 20) test.stage = 0;
                else {
                    test.check(test.failures === 0, "unexpected adapter failure");
                    picker.sessionComponent = missing;
                    picker.launchTimeout = 200;
                    picker.open(); test.stage = 3;
                }
            } else if (test.stage === 3 && !picker.active) {
                test.check(test.failures === 1, "launch failure was not recoverable");
                picker.sessionComponent = working;
                picker.launchTimeout = 6000;
                picker.open(); test.stage = 4;
            } else if (test.stage === 4 && picker.state === "open") {
                picker.session.destroy(); test.stage = 5;
            } else if (test.stage === 5 && !picker.active) {
                test.check(test.failures === 2, "unexpected destruction left coordinator stuck");
                picker.open(); test.stage = 6;
            } else if (test.stage === 6 && picker.state === "open") {
                picker.cancel(); test.stage = 7;
            } else if (test.stage === 7 && !picker.active) {
                console.warn("KDE_ADAPTER_OK: 20 Qt Process coordinator cycles, duplicate focus, failed launch, unexpected destruction and recovery");
                Qt.quit();
            }
        }
    }
}''')
result = subprocess.run(["qs", "-p", str(shell / "kde-adapter.qml"), "--no-color"],
                        env=environment(), capture_output=True, text=True, timeout=35)
output = result.stdout + result.stderr
print(output)
assert "KDE_ADAPTER_OK" in output and "KDE_FAIL" not in output
assert not any(x in output for x in ("TypeError", "ReferenceError", "Cannot assign", "Error loading configuration"))
