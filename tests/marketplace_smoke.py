#!/usr/bin/env python3
"""Fresh source-root QML load: no installer, native binary or Omdrop required.

All backend paths are injected into private fixtures. Only metadata reads are
allowed; unexpected commands abort the wrapper before reaching the adapter.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from preview import ROOT, prepare, environment, write, link

(ROOT / ".qa").mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix="marketplace-", dir=ROOT / ".qa") as tmp:
    base = Path(tmp)
    config = base / "custom config"
    plugin = config / "DankMaterialShell/plugins/dmsAirDrop"
    plugin.mkdir(parents=True)
    for relative in (ROOT / "PUBLIC_FILES.txt").read_text().splitlines():
        target = plugin / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    assert not (plugin / ".build").exists()
    manifest = json.loads((plugin / "plugin.json").read_text())
    assert manifest["id"] == "dmsAirDrop" and manifest["name"] == "AirDrop"
    for relative in [*manifest["components"].values(), manifest["settings"]]:
        assert (plugin / relative).is_file()
    for relative in ("install.sh", "scripts/backend.py", "scripts/install.py"):
        assert os.access(plugin / relative, os.X_OK)
    home = base / "home"; home.mkdir()
    runtime = base / "runtime"; runtime.mkdir(mode=0o700)
    calls = base / "commands.jsonl"
    selected = home / 'sample 日本語 "file".txt'; selected.write_text("harmless fixture")
    wrapper = base / "backend_fixture.py"
    wrapper.write_text("import sys,json\nfrom pathlib import Path\n"
        + "sys.path.insert(0," + repr(str(plugin / "scripts")) + ")\nfrom backend import Backend,main\n"
        + "with open(" + repr(str(calls)) + ",'a') as out: out.write(json.dumps(sys.argv[1:])+'\\n')\n"
        + "assert sys.argv[1] in ('status','inspect-files'), 'Unexpected mutation or diagnostic command'\n"
        + "b=Backend(home=" + repr(str(home)) + ",config=" + repr(str(config)) + ",runtime=" + repr(str(runtime))
        + ",cli=" + repr(str(base / "missing-omdrop")) + ",systemctl=" + repr(str(base / "missing-systemctl"))
        + ",radio_helper=" + repr(str(base / "missing-radio")) + ")\nsys.exit(main(b))\n")
    shell = prepare()
    link(plugin, shell / "RegistryPlugin")
    qml = r'''import QtQuick
import Quickshell
import "RegistryPlugin" as Plugin
ShellRoot {
    FloatingWindow {
        id: window; visible: true; implicitWidth: 620; implicitHeight: 900
        Plugin.AirDropPopout { id: popout; controller: controller; width: 600; availableHeight: 900 }
    }
    Plugin.AirDropController { id: controller; helper: __HELPER__ }
    Item {
        id: test
        property int stage: 0
        property int ticks: 0
        property double pickerRequestedAt: 0
        function check(ok, message) {
            if (!ok) { console.error("MARKETPLACE_FAIL", message); Qt.quit(); throw new Error(message); }
        }
        function texts(item) {
            let result = typeof item.text === "string" ? [item.text] : [];
            for (const child of item.children || []) result = result.concat(texts(child));
            return result;
        }
        Timer {
            interval: 50; running: true; repeat: true
            onTriggered: {
                test.check(++test.ticks < 450, "timeout stage=" + test.stage);
                const c = controller;
                if (test.stage === 0 && c.state === "UNAVAILABLE") {
                    test.check(c.snapshot.code === "missing" && !c.canAct && !c.canSend, "missing backend allowed a transfer");
                    const labels = test.texts(popout);
                    test.check(labels.includes("Set up Omdrop and a compatible radio backend"), "setup status missing");
                    test.check(!labels.includes("Ready to send or receive"), "unavailable backend advertised ready");
                    c.receive("1m"); c.send(); c.stop();
                    test.check(!c.pending, "blocked backend accepted an operation");
                    test.pickerRequestedAt=Date.now();c.pickFiles();test.check(c.basicPicker,"missing helper did not choose Basic before launch");test.stage = 1;
                } else if (test.stage === 1 && c.picker?.dialog.visible) {
                    test.check(Date.now()-test.pickerRequestedAt<2000 && !c.error,"fresh installation delayed or reported a picker error");
                    c.picker.complete("accepted", [__SELECTED__], ""); test.stage = 3;
                } else if (test.stage === 3 && !c.selecting && c.selectedFiles.length === 1) {
                    test.check(!c.canAct && !c.canSend && !c.pending && !c.active, "selection started a missing backend");
                    test.check(c.selectedFiles[0] === __PATH__, "fallback changed selected path");
                    c.clearSelection(); c.pickFiles(); test.stage = 4;
                } else if (test.stage === 4 && c.picker?.dialog.visible) {
                    c.cancelPicker(); test.stage = 5;
                } else if (test.stage === 5 && !c.pickerActive) {
                    test.check(c.selectedFiles.length === 0, "cancel retained selection");
                    console.warn("MARKETPLACE_OK: fresh source root, first-click Basic without helper/error/delay, missing backend guards, Unicode selection/cancel/reopen");
                    Qt.quit();
                }
            }
        }
    }
}'''.replace("__HELPER__", json.dumps(str(wrapper))).replace("__SELECTED__", json.dumps(selected.as_uri())).replace("__PATH__", json.dumps(str(selected)))
    write(shell / "marketplace.qml", qml)
    env = environment()
    env.update(HOME=str(home), XDG_CONFIG_HOME=str(config), XDG_RUNTIME_DIR=str(runtime))
    result = subprocess.run(["qs", "-p", str(shell / "marketplace.qml"), "--no-color"], env=env, capture_output=True, text=True, timeout=30)
    output = result.stdout + result.stderr
    print(output)
    assert "MARKETPLACE_OK" in output and "MARKETPLACE_FAIL" not in output
    assert not any(x in output for x in ("TypeError", "ReferenceError", "Cannot assign", "Error loading configuration"))
    recorded = [json.loads(line) for line in calls.read_text().splitlines()]
    assert all(call[0] in ("status", "inspect-files") for call in recorded), recorded
    assert any(call[0] == "inspect-files" for call in recorded)
    print("PASS: no installer invoked, no native binary built, no backend/radio mutation attempted")
