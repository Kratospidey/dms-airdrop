#!/usr/bin/env python3
"""Real Quickshell Process tests for stream ordering and late completions."""
import subprocess
from preview import prepare, environment, write

shell = prepare()
write(shell / "command.qml", '''import QtQuick
import Quickshell
import "Plugin/components" as Plugin
ShellRoot {
    Item {
        id: owner
        property int stage: 0
        property int completions: 0
        function fail(message) { console.warn("COMMAND_FAIL: " + message); Qt.quit(); }
        function invoke(script) {
            if (!command.start(["python3", "-c", script])) fail("new command refused");
            if (command.start(["python3", "-c", "raise RuntimeError('duplicate')"])) fail("duplicate accepted");
        }
        Plugin.Command {
            id: command
            timeoutMs: owner.stage === 4 ? 150 : 3000
            onCompleted: result => {
                owner.completions++;
                if (owner.stage === 0 && (!result.ok || result.value !== "first")) { owner.fail("valid result"); return; }
                if (owner.stage === 1 && (result.ok || result.error !== "expected")) { owner.fail("exit failure"); return; }
                if (owner.stage === 2 && (result.ok || result.code !== "helper")) { owner.fail("malformed result"); return; }
                if (owner.stage === 3 && (!result.ok || result.value !== "late stderr")) { owner.fail("stream ordering"); return; }
                if (owner.stage === 4 && (result.ok || result.code !== "timeout")) { owner.fail("timeout"); return; }
                if (owner.stage === 5 && (!result.ok || result.value !== "after timeout")) { owner.fail("stale response"); return; }
                owner.stage++;
                Qt.callLater(owner.next);
            }
        }
        function next() {
            if (stage === 0) invoke("import json; print(json.dumps({'ok':True,'value':'first'}))");
            if (stage === 1) invoke("import json,sys; print(json.dumps({'ok':False,'error':'expected'})); sys.exit(7)");
            if (stage === 2) invoke("print('not json')");
            if (stage === 3) invoke("import json,os,time,sys; print(json.dumps({'ok':True,'value':'late stderr'}),flush=True); os.close(1); time.sleep(0.15); print('stderr',file=sys.stderr)");
            if (stage === 4) invoke("import signal,time,json; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(0.4); print(json.dumps({'ok':True,'value':'obsolete'}))");
            if (stage === 5) invoke("import json; print(json.dumps({'ok':True,'value':'after timeout'}))");
            if (stage === 6) settle.start();
        }
        Component.onCompleted: next()
        Timer {
            id: settle; interval: 650
            onTriggered: {
                if (owner.completions !== 6 || command.busy) owner.fail("late callback or stuck process");
                else { console.warn("COMMAND_SMOKE_OK"); Qt.quit(); }
            }
        }
    }
}''')
result = subprocess.run(["qs", "-p", str(shell / "command.qml"), "--no-color"], env=environment(), capture_output=True, text=True, timeout=12)
output = result.stdout + result.stderr
print(output)
raise SystemExit(0 if "COMMAND_SMOKE_OK" in output and "COMMAND_FAIL" not in output else 1)
