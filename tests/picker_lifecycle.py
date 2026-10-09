#!/usr/bin/env python3
"""Actual Qt dialog lifecycle checks with no backend or radio access."""
import json
import subprocess
from pathlib import Path
from preview import prepare, environment, write, QA

shell = prepare()
files = QA / "picker-files"
files.mkdir(exist_ok=True)
urls = []
for name in ("space 日本語.txt", "second.txt"):
    path = files / name
    path.write_text("fixture")
    urls.append(path.resolve().as_uri())
source = '''import QtQuick
import Quickshell
import "Plugin/picker" as Plugin
ShellRoot {
    id: test
    property int tick: 0
    property int count: 0
    property int phase: 0
    property int accepted: 0
    property int errors: 0
    property var paths: []
    property var originalFactory: null
    property var urls: __URLS__
    FloatingWindow { id: popout; visible: true; implicitWidth: 100; implicitHeight: 100 }
    Plugin.FilePicker {
        id: picker
        launchTimeout: 100
        onSelected: values => { test.accepted++; test.paths = values; }
        onFailed: message => { test.errors++; }
    }
    Component {
        id: throwsOnStart
        Item {
            property var coordinator
            property int token
            function start() { throw new Error("injected launch failure"); }
            function present() {}
            function dispose() {}
        }
    }
    Component {
        id: neverOpens
        Item {
            property var coordinator
            property int token
            function start() {}
            function present() {}
            function dispose() {}
        }
    }
    function check(value, message) { if (!value) { console.error("PICKER_FAIL", message); Qt.quit(); throw new Error(message); } }
    Timer {
        interval: 40; running: true; repeat: true
        onTriggered: {
            test.tick++;
            if (test.tick > 500) { test.check(false, "timeout phase="+test.phase+" state="+picker.state+" count="+test.count); return; }
            if (test.phase === 0) {
                test.originalFactory = picker.sessionComponent;
                picker.open();
                const session = picker.session;
                for (let i=0; i<10; i++) picker.open();
                test.check(picker.session === session, "duplicate dialogs");
                test.phase = 1;
            } else if (test.phase === 1 && picker.state === "open") {
                // The original failure: dismissal of the caller must not hide
                // the dedicated picker host or leave a retained hidden dialog.
                popout.visible = false;
                test.check(picker.session.backingWindowVisible, "host missing");
                test.check(picker.session.dialog.parentWindow !== popout.contentItem.Window.window, "transient parent reused");
                picker.session.dialog.reject();
                test.phase = 2;
            } else if (test.phase === 2 && !picker.active) {
                test.check(picker.session === null, "cancel retained session");
                test.count++;
                if (test.count < 20) { picker.open(); test.phase = 1; }
                else { picker.open(); test.phase = 3; }
            } else if (test.phase === 3 && picker.state === "open") {
                const token = picker.serial;
                picker.session.complete("accepted", test.urls, "");
                test.check(test.accepted === 1 && test.paths.length === 2, "multiple acceptance");
                test.check(test.paths[0].includes("日本語"), "URL decode");
                picker.open();
                picker.finish(token, "cancelled", [], "");
                test.check(picker.active, "late callback closed replacement");
                test.phase = 4;
            } else if (test.phase === 4 && picker.state === "open") {
                picker.session.visible = false; // window-manager close/hide
                test.phase = 5;
            } else if (test.phase === 5 && !picker.active) {
                picker.open(); test.phase = 6;
            } else if (test.phase === 6 && picker.state === "open") {
                picker.session.destroy(); test.phase = 7;
            } else if (test.phase === 7 && !picker.active) {
                test.check(test.errors === 1, "destruction was not reported once");
                picker.sessionComponent = null;
                picker.open();
                test.check(!picker.active && test.errors === 2, "creation failure stuck");
                picker.sessionComponent = throwsOnStart;
                picker.open();
                test.check(!picker.active && test.errors === 3, "open exception stuck");
                picker.sessionComponent = neverOpens;
                picker.open(); test.phase = 8;
            } else if (test.phase === 8 && !picker.active) {
                test.check(test.errors === 4, "launch watchdog failed");
                picker.sessionComponent = test.originalFactory;
                picker.open(); test.phase = 9;
            } else if (test.phase === 9 && picker.state === "open") {
                // Portal-style rejection, then normal recreation after faults.
                picker.session.dialog.reject();
                test.phase = 10;
            } else if (test.phase === 10 && !picker.active) {
                test.check(picker.children.length === 0, "session object leaked");
                console.warn("PICKER_LIFECYCLE_OK: 20 cancel/reopen cycles, rapid clicks, parent hiding, Unicode multi-selection, late signals, WM close, destruction, creation/open failures, launch timeout and recovery");
                Qt.quit();
            }
        }
    }
}'''.replace("__URLS__", json.dumps(urls))
write(shell / "picker-lifecycle.qml", source)
result = subprocess.run(["qs", "-p", str(shell / "picker-lifecycle.qml"), "--no-color"],
                        env=environment(), capture_output=True, text=True, timeout=30)
output = result.stdout + result.stderr
print(output)
assert "PICKER_LIFECYCLE_OK" in output and "PICKER_FAIL" not in output
assert not any(error in output for error in ("TypeError", "ReferenceError", "Binding loop", "Cannot assign", "Error loading configuration"))
