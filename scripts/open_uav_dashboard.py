"""Start/reuse the local dashboard server and open its window. No training commands."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
from urllib.request import urlopen
import webbrowser

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'target/uav-dashboard'


def open_window(url):
    if os.name=='nt':
        for candidate in [Path(os.environ.get('PROGRAMFILES(X86)','C:/Program Files (x86)'))/'Microsoft/Edge/Application/msedge.exe',
                          Path(os.environ.get('PROGRAMFILES','C:/Program Files'))/'Microsoft/Edge/Application/msedge.exe']:
            if candidate.exists():
                subprocess.Popen([str(candidate),'--app='+url,'--window-size=1440,1000'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                return 'Edge app window'
    webbrowser.open_new(url);return 'Default browser'


def start(open_browser=True):
    OUT.mkdir(parents=True,exist_ok=True)
    marker=OUT/'server.json';url=None;reused=False
    if marker.exists():
        previous=json.loads(marker.read_text(encoding='utf-8'))
        try:
            with urlopen(previous['url']+'build.json',timeout=2) as response:
                if json.load(response).get('schema')=='uav-comparison-dashboard-v1':url=previous['url'];reused=True
        except (OSError,ValueError):pass
    if url is None:
        instance=uuid.uuid4().hex
        with (OUT/'server.log').open('a',encoding='utf-8') as log:
            proc=subprocess.Popen([sys.executable,'-u',str(ROOT/'scripts/uav_dashboard.py'),'--serve','--instance',instance],cwd=ROOT,
                    stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,
                    creationflags=(subprocess.CREATE_NO_WINDOW|subprocess.CREATE_NEW_PROCESS_GROUP) if os.name=='nt' else 0,
                    start_new_session=os.name!='nt')
        for _ in range(300):
            if proc.poll() is not None:raise RuntimeError('Dashboard server exited; inspect target/uav-dashboard/server.log')
            if marker.exists():
                info=json.loads(marker.read_text(encoding='utf-8'))
                if info.get('instance')==instance:
                    with urlopen(info['url']+'build.json',timeout=2) as response:json.load(response)
                    url=info['url'];break
            time.sleep(.1)
        if not url:raise TimeoutError('Dashboard server did not become ready')
    receipt=dict(url=url,reused_server=reused,opened=open_window(url) if open_browser else False)
    print(json.dumps(receipt,indent=2));return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--no-open',action='store_true');a=p.parse_args();start(not a.no_open)
