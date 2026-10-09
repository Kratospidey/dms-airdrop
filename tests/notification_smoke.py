#!/usr/bin/env python3
"""Controller behavior against the installed DMS toast implementation."""
import subprocess
from pathlib import Path
from preview import ROOT, prepare, environment, write
from test_backend import BackendTests
from support import dms_source

fixture = BackendTests()
fixture.setUp()
try:
    shell = prepare()
    dms = dms_source() / "Services/ToastService.qml"
    # The unused settings import is omitted; the implementation is unchanged.
    write(shell / "Services/ToastService.qml", dms.read_text().replace("import qs.Common.settings\n", ""))
    write(shell / "Services/SessionData.qml", '''pragma Singleton
import Quickshell
Singleton { signal loadErrorOccurred(string file, string message) }
''')
    write(shell / "Services/Processes.qml", '''pragma Singleton
import Quickshell
Singleton {
    signal toastRequested(int severity, string title, string body, string command, string category)
    signal toastCategoryDismissed(string category)
}
''')
    write(shell / "notifications.qml", '''import QtQuick
import Quickshell
import qs.Services
import "Plugin" as Plugin
ShellRoot {
    Item {
        id: test
        property var controller
        property int stage: 0
        property double started: 0
        property int ticks: 0
        Component { id: factory; Plugin.AirDropController { helper: "__HELPER__" } }
        function check(condition, message) {
            if (!condition) { console.error("NOTIFICATION_FAIL", message); Qt.quit(); throw new Error(message); }
        }
        Component.onCompleted: controller = factory.createObject(test)
        Timer {
            interval: 50; running: true; repeat: true
            onTriggered: {
                test.ticks++;
                test.check(test.ticks < 340, "notification timeout stage=" + test.stage);
                const c = test.controller;
                if (test.stage === 0 && c.state === "OFF") {
                    c.snapshot = {ok: true, busy: false, status: c.backend, job: {id: "old", state: "complete", action: "send"}};
                    test.check(!c.showResult, "old success footer");
                    c.showSuccess("first");
                    test.started = Date.now();
                    test.stage = 1;
                } else if (test.stage === 1 && Date.now() - test.started > 1800) {
                    test.check(ToastService.toastVisible, "DMS default timer was not extended");
                    c.showSuccess("second");
                    test.stage = 2;
                } else if (test.stage === 2 && ToastService.currentCategory.endsWith("second")) {
                    test.check(Date.now() - test.started >= 3400, "first toast vanished too soon");
                    test.started = Date.now();
                    test.stage = 3;
                } else if (test.stage === 3 && !ToastService.toastVisible) {
                    test.check(Date.now() - test.started >= 3400 && Date.now() - test.started < 4000, "success lifetime");
                    c.snapshot = {ok: true, busy: false, status: c.backend, job: {id: "failed", state: "failed", action: "send", message: "Recipient declined."}};
                    test.check(c.showResult, "failure not visible");
                    ToastService.showError("Failure", "Recipient declined.");
                    c.showSuccess("queued");
                    test.started = Date.now();
                    test.stage = 4;
                } else if (test.stage === 4 && Date.now() - test.started > 3700) {
                    test.check(ToastService.currentLevel === ToastService.levelError && c.showResult, "success timer hid an error");
                    // Reload while our toast is queued: it must not leave a
                    // stale timer or touch the unrelated error notification.
                    c.destroy();
                    test.controller = null;
                    test.stage = 5;
                } else if (test.stage === 5) {
                    test.check(ToastService.toastQueue.length === 0, "destroyed controller left queued success");
                    test.check(ToastService.currentLevel === ToastService.levelError, "reload dismissed error");
                    test.controller = factory.createObject(test);
                    test.stage = 6;
                } else if (test.stage === 6 && c.state === "OFF") {
                    test.check(!c.showResult, "reopen resurrected success");
                    c.showSuccess("reload-active");
                    ToastService.hideToast();
                    test.stage = 7;
                } else if (test.stage === 7 && ToastService.currentCategory.endsWith("reload-active")) {
                    c.destroy(); test.controller = null; test.stage = 8;
                } else if (test.stage === 8) {
                    test.check(!ToastService.toastVisible, "destroy left stopped native timer");
                    console.warn("NOTIFICATION_SMOKE_OK: real DMS queue, 3.5s lifetime, rapid successes, durable error, reload cleanup, no success footer");
                    Qt.quit();
                }
            }
        }
    }
}'''.replace("__HELPER__", str(fixture.wrapper)))
    result = subprocess.run(["qs", "-p", str(shell / "notifications.qml"), "--no-color"],
                            env=environment(), capture_output=True, text=True, timeout=25)
    output = result.stdout + result.stderr
    print(output)
    assert "NOTIFICATION_SMOKE_OK" in output and "NOTIFICATION_FAIL" not in output
    assert not any(x in output for x in ("TypeError", "ReferenceError", "Cannot assign", "Error loading configuration"))
    assert all(c == ["status", "--json"] for c in fixture.calls())
finally:
    fixture.tearDown()
