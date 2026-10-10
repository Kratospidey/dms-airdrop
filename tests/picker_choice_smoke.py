#!/usr/bin/env python3
"""Picker capability, recovery and persisted preference tests in isolated QS.

The enhanced executable is a protocol fixture; real KDE widgets have separate
native/adapter tests. No capability probe process or host backend is used.
"""
import json
from pathlib import Path
import subprocess
import tempfile
from preview import ROOT, prepare, environment, write

with tempfile.TemporaryDirectory(prefix='picker-choice-', dir=ROOT / '.qa') as tmp:
    base = Path(tmp)
    executable = base / 'helper space 日本語'
    wrapper = base / 'fixture.py'
    preferences = base / 'preferences.json'
    preferences.write_text('{}')
    native = '''#!/usr/bin/env python3
import json,sys,time
from pathlib import Path
base=Path(__file__).parent
with (base/'native.jsonl').open('a') as out: out.write(json.dumps(sys.argv[1:])+'\\n')
mode=(base/'mode').read_text()
if mode!='stall': print(json.dumps({'event':'opened'}),flush=True)
if mode=='crash':
 time.sleep(0.2)
 sys.exit(7)
for line in sys.stdin:
 if line.strip()=='cancel':
  print(json.dumps({'event':'result','accepted':False,'urls':[]}),flush=True)
  break
'''
    wrapper.write_text('''import json,sys
from pathlib import Path
base=Path(__file__).parent
command=sys.argv[1]
with (base/'calls.jsonl').open('a') as out: out.write(json.dumps(sys.argv[1:])+'\\n')
if command=='configure':
 mode=sys.argv[2]; target=Path(EXECUTABLE)
 if target.exists(): target.unlink()
 if mode!='absent':
  target.write_text(NATIVE);target.chmod(0o600 if mode=='nonexec' else 0o700)
 (base/'mode').write_text(mode); result={'ok':True}
elif command=='status': result={'ok':False,'code':'missing','error':'Fixture backend unavailable'}
else: raise AssertionError('Unexpected operation '+command)
print(json.dumps(result))
'''.replace('EXECUTABLE', repr(str(executable))).replace('NATIVE', repr(native)))
    shell = prepare()
    service = shell / 'Services/PluginService.qml'
    service.write_text(service.read_text().replace('import Quickshell\n', 'import Quickshell\nimport Quickshell.Io\n')
        .replace('property var preferences: ({})', 'property var preferences: JSON.parse(preferenceFile.text())\n'
                 + 'FileView { id: preferenceFile; path: ' + json.dumps(str(preferences))
                 + '; blockLoading: true; blockWrites: true }')
        .replace('pluginDataChanged(id); }', 'preferenceFile.setText(JSON.stringify(preferences)); pluginDataChanged(id); }'))
    source = r'''import QtQuick
import QtTest
import Quickshell
import qs.Services
import "Plugin" as Plugin
import "Plugin/components" as Components
ShellRoot {
 FloatingWindow {
  id: window; visible:true; implicitWidth:600; implicitHeight:800
  TestCase {
   id: test; name:"PickerChoice"; when:window.visible
   property string phase:__PHASE__
   property var c:null
   property int brokenStarts:0
   onCompletedChanged: if(completed) console.warn("CHOICE_RESULT",JSON.stringify({passed:qtest_results.passCount,failed:qtest_results.failCount}));
   Components.Command { id: fixture }
   Component { id: factory; Plugin.AirDropController { helper:__HELPER__; nativePickerExecutable:__NATIVE__; pluginService:PluginService } }
   Component { id: brokenBasic; Item {
    property var coordinator; property int token
    function start() { test.brokenStarts++;throw new Error("Fixture basic failure"); }
    function dispose() {}
   } }
   function configure(mode) {
    verify(fixture.start(["python3",__HELPER__,"configure",mode]));tryCompare(fixture,"busy",false,2000);
   }
   function create() { c=factory.createObject(window.contentItem);verify(c!==null);tryCompare(c,"state","UNAVAILABLE",2000); }
   function basic() { c.pickFiles();tryVerify(()=>c.picker?.dialog?.visible,2000);compare(c.error,""); }
   function enhanced() { c.pickFiles();tryCompare(c,"pickerState","open",2000);verify(!c.picker.dialog);compare(c.picker.executable,__NATIVE__); }
   function init() {
    if(phase!=="main" && qtest_results.functionName!=="test_restart") {skip("separate restart phase");return;}
    if(phase==="main") PluginService.savePluginData("dmsAirDrop","filePicker","auto");
   }
   function cleanup() {
    console.warn("CHOICE_CASE",qtest_results.functionName,"failures",qtest_results.failCount);
    if(c) {c.cancelPicker();c.destroy();} c=null;wait(50);
   }
   function test_missing_first_click_and_repeat() {
    configure("absent");create();const requested=Date.now();basic();verify(Date.now()-requested<2000);
    const session=c.picker;for(let i=0;i<8;i++)c.pickFiles();compare(c.picker,session);
    for(let i=0;i<5;i++){c.cancelPicker();wait(50);basic();}
   }
   function test_nonexecutable() {configure("nonexec");create();basic();verify(c.basicPicker);}
   function test_available() {configure("working");create();enhanced();verify(!c.basicPicker);}
   function test_install_after_first_use() {
    configure("absent");create();basic();c.cancelPicker();wait(50);
    configure("working");enhanced();c.cancelPicker();wait(50);
    configure("nonexec");basic();
   }
   function test_crash_recovers_once() {
    configure("crash");create();c.pickFiles();const coordinator=c.picker.coordinator;
    tryVerify(()=>c.picker?.dialog?.visible,2500);verify(coordinator.usingFallback);compare(c.error,"");
    const session=c.picker;for(let i=0;i<8;i++)c.pickFiles();compare(c.picker,session);
    c.cancelPicker();wait(50);configure("working");enhanced();verify(!coordinator.usingFallback);
   }
   function test_fallback_failure_is_bounded_and_retryable() {
    configure("working");create();enhanced();const coordinator=c.picker.coordinator;
    coordinator.fallbackComponent=brokenBasic;brokenStarts=0;
    c.picker.complete("failed",[],"Fixture native failure");
    tryVerify(()=>!c.pickerActive,2000);compare(brokenStarts,1);verify(c.error.includes("picker"));
    wait(300);compare(brokenStarts,1);verify(!c.pickerActive);
    c.useBasicPicker();tryVerify(()=>c.picker?.dialog?.visible,2000);compare(c.error,"");
    compare(c.pickerPreference,"auto");
   }
   function test_cancel_during_recovery_and_late_callbacks() {
    configure("working");create();enhanced();const coordinator=c.picker.coordinator;const token=coordinator.serial;
    c.picker.complete("failed",[],"Fixture native failure");
    c.pickFiles();compare(coordinator.serial,token+1); // No duplicate launch during deferred disposal.
    c.cancelPicker();wait(100);verify(!c.pickerActive);verify(c.picker===null);
    enhanced();const current=c.picker;coordinator.finish(token,"failed",[],"Late failure");compare(c.picker,current);
   }
   function test_destroy_during_recovery() {
    configure("working");create();enhanced();c.picker.complete("failed",[],"Fixture native failure");
    c.destroy();c=null;wait(200);
    verify(PluginService.getGlobalVar("dmsAirDrop","controller",null)===null);
    configure("absent");create();basic();
   }
   function test_basic_preference_with_available_helper() {
    configure("working");PluginService.savePluginData("dmsAirDrop","filePicker","basic");create();basic();
    c.cancelPicker();c.destroy();c=null;wait(50);create();compare(c.pickerPreference,"basic");basic();
   }
   function test_explicit_kde_still_handles_absence() {
    configure("absent");PluginService.savePluginData("dmsAirDrop","filePicker","kde");create();basic();
    c.cancelPicker();wait(50);configure("working");enhanced();
   }
   function test_idle_does_not_probe() {
    configure("working");create();compare(c.pollInterval,300000);verify(!c.clockRunning);
    const serial=c.pickerState;wait(3500);compare(c.pickerState,serial);verify(!c.pickerActive);
   }
   function test_launch_watchdog_recovers() {
    configure("stall");create();c.pickFiles();const coordinator=c.picker.coordinator;
    compare(coordinator.launchTimeout,6000);coordinator.launchTimeout=500;
    tryVerify(()=>c.picker?.dialog?.visible,2500);verify(coordinator.usingFallback);compare(c.error,"");
   }
   function test_restart() {
    if(phase==="main"){skip("tested in fresh QS processes");return;}
    // Disk-backed stand-in for DMS's supported load/savePluginData API.
    compare(PluginService.loadPluginData("dmsAirDrop","filePicker","auto"),phase);
    configure(phase==="auto"?"absent":"working");create();compare(c.pickerPreference,phase);
    if(phase==="kde") enhanced();else basic();
    PluginService.savePluginData("dmsAirDrop","filePicker",phase==="basic"?"kde":"auto");
   }
   function test_z_save_for_restart() {PluginService.savePluginData("dmsAirDrop","filePicker","basic");}
  }
 }
}'''.replace('__HELPER__', json.dumps(str(wrapper))).replace('__NATIVE__', json.dumps(str(executable)))
    for phase in ('main', 'basic', 'kde', 'auto'):
        write(shell / 'picker-choice.qml', source.replace('__PHASE__', json.dumps(phase)))
        result = subprocess.run(['qs', '-p', str(shell / 'picker-choice.qml'), '--no-color'],
            env=environment(), capture_output=True, text=True, timeout=70)
        output = result.stdout + result.stderr
        print(phase, output)
        report = json.loads(next(line.split('CHOICE_RESULT ', 1)[1] for line in output.splitlines() if 'CHOICE_RESULT ' in line))
        assert result.returncode == 0 and report['failed'] == 0 and report['passed'] >= (14 if phase == 'main' else 2), report
        assert not any(s in output for s in ('TypeError', 'ReferenceError', 'Binding loop', 'Cannot assign', 'Error loading configuration'))
    calls = [json.loads(line) for line in (base / 'calls.jsonl').read_text().splitlines()]
    assert all(call[0] in ('configure', 'status') for call in calls), calls
    # Startup status only: 14 controllers in the main cases, then 3 restarts.
    assert sum(call[0] == 'status' for call in calls) == 17, calls
    assert len((base / 'native.jsonl').read_text().splitlines()) == 11
    print('PASS: capability/recovery cases and Basic/KDE/Auto persistence across fresh QS processes; no idle capability subprocesses')
