import json, socket, sys, tempfile, threading, time, urllib.request, urllib.error
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
import uvicorn
from backend.app import create_app
from backend.skills.store import ATTRS
with tempfile.TemporaryDirectory() as temp:
    app=create_app(Path(temp)/'skills.json',Path(temp)/'equipment.json',Path(temp)/'groups.json',Path(temp)/'configurations.json',Path(temp)/'raw.json',Path(temp)/'wiki.json')
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(app,log_level='error'));thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
    deadline=time.monotonic()+10
    while not server.started and time.monotonic()<deadline:time.sleep(.02)
    def request(method,route,body=None):
        req=urllib.request.Request(f'http://127.0.0.1:{port}'+route,method=method,headers={'Content-Type':'application/json'},data=json.dumps(body).encode() if body is not None else None)
        try:
            with urllib.request.urlopen(req,timeout=10) as response:return response.status,json.loads(response.read())
        except urllib.error.HTTPError as error:return error.code,json.loads(error.read())
    try:
        from backend.wiki_equipment.classifier import classify_all
        from backend.wiki_equipment.store import WikiEquipmentStore,progress
        raw=json.loads((root/'data/unclassified_equipment.json').read_text(encoding='utf-8'))['equipment'];items=classify_all(raw)
        assert len(items)==753
        tree=progress(items);assert tree['total']['converted']==451 and tree['total']['needsReview']==302
        by_name={i['name']:i for i in items}
        world=by_name['世界树之杖★'];assert world['startingBuff']['coefficients']['magic']==.73;assert world['triggerEffects'][0]['effect']['conversions'][1]['coefficients']['magic']==.85
        black=by_name['黑星★'];assert black['triggerEffects'][0]['effect']['coefficients']['magic']==12.5
        heart=by_name['影兽之心★'];assert heart['triggerEffects'][0]['triggerType']=='none' and heart['triggerEffects'][0]['effect']['maxStacks']==5
        assert by_name['碎魄大剑']['baseAttributes']['hitRate']['min']==-4
        assert by_name['古式刺剑']['baseAttributes']['weaponPower']['max']==180
        assert by_name['深邃之杖']['baseAttributes']['weaponPower']['value'] is None
        assert len(by_name['烈炎星陨杖']['startingEffects'])==2
        assert by_name['饮血剑']['extraAttributes'][0]['min']==25
        assert by_name['龙纹包']['baseAttributes']['load']['min']==5000
        assert any(d.get('parameters',{}).get('kind')=='regeneration' for d in by_name['战场余晖']['effectDefinitions'])
        assert any(d.get('parameters',{}).get('ratio')==.5 for d in by_name['朽梦行囊']['effectDefinitions'])
        app.state.wiki_equipment_store.import_library({'equipment':items})
        code,result=request('GET','/api/wiki-equipment');assert code==200 and len(result['equipment'])==753
        edited=json.loads(json.dumps(world));edited['reviewNotes']='人工核对';edited['baseAttributes']['magic']['min']=700;edited['classificationStatus']='reviewed';edited['crystal']={'enabled':True,'attributes':{'strength':3,'magic':12.5,'technique':0,'speed':0,'constitution':2}}
        code,result=request('PUT','/api/wiki-equipment/'+world['id'],edited);assert code==200,result
        restored=WikiEquipmentStore(Path(temp)/'wiki.json').read();stored=next(i for i in restored['equipment'] if i['id']==world['id']);assert stored['reviewNotes']=='人工核对' and stored['baseAttributes']['magic']['min']==700
        assert stored['crystal']==edited['crystal'];assert stored['source']==world['source'] and stored['effectDefinitions']==world['effectDefinitions']
        repeated=app.state.wiki_equipment_store.classify_missing(raw);assert repeated['added']==0;assert next(i for i in repeated['equipment'] if i['id']==world['id'])==stored
        assert app.state.equipment_store.read()['equipment']==[]
        assert request('GET','/api/equipment')[1]['equipment']==[]
        code,added=request('POST','/api/wiki-equipment/'+black['id']+'/promote',{});assert code==200 and not added['replaced']
        old=json.loads(json.dumps(world));old['id']='equipment_existing';old.pop('baseAttributes');old.pop('classificationStatus')
        old=app.state.equipment_store.save(old)['item'];assert old['baseAttributes']['magic']['value']==0
        code,result=request('POST','/api/wiki-equipment/'+world['id']+'/promote',{});assert code==200 and result['replaced'],result
        assert result['item']['crystal']==edited['crystal'];assert result['item']['id']=='equipment_existing' and result['item']['baseAttributes']['magic']['min']==700
        code,result=request('POST','/api/wiki-equipment/'+world['id']+'/promote',{});assert code==200 and len(result['equipment'])==2
        assert request('DELETE','/api/equipment/equipment_existing')[0]==200
        assert request('DELETE','/api/equipment/equipment_existing')[0]==404
        assert request('DELETE','/api/wiki-equipment/'+world['id'])[0]==200
        assert request('DELETE','/api/wiki-equipment/'+world['id'])[0]==404
        remaining=app.state.wiki_equipment_store.classify_missing(raw);assert remaining['added']==0 and all(i['id']!=world['id'] for i in remaining['equipment'])
        assert any(i['id']==black['id'] for i in app.state.equipment_store.read()['equipment'])
        print('PASS: all 753 typed records, negative/range/unknown stats, multiple start buffs, major coefficients, extra mechanisms, independent editable API and no custom overwrite')
    finally:
        server.should_exit=True;thread.join(5)
