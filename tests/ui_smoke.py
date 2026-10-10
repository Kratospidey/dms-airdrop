#!/usr/bin/env python3
"""Actual installed DMS controls: responsive layout and synthetic input checks."""
import json
from pathlib import Path
import shlex
import shutil
import subprocess
from preview import ROOT, QA, prepare, environment, write

shell=prepare()
module=shell/'TestInput';module.mkdir(exist_ok=True)
build=ROOT/'.build/ui-input';build.mkdir(parents=True,exist_ok=True)
shutil.copy2(ROOT/'tests/ui_input.cpp',build/'ui_input.cpp')
flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Quick','Qt6Qml'],text=True))
moc_dir=subprocess.check_output(['pkg-config','--variable=libexecdir','Qt6Core'],text=True).strip()
subprocess.run([str(Path(moc_dir)/'moc'),*[flag for flag in flags if flag.startswith(('-I','-D'))],str(build/'ui_input.cpp'),'-o',str(build/'ui_input.moc')],check=True)
subprocess.run(['c++','-std=c++17','-shared','-fPIC',str(build/'ui_input.cpp'),'-o',str(module/'libuiinput.so'),*flags],check=True)
write(module/'qmldir','module TestInput\nplugin uiinput\n')
qml=(shell/'shell.qml').read_text().replace('import QtQuick\n','import QtQuick\nimport QtTest\nimport TestInput 1.0\n',1)
qml=qml.replace('Plugin.AirDropPopout { id: popout;', 'QtObject { id: host; property bool shouldBeVisible: true }\n            Plugin.AirDropPopout { id: popout; parentPopout: host;')
start=qml.index('    Timer {\n        interval: 1200')
qml=qml[:start]+r'''
    TestCase {
        id: tests; name: "NativeUi"; when: win.visible
        property int choices: 0
        property bool captured: false
        UiInput { id: nativeInput }
        onCompletedChanged: if(completed) console.warn("UI_RESULT",JSON.stringify({passed:qtest_results.passCount,failed:qtest_results.failCount}));
        function cleanup() { console.warn("UI_CASE",qtest_results.functionName,"failures",qtest_results.failCount); }
        function descendants(item) {
            let list=[item];for(const child of item.children||[])list=list.concat(descendants(child));return list;
        }
        function rows() { return descendants(popout).filter(item=>item.peer!==undefined); }
        function scroll() { return findChild(popout,"airDropScroll"); }
        function capture(name) {
            captured=false;canvas.grabToImage(result=>{result.saveToFile(__QA__+"/"+name+".png");captured=true;});tryVerify(()=>captured,2000);
        }
        function test_01_layout_themes_scale() {
            for(const light of [false,true]) for(const scale of [1,1.5]) for(const width of [380,300]) {
                Theme.isLightMode=light;Theme.fontSizeSmall=12*scale;Theme.fontSizeMedium=14*scale;Theme.fontSizeLarge=16*scale;
                popout.width=width;popout.availableHeight=600;popout.receiveOptions=true;popout.customDuration=true;
                mock.peers=[{mac:"aa:bb:cc:dd:ee:ff",name:"A very long Apple device name that must elide",label:"A very long Apple device name that must elide"}, {mac:"11:22:33:44:55:66",name:"Second phone",label:"Second phone"}];
                wait(100);verify(popout.height<=popout.availableHeight+1);
                for(const row of rows()) {
                    const text=findChild(row,"deviceLabels"),icon=findChild(row,"deviceIcon"),choice=findChild(row,"selectionIcon");
                    verify(text.width>0);verify(text.x>=icon.x+icon.width);verify(text.x+text.width<=choice.x);
                    verify(row.height>=text.implicitHeight+Theme.spacingM*2);
                    verify(row.x+row.width<=popout.width);
                }
                verify(scroll().clip);verify(scroll().verticalScrollBar.visible);
                if(light&&scale===1.5&&width===300)capture("ui-light-large-narrow");
                if(!light&&scale===1&&width===380)capture("ui-dark-default");
            }
        }
        function test_02_scrolling_and_small_display() {
            Theme.fontSizeSmall=12;Theme.fontSizeMedium=14;Theme.fontSizeLarge=16;popout.width=380;popout.availableHeight=300;
            mock.peers=Array.from({length:14},(_,i)=>({mac:"aa:bb:cc:dd:ee:"+String(i).padStart(2,"0"),name:"Device "+i,label:"Device "+i}));
            wait(100);const s=scroll();verify(s.contentHeight>s.height);verify(popout.height<=300);
            s.contentY=0;mouseWheel(s,s.width/2,s.height/2,0,-120);wait(50);verify(s.contentY>0);
            const before=s.contentY;mouseWheel(s,s.width/2,s.height/2,0,-15);wait(50);verify(s.contentY>before);
            const pixelBefore=s.contentY;const accepted=nativeInput.touchpad(s,-40);wait(50);
            console.warn("TOUCHPAD_INPUT",accepted,pixelBefore,s.contentY);verify(s.contentY>pixelBefore);
            verify(s.verticalScrollBar.opacity>0);
            s.flick(0,-1000);wait(200);verify(s.contentY>before);s.cancelFlick();
            s.contentY=s.contentHeight-s.height;verify(s.atYEnd);s.contentY=0;
            mock.peers=[];mock.selectedFiles=[];mock.active=false;popout.receiveOptions=false;popout.availableHeight=1400;wait(100);
            verify(!s.verticalScrollBar.visible);compare(s.contentY,0);
        }
        function test_03_device_input_and_busy_indicator() {
            Theme.isLightMode=false;popout.width=380;popout.availableHeight=850;mock.active=true;
            mock.peers=[{mac:"aa:bb:cc:dd:ee:ff",label:"First phone"},{mac:"11:22:33:44:55:66",label:"Other phone"}];
            mock.peersAt=Date.now();mock.now=Date.now();mock.selectedPeer="";wait(100);
            const row=rows()[1];const s=scroll();s.contentY=row.y;wait(50);
            row.forceActiveFocus();verify(row.activeFocus);keyClick(Qt.Key_Return);compare(mock.selectedPeer,row.peer.mac);
            mock.selectedPeer="";mouseMove(row,row.width/2,row.height/2);wait(50);
            verify(row.color.toString()===Theme.surfaceContainerHigh.toString());
            mouseClick(row,row.width/2,row.height/2);compare(mock.selectedPeer,row.peer.mac);
            mock.busy=true;s.contentY=s.contentHeight-s.height;wait(100);capture("ui-busy");
            host.shouldBeVisible=false;wait(50);verify(!popout.popoutOpen);mock.busy=false;
        }
    }
}'''.replace('__QA__',json.dumps(str(QA)))
write(shell/'ui.qml',qml)
env=environment();env['QML_IMPORT_PATH']=str(shell)
result=subprocess.run(['qs','-p',str(shell/'ui.qml'),'--no-color'],env=env,capture_output=True,text=True,timeout=30)
output=result.stdout+result.stderr;print(output)
report=json.loads(next(line.split('UI_RESULT ',1)[1] for line in output.splitlines() if 'UI_RESULT ' in line))
assert result.returncode==0 and report['failed']==0 and report['passed']>=4,report
assert not any(s in output for s in ['TypeError','ReferenceError','Binding loop','Cannot assign','Error loading configuration'])
print('PASS: 3 native UI cases; dark/light, 100%/150% fonts, narrow/tall content, wheel/high-resolution wheel/pixel-delta touchpad/flick, focus/hover/selection and busy preview')
