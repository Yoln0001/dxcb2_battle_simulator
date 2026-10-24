"""Real HTTP TAS checks using temporary libraries."""
import sys,json,tempfile,socket,threading,time,urllib.request,urllib.error
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.app import create_app
import uvicorn
from verify_boss_combat import fixture


def main():
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory);app=create_app(root/'skills.json',root/'equipment.json',root/'groups.json',configuration_file=root/'config.json')
        cfg,_,skills,groups=fixture()
        for c in cfg['characters']:c['job']='寒霜法师'
        skills['s']['job']='寒霜法师';groups['g']['job']='寒霜法师'
        skill={**skills['s'],'schemaVersion':1,'id':'s','raceBonus':{'race':'none','multiplier':0}}
        skill['coefficients']={k:skill['coefficients'].get(k,0) for k in ('strength','magic','technique','speed','constitution','hitPoint','weaponPower')}
        app.state.skill_store.save(skill)
        app.state.group_store.save({**groups['g'],'schemaVersion':2,'id':'g','name':'测试','opening':[],'selfBuff':[]})
        sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        server=uvicorn.Server(uvicorn.Config(app,log_level='error'));thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
        until=time.monotonic()+10
        while not server.started and time.monotonic()<until:time.sleep(.02)
        def req(path,payload=None):
            request=urllib.request.Request('http://127.0.0.1:'+str(port)+path,method='POST' if payload is not None else 'GET',data=json.dumps(payload).encode() if payload is not None else None,headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(request) as response:return json.load(response)
        try:
            created=req('/api/battle/tas',cfg)
            assert created['time']==0 and created['step']==.1 and created['boss_attacks']
            identifier=created['id'];state=created
            def operation(**op):
                nonlocal state
                state=req('/api/battle/tas/'+identifier,{**op,'revision':state['revision']})
                return state
            while not state['pending_character']:operation(kind='step')
            before=state
            try:operation(kind='cast',character=state['pending_character'],skill_id='missing')
            except urllib.error.HTTPError as error:assert error.code==400
            else:raise AssertionError('invalid skill accepted')
            operation(kind='cast',character=state['pending_character'],skill_id='s')
            assert any(e['type']=='skill_released' for e in state['events'])
            try:req('/api/battle/tas/'+identifier,{'kind':'step','revision':0})
            except urllib.error.HTTPError as error:assert error.code==409
            else:raise AssertionError('stale revision accepted')
            operation(kind='seek',tick=0);assert state['time']==0
            operation(kind='seek',tick=15);assert state['time']==1.5
            request=urllib.request.Request('http://127.0.0.1:'+str(port)+'/api/battle/tas/'+identifier,method='DELETE')
            with urllib.request.urlopen(request) as response:assert json.load(response)['closed']
            try:operation(kind='step')
            except urllib.error.HTTPError as error:assert error.code==404
            else:raise AssertionError('closed session accepted')
            print('PASS: real HTTP TAS create, step, cast, rewind, revision conflict and session close')
        finally:server.should_exit=True;thread.join(5);sock.close()

if __name__=='__main__':main()
