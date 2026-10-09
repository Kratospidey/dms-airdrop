#!/usr/bin/env python3
"""Exercise the actual controller + Process/pipe completion in isolated QS."""
import json
from pathlib import Path
import subprocess
import sys

from preview import ROOT, QA, prepare, environment, write
from test_backend import BackendTests

fixture = BackendTests()
fixture.setUp()
try:
    # Submission stays inside this fake adapter process; no systemd worker
    # or real CLI can be started by this integration test.
    fixture.wrapper.write_text("import sys,json,uuid\n" + "sys.path.insert(0, " + repr(str(ROOT / "scripts")) + ")\nfrom backend import Backend,main,emit\n"
        + "b=Backend(home=" + repr(str(fixture.home)) + ", runtime=" + repr(str(fixture.runtime))
        + ", config=" + repr(str(fixture.config)) + ", cli=" + repr(str(fixture.cli))
        + ", systemctl=" + repr(str(fixture.systemctl)) + ", radio_helper=" + repr(str(fixture.radio)) + ")\n"
        + "b.window_fingerprint=lambda: str(json.load(open(" + repr(str(fixture.home / 'scenario.json')) + ")).get('generation',0))\n"
        + "b.schedule_session_cleanup=lambda token: None\nb.cancel_session_timer=lambda token: None\nb.incoming_busy=lambda: False\n"
        + "if sys.argv[1]=='submit':\n job_id=uuid.uuid4().hex\n b.operation(json.loads(sys.argv[2]),job_id)\n emit({'ok':True,'id':job_id})\nelse: sys.exit(main(b))\n")
    selected = fixture.file("choose 日本語 file.txt")
    shell = prepare()
    write(shell / "controller.qml", '''import QtQuick
import Quickshell
import qs.Services
import "Plugin" as Plugin
ShellRoot {
    FloatingWindow { id: window; visible: true; implicitWidth: 200; implicitHeight: 100 }
    Item {
        id: owner
        property var instance: null
        property int stage: 0
        property int ticks: 0
        function fail(message) { console.warn("SMOKE_FAIL: " + message); Qt.quit(); }
        Component { id: factory; Plugin.AirDropController { pluginService: PluginService; basicPicker: true; helper: "''' + str(fixture.wrapper) + '''" } }
        Component.onCompleted: instance = factory.createObject(owner)
        Timer {
            interval: 100; running: true; repeat: true
            onTriggered: {
                owner.ticks++;
                const c = owner.instance;
                if (owner.ticks > 180) { owner.fail("controller did not settle: stage=" + owner.stage + " picker=" + c.pickerState + " error=" + c.error + " selected=" + c.selectedFiles.length + " dialogVisible=" + c.picker?.dialog.visible + " hostVisible=" + c.picker?.visible + " finished=" + c.picker?.finished); return; }
                if (owner.stage === 0 && c && c.state === "OFF") {
                    if (!c.canAct || c.busy) { owner.fail("off state cannot act"); return; }
                    if (PluginService.getGlobalVar("dmsAirDrop", "controller", null) !== c) { owner.fail("shared controller missing"); return; }
                    c.refresh(); c.refresh(); c.refresh();
                    owner.stage = 1;
                } else if (owner.stage === 1 && owner.ticks > 8) {
                    c.destroy();
                    owner.instance = null;
                    owner.stage = 2;
                } else if (owner.stage === 2) {
                    if (PluginService.getGlobalVar("dmsAirDrop", "controller", null) !== null) { owner.fail("destroyed controller retained"); return; }
                    owner.instance = factory.createObject(owner);
                    owner.stage = 3;
                } else if (owner.stage === 3 && c && c.state === "OFF") {
                    c.pickFiles(window.contentItem.Window.window);
                    owner.stage = 4;
                } else if (owner.stage === 4 && c.picker && c.picker.visible) {
                    c.picker.dialog.reject();
                    owner.stage = 5;
                } else if (owner.stage === 5 && c.picker === null) {
                    if (c.selectedFiles.length !== 0) { owner.fail("cancelled picker retained files"); return; }
                    c.pickFiles();
                    owner.stage = 6;
                } else if (owner.stage === 6 && c.picker?.dialog.visible) {
                    c.picker.complete("accepted", ["__SELECTED_URL__"], "");
                    owner.stage = 7;
                } else if (owner.stage === 7 && c.selectedFiles.length === 1 && !c.selecting && c.active && !c.busy) {
                    if (!c.temporarySession || !c.selectionSummary.includes("choose")) { owner.fail("automatic discovery ownership or summary missing"); return; }
                    c.pickFiles();
                    owner.stage = 8;
                } else if (owner.stage === 8 && c.picker?.dialog.visible) {
                    c.picker.dialog.reject();
                    owner.stage = 9;
                } else if (owner.stage === 9 && c.picker === null) {
                    if (c.selectedFiles.length !== 1) { owner.fail("cancel lost previous selection"); return; }
                    c.pickFiles();
                    owner.stage = 10;
                } else if (owner.stage === 10 && c.picker?.dialog.visible) {
                    c.picker.complete("accepted", ["__SELECTED_URL__"], "");
                    c.clearSelection();
                    owner.stage = 11;
                } else if (owner.stage === 11 && !c.selecting && !c.picker && !c.busy && !c.active) {
                    if (c.selectedFiles.length) { owner.fail("cancelled validation restored files"); return; }
                    console.warn("CONTROLLER_SMOKE_OK");
                    Qt.quit();
                }
            }
        }
    }
}'''.replace('__SELECTED_URL__', Path(selected).as_uri()))
    env = environment()
    env.update(HOME=str(fixture.home), XDG_CONFIG_HOME=str(fixture.config), XDG_RUNTIME_DIR=str(fixture.runtime))
    result = subprocess.run(["qs", "-p", str(shell / "controller.qml"), "--no-color"], env=env, capture_output=True, text=True, timeout=30)
    output = result.stdout + result.stderr
    print(output)
    calls = fixture.calls()
    assert "CONTROLLER_SMOKE_OK" in output, "controller smoke test failed"
    assert [c for c in calls if c[0] in ('on','off','send')] == [['on','60m'],['off']], calls
    assert "ReferenceError" not in output and "TypeError" not in output
    print("PASS: actual QML controller, structured Process completion, deduplicated polls, destruction/recreation, Qt fallback cancel/reopen, validated selection automatically prepares mocked discovery, replacement cancel retains selection, cancellation cleans owned session.")
finally:
    fixture.tearDown()
