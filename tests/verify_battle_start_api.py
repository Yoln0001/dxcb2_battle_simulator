import sys, json, tempfile, socket, threading, time, urllib.request, urllib.error
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import uvicorn
from backend.app import create_app
from backend.equipment.validation import validate_equipment
with tempfile.TemporaryDirectory() as directory:
    root_temp=Path(directory)
    app=create_app(root_temp/'skills.json',root_temp/'equipment.json',root_temp/'groups.json')
    for equipment_id,category,ratio in [('weapon','weapon',.5),('accessory','accessory',.4)]:
        app.state.equipment_store.save({'schemaVersion':1,'id':equipment_id,'name':equipment_id,'category':category,'weaponJob':'法师','attackType':'magic','effectName':equipment_id,'startingBuff':{'enabled':True,'recipient':'self','coefficients':{'strength':0,'magic':ratio,'technique':0,'speed':0},'target':'magic'},'triggerRate':0,'effect':None})
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(app,log_level='error'));thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
    deadline=time.monotonic()+10
    while not server.started and time.monotonic()<deadline:time.sleep(.02)
    def request(payload):
        req=urllib.request.Request(f'http://127.0.0.1:{port}/api/battle/initialize',method='POST',headers={'Content-Type':'application/json'},data=json.dumps(payload).encode())
        try:
            with urllib.request.urlopen(req) as response:return response.status,json.load(response)
        except urllib.error.HTTPError as error:return error.code,json.load(error)
    try:
        payload={'target':{'hitPoint':1000000},'characters':[{'name':f'角色{i+1}','enabled':True,'job':'寒霜法师','stats':{'strength':100,'magic':10000,'technique':200,'speed':300},'equipment':{}} for i in range(4)]}
        payload['characters'][0]['equipment']={'weapon':'weapon','accessory2':'accessory'}
        code,result=request(payload);assert code==200,result;assert result['characters'][0]['stats']['magic']==21000;assert [b['amount'] for b in result['characters'][0]['buffs']]==[5000,6000]
        payload['characters'][0]['equipment']['weapon']='missing';assert request(payload)[0]==400
        assert request({'characters':[]})[0]==400
        assert len(app.state.equipment_store.read()['equipment'])==2
        print('PASS: battle initialization HTTP API, equipment persistence, compound buffs, error handling and isolation')
    finally:server.should_exit=True;thread.join(5)
