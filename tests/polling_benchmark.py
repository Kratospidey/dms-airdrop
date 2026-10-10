#!/usr/bin/env python3
"""Measure the real controller and backend with fixture-owned child executables.

No radio/systemd command reaches the host. Default measurement: five minutes,
excluding initial status. CPU includes QS and its mocked backend descendants.
"""
import argparse
import json
import resource
import shutil
import subprocess
import time
from pathlib import Path
from preview import ROOT, prepare, environment, write
from test_backend import BackendTests

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, default=ROOT)
parser.add_argument('--seconds', type=int, default=300)
parser.add_argument('--mode', choices=['idle', 'open', 'receiving'], default='idle')
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
fixture = BackendTests(); fixture.setUp()
try:
    if args.mode == 'receiving': fixture.receiving()
    records = fixture.home / 'measurements.jsonl'
    original = fixture.wrapper.read_text()
    original = original.replace('import sys\n', 'import sys,time,json,resource,atexit\n')
    original = original.replace('sys.exit(main(Backend(', '''started=time.time()
children=[]
class MeasuredBackend(Backend):
 def run(self, argv, *a, **kw):
  result=super().run(argv,*a,**kw)
  children.append(Path(argv[0]).name)
  return result
from pathlib import Path
def record():
 own=resource.getrusage(resource.RUSAGE_SELF); child=resource.getrusage(resource.RUSAGE_CHILDREN)
 with open(RECORDS,'a') as out: out.write(json.dumps(dict(started=started,command=sys.argv[1],children=children,cpu_seconds=own.ru_utime+own.ru_stime+child.ru_utime+child.ru_stime,elapsed_seconds=time.time()-started))+'\\n')
atexit.register(record)
assert sys.argv[1]=='status', 'Benchmark attempted a mutation'
sys.exit(main(MeasuredBackend(''').replace('RECORDS',repr(str(records)))
    fixture.wrapper.write_text(original)
    prepared = prepare()
    shell = fixture.home / 'shell'
    shutil.copytree(prepared,shell,symlinks=True)
    source = args.source.resolve()
    frozen = shell / 'MeasuredPlugin'
    for relative in (source / 'PUBLIC_FILES.txt').read_text().splitlines():
        target = frozen / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / relative, target)
    qml='''import QtQuick
import Quickshell
import "MeasuredPlugin" as Plugin
ShellRoot {
 Item {
  id: test
  property double start: 0
  property int clockChanges: 0
  Plugin.AirDropController {
   id: controller; helper: __HELPER__
   onHadStatusChanged: if (hadStatus && !test.start) {
    test.start=Date.now()+1000;
    __OPEN__
    finish.start();
   }
   onNowChanged: if (test.start && Date.now()>=test.start && Date.now()<test.start+__MS__) test.clockChanges++;
  }
  Timer { id: finish; interval: __MS__+1000; onTriggered: {
   console.warn("BENCHMARK_RESULT",JSON.stringify({start:test.start,end:test.start+__MS__,clock_changes:test.clockChanges})); Qt.quit();
  } }
  Timer { interval: __MS__+10000; running:true; onTriggered: {console.error("BENCHMARK_TIMEOUT");Qt.quit();} }
 }
}'''.replace('__HELPER__',json.dumps(str(fixture.wrapper))).replace('__MS__',str(args.seconds*1000)).replace('__OPEN__','controller.setPopoutVisible(test,true);' if args.mode=='open' else '')
    write(shell/'measure.qml',qml)
    env=environment(); env.update(HOME=str(fixture.home),XDG_CONFIG_HOME=str(fixture.config),XDG_RUNTIME_DIR=str(fixture.runtime))
    before=resource.getrusage(resource.RUSAGE_CHILDREN); started=time.monotonic()
    result=subprocess.run(['qs','-p',str(shell/'measure.qml'),'--no-color'],env=env,capture_output=True,text=True,timeout=args.seconds+20)
    after=resource.getrusage(resource.RUSAGE_CHILDREN)
    output=result.stdout+result.stderr
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.with_suffix('.log').write_text(output)
    line=next(line.split('BENCHMARK_RESULT ',1)[1] for line in output.splitlines() if 'BENCHMARK_RESULT ' in line)
    measurement=json.loads(line)
    rows=[json.loads(line) for line in records.read_text().splitlines()]
    measured=[r for r in rows if measurement['start']<=r['started']*1000<measurement['end']]
    report=dict(source=str(args.source.resolve()),mode=args.mode,seconds=args.seconds,status_invocations=len(measured),child_processes=sum(len(r['children']) for r in measured),child_tools=sorted({c for r in measured for c in r['children']}),backend_cpu_seconds=sum(r['cpu_seconds'] for r in measured),check_seconds=[r['elapsed_seconds'] for r in measured],status_offsets_seconds=[round(r['started']-measurement['start']/1000,3) for r in measured],clock_changes=measurement['clock_changes'],total_process_cpu_seconds=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,wall_seconds=time.monotonic()-started,max_rss_kib=after.ru_maxrss,initial_checks_excluded=len(rows)-len(measured))
    args.output.write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps(report,indent=2))
finally:
    fixture.tearDown()
