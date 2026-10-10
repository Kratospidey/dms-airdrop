#!/usr/bin/env python3
"""Controller lifecycle/polling regression tests with explicit file-backed mocks."""
import json
from pathlib import Path
import subprocess
import tempfile
from preview import ROOT, prepare, environment, write

(ROOT / '.qa').mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='polling-',dir=ROOT/'.qa') as tmp:
    base=Path(tmp); wrapper=base/'fixture.py'; calls=base/'calls.jsonl'
    wrapper.write_text('''import json,sys,time
from pathlib import Path
base=Path(__file__).parent
command=sys.argv[1]
with (base/'calls.jsonl').open('a') as out: out.write(json.dumps(sys.argv[1:])+'\\n')
if command=='fixture':
 (base/'state.json').write_text(sys.argv[2]); result={'ok':True}
elif command=='status': result=json.loads((base/'state.json').read_text())
elif command=='peers': result={'ok':True,'peers':[]}
elif command=='submit':
 request=json.loads(sys.argv[2]); assert request['action']=='cleanup-send'
 result=json.loads((base/'state.json').read_text()); result.update(busy=False,session={},job={'id':'cleanup','action':'cleanup-send','state':'complete','updated':time.time()})
 result['status'].update(receiving=False,visible=False,mode='off',remaining=None)
 (base/'state.json').write_text(json.dumps(result)); result={'ok':True,'id':'cleanup'}
else: raise AssertionError('Unexpected fixture operation '+command)
print(json.dumps(result))
''')
    shell=prepare()
    write(shell/'polling.qml',r'''import QtQuick
import QtTest
import Quickshell
import qs.Services
import "Plugin" as Plugin
import "Plugin/components" as Components
ShellRoot {
 FloatingWindow {
  id: window; visible:true; implicitWidth:600; implicitHeight:800
  TestCase {
   id: test; name:"Monitoring"; when:window.visible
   property var c:null
   property var views:[]
   property int samples:0
   onCompletedChanged: if (completed) console.warn("MONITORING_RESULT",JSON.stringify({passed:qtest_results.passCount,failed:qtest_results.failCount}));
   Components.Command { id: fixture }
   Component { id: controllerFactory; Plugin.AirDropController { helper:__HELPER__; pluginService:PluginService } }
   Component { id: popoutFactory; Plugin.AirDropPopout { width:380; availableHeight:700 } }
   Component { id: parentFactory; QtObject { property bool shouldBeVisible:false } }
   Connections { target:test.c; function onSampledAtChanged() { test.samples++; } }
   function response(active=false) { return {ok:true,busy:false,job:{},session:{},status:{receiving:active,visible:active,remaining:active?600:null,mode:active?"timed":"off",receiver_state:active?"active":"inactive",dir:"/mock",name:"Mock"}}; }
   function configure(value) {
    verify(fixture.start(["python3",__HELPER__,"fixture",JSON.stringify(value)])); tryCompare(fixture,"busy",false,2000);
   }
   function create(value=response()) {
    configure(value); c=controllerFactory.createObject(window.contentItem); verify(c!==null);
    tryVerify(()=>c.sampledAt>0,2000); compare(c.checking,false);
   }
   function popout() {
    const parent=parentFactory.createObject(test);
    const view=popoutFactory.createObject(window.contentItem,{controller:c,parentPopout:parent});
    views.push({view:view,parent:parent}); return views[views.length-1];
   }
   function init() { samples=0; }
   function cleanup() {
    console.warn("MONITORING_CASE",qtest_results.functionName,"failures",qtest_results.failCount);
    for(const v of views) {v.view.destroy();v.parent.destroy();} views=[];
    if(c) c.destroy();c=null;wait(50);
    ToastService.currentCategory="";ToastService.toastVisible=false;
   }
   function test_idle_closed() {
    create();compare(c.state,"OFF");compare(c.pollInterval,300000);verify(!c.clockRunning);
    const n=c.now;const count=samples;wait(1200);compare(c.now,n);compare(samples,count);
    const hidden=popout();wait(100);compare(samples,count);verify(!c.popoutVisible);
   }
   function test_open_close_and_duplicates() {
    create();const a=popout(),b=popout();const count=samples;
    a.parent.shouldBeVisible=true;verify(c.stale);verify(!c.canAct);compare(c.pollInterval,15000);
    b.parent.shouldBeVisible=true;tryVerify(()=>!c.stale,2000);compare(samples,count+1);
    compare(c.visiblePopouts.length,2);verify(!c.clockRunning);
    a.parent.shouldBeVisible=false;verify(c.popoutVisible);
    b.view.destroy();views.pop();b.parent.destroy();wait(50);
    verify(!c.popoutVisible);compare(c.pollInterval,300000);verify(!c.clockRunning);
   }
   function test_receiving_closed() {
    create(response(true));compare(c.pollInterval,30000);verify(c.clockRunning);verify(!c.popoutVisible);
    verify(c.active);verify(c.lastKnownActive);verify(!c.busy);verify(!c.lastKnownBusy);
    verify(!c.fastPolling);compare(c.freshnessLimit,45000);
    const count=samples;const n=c.now;wait(4000);compare(samples,count);verify(c.now>n);verify(c.timeLabel.length>0);
    // Exercise a full, unmodified background interval in addition to the benchmark.
    tryVerify(()=>samples>count,28000);compare(samples,count+1);verify(!c.stale);
   }
   function test_countdown_expiry() {
    const value=response(true);value.status.remaining=1;create(value);
    tryCompare(c,"timeLabel","Checking window expiry",2200);verify(c.active);
    compare(c.pollInterval,30000);configure(response());
    const poll=findChild(c,"statusPoll");poll.interval=200;poll.restart();
    tryCompare(c,"state","OFF",2000);verify(!c.clockRunning);
    poll.interval=Qt.binding(()=>c.pollInterval);compare(poll.interval,300000);
   }
   function test_send_completion_closed() {
    const value=response(true);value.busy=true;value.job={id:"send-closed",action:"send",state:"running",updated:Date.now()/1000};create(value);
    compare(c.state,"SENDING");compare(c.pollInterval,3000);
    const done=response();done.job={id:"send-closed",action:"send",state:"complete",updated:Date.now()/1000};configure(done);
    tryCompare(c,"busy",false,4000);compare(c.notifiedId,"send-closed");compare(ToastService.currentCategory,"dms-airdrop-sent-send-closed");
    verify(!c.popoutVisible);verify(!c.clockRunning);compare(c.pollInterval,300000);
   }
   function test_temporary_abandonment() {
    create();const value=response(true);value.session={owned:true,phase:"discovering",token:"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"};
    configure(value);c.refresh();tryVerify(()=>c.temporarySession,2000);
    compare(c.pollInterval,30000);verify(!c.fastPolling);
    c.selectedFiles=["/mock/file"];const expiry=findChild(c,"selectionExpiry");verify(expiry!==null);compare(expiry.interval,300000);
    expiry.interval=50;expiry.start();tryCompare(c,"state","OFF",3000);
    compare(c.selectedFiles.length,0);verify(!c.temporarySession);
   }
   function test_external_activation_reconciliation() {
    create();const poll=findChild(c,"statusPoll");compare(poll.interval,300000);
    configure(response(true));poll.interval=200;poll.restart();tryCompare(c,"state","RECEIVING",2000);
    poll.interval=Qt.binding(()=>c.pollInterval);compare(poll.interval,30000);verify(c.clockRunning);
   }
   function test_reload_receiving() {
    create(response(true));const view=popout();view.parent.shouldBeVisible=true;tryVerify(()=>!c.checking,2000);
    c.destroy();c=null;wait(50);verify(PluginService.getGlobalVar("dmsAirDrop","controller",null)===null);
    create(response(true));view.view.controller=c;tryVerify(()=>c.popoutVisible&&!c.stale,2000);compare(c.visiblePopouts.length,1);compare(c.pollInterval,3000);
   }
   function test_receiving_status_failure_retries() {
    create(response(true));configure({ok:false,code:"status",error:"Transient mock failure"});c.refresh();
    tryCompare(c,"state","UNKNOWN",2000);compare(c.pollInterval,30000);verify(!c.canAct);verify(c.lastKnownActive);verify(!c.lastKnownBusy);
    // An error must retain background reconciliation, and opening must retry now.
    const count=samples;configure(response());const view=popout();view.parent.shouldBeVisible=true;
    compare(c.pollInterval,3000);tryCompare(c,"state","OFF",2000);compare(samples,count+1);compare(c.pollInterval,15000);
    view.parent.shouldBeVisible=false;compare(c.pollInterval,300000);
   }
   function test_sending_status_failure_and_closed_failure_result() {
    const value=response();value.busy=true;value.job={id:"failed-send",action:"send",state:"running",updated:Date.now()/1000};create(value);
    configure({ok:false,code:"timeout",error:"Mock timeout"});c.refresh();tryCompare(c,"state","UNKNOWN",2000);compare(c.pollInterval,3000);
    const done=response();done.job={id:"failed-send",action:"send",state:"failed",message:"Mock transfer failure",updated:Date.now()/1000};configure(done);
    tryCompare(c,"notifiedId","failed-send",4000);verify(c.showResult);compare(c.pollInterval,300000);verify(!c.popoutVisible);
   }
   function test_clock_resume_peer_expiry() {
    create();verify(!c.clockRunning);c.peers=[{mac:"mock",label:"Mock"}];c.peersAt=Date.now()-20000;c.selectedPeer="mock";c.now=c.peersAt;
    const view=popout();view.parent.shouldBeVisible=true;compare(c.selectedPeer,"");verify(c.now>c.peersAt+15000);
    tryVerify(()=>!c.stale,2000);verify(!c.canSend);verify(!c.clockRunning);
    c.selectedFiles=["/mock/file"];verify(c.clockRunning);c.clearSelection(false);verify(!c.clockRunning);
   }
   function test_stale_deadline_and_recovery() {
    create();const deadline=findChild(c,"freshnessDeadline");verify(deadline.running);
    // A subsequent successful sample must re-arm even if its delay is equal.
    c.refresh();tryVerify(()=>!c.checking,2000);verify(deadline.running);
    c.sampledAt=Date.now()-c.freshnessLimit+120;
    tryVerify(()=>c.stale,1000);verify(!c.canAct);verify(!c.clockRunning);
    const view=popout();view.parent.shouldBeVisible=true;tryVerify(()=>c.canAct,2000);compare(c.state,"OFF");
    configure({ok:false,code:"missing",error:"Missing mock backend"});c.refresh();tryCompare(c,"state","UNAVAILABLE",2000);verify(!c.canAct);
    configure(response());c.refresh();tryVerify(()=>c.canAct,2000);
   }
   function test_old_preference_ignored() {
    PluginService.savePluginData("dmsAirDrop","idleInterval",10);create();compare(c.pollInterval,300000);
    PluginService.savePluginData("dmsAirDrop","openInterval",30);const view=popout();view.parent.shouldBeVisible=true;compare(c.pollInterval,30000);
    PluginService.savePluginData("dmsAirDrop","openInterval",15);
   }
   function test_unavailable_selection_expiry_returns_idle() {
    configure({ok:false,code:"missing",error:"Missing mock backend"});
    c=controllerFactory.createObject(window.contentItem);tryCompare(c,"state","UNAVAILABLE",2000);
    c.selectedFiles=["/mock/file"];c.startDiscovery();compare(c.pollInterval,3000);
    c.clearSelection();wait(100);verify(!c.prepareRequested);verify(!c.cleanupRequested);compare(c.pollInterval,300000);verify(!c.clockRunning);
   }
   function test_receiving_open_close() {
    create(response(true));const a=popout(),b=popout();const count=samples;
    // Almost-old background status becomes fresh immediately on opening.
    c.sampledAt=Date.now()-29000;c.syncClock();verify(!c.stale);
    const value=response(true);value.status.remaining=120;configure(value);
    a.parent.shouldBeVisible=true;verify(c.stale);compare(c.pollInterval,3000);
    b.parent.shouldBeVisible=true;tryVerify(()=>!c.stale,2000);compare(samples,count+2);
    compare(c.backend.remaining,120);compare(c.timeLabel,"2m remaining");
    const opened=samples;tryVerify(()=>samples>opened,4000);
    a.parent.shouldBeVisible=false;compare(c.pollInterval,3000);
    b.parent.shouldBeVisible=false;compare(c.pollInterval,30000);
    const closed=samples;wait(3500);compare(samples,closed);verify(c.clockRunning);
   }
   function test_receiving_modes_closed() {
    create();
    for(const mode of ["once","forever"]) {
     const value=response(true);value.status.mode=mode;value.status.remaining=null;
     configure(value);c.refresh();tryVerify(()=>!c.checking,2000);
     compare(c.pollInterval,30000);verify(!c.fastPolling);
     compare(c.timeLabel,mode==="once"?"Until one transfer arrives":"Until turned off");
    }
   }
   function test_temporary_discovery_and_leftover_phase() {
    create();c.selectedFiles=["/mock/file"];
    // A phase may survive a finished/failed worker; only its lock signals busy.
    for(const phase of ["discovering","cleanup-failed","cleaning","sending"]) {
     const value=response(true);value.session={owned:true,phase:phase,token:"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"};
     configure(value);c.refresh();tryVerify(()=>!c.checking,2000);
     verify(c.temporarySession);verify(!c.prepareRequested);verify(!c.cleanupRequested);compare(c.pollInterval,30000);
    }
    const count=samples;wait(3500);compare(samples,count);
   }
   function test_pending_work_priority() {
    create(response(true));
    c.pending="send";compare(c.pollInterval,3000);c.pending="";compare(c.pollInterval,30000);
    c.prepareRequested=true;compare(c.pollInterval,3000);c.prepareRequested=false;compare(c.pollInterval,30000);
    c.cleanupRequested=true;compare(c.pollInterval,3000);c.cleanupRequested=false;compare(c.pollInterval,30000);
    const value=response(true);value.busy=true;value.session={owned:true,phase:"cleaning"};
    configure(value);c.refresh();tryVerify(()=>!c.checking,2000);compare(c.state,"CLEANING");compare(c.pollInterval,3000);
    configure(response(true));tryCompare(c,"busy",false,4000);verify(!c.lastKnownBusy);compare(c.pollInterval,30000);
   }
   function test_external_send_and_authoritative_busy_recovery() {
    const value=response(true);value.external_send=true;create(value);compare(c.state,"SENDING");compare(c.pollInterval,3000);
    configure({ok:false,code:"timeout",error:"Mock timeout"});c.refresh();tryCompare(c,"state","UNKNOWN",2000);
    verify(c.lastKnownBusy);compare(c.pollInterval,3000);
    // Backend can confirm no worker even when receiver/radio status is unavailable.
    configure({ok:false,busy:false,external_send:false,code:"status",error:"Mock receiver failure"});
    tryCompare(c,"lastKnownBusy",false,4000);verify(c.lastKnownActive);compare(c.pollInterval,30000);
    configure(response(true));c.refresh();tryCompare(c,"state","RECEIVING",2000);compare(c.pollInterval,30000);
   }
   function test_receiving_stale_recovery_closed() {
    create(response(true));c.sampledAt=Date.now()-c.freshnessLimit+120;
    tryVerify(()=>c.stale,1500);verify(!c.canAct);compare(c.timeLabel,"");compare(c.pollInterval,30000);
    const value=response(true);value.status.remaining=60;configure(value);
    const poll=findChild(c,"statusPoll");poll.interval=200;poll.restart();tryVerify(()=>c.canAct,2000);
    compare(c.timeLabel,"1m remaining");poll.interval=Qt.binding(()=>c.pollInterval);compare(poll.interval,30000);
   }
  }
 }
}'''.replace('__HELPER__',json.dumps(str(wrapper))))
    result=subprocess.run(['qs','-p',str(shell/'polling.qml'),'--no-color'],env=environment(),capture_output=True,text=True,timeout=120)
    output=result.stdout+result.stderr;print(output)
    report=json.loads(next(line.split('MONITORING_RESULT ',1)[1] for line in output.splitlines() if 'MONITORING_RESULT ' in line))
    assert result.returncode==0 and report['failed']==0 and report['passed']>=21, report
    assert not any(s in output for s in ['TypeError','ReferenceError','Binding loop','Cannot assign','Error loading configuration'])
    logged=[json.loads(line) for line in calls.read_text().splitlines()]
    assert all(call[0] in ('fixture','status','peers','submit') for call in logged)
    assert all(json.loads(call[1])['action']=='cleanup-send' for call in logged if call[0]=='submit')
    print('PASS: 20 monitoring cases; all operations stayed in the fixture')
