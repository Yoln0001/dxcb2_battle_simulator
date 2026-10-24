import json
import socket
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
import uvicorn
from backend.app import create_app
from backend.equipment.store import EquipmentStore
from backend.skills.store import ATTRS,TARGETS

def sample(kind=None):
    rows=[{'target':a,'enabled':a=='strength','coefficients':dict.fromkeys(ATTRS,.1)} for a in TARGETS]
    effect=None
    if kind=='amplify':effect={'kind':kind,'conversions':rows}
    if kind=='trueDamage':effect={'kind':kind,'coefficients':dict.fromkeys(TARGETS+['weaponPower'],1)}
    if kind=='immediateAction':effect={'kind':kind}
    if kind=='debuff':effect={'kind':kind,'type':'slow','baseValue':1,'duration':8,'maxStacks':999,'coefficients':dict.fromkeys(TARGETS,.45)}
    if kind=='buff':effect={'kind':kind,'type':'strength','recipient':'allAllies','duration':10,'maxStacks':5,'conversions':rows}
    return {'schemaVersion':1,'name':'装备测试 '+str(kind),'category':'weapon','weaponJob':'狂战神','attackType':'physical','effectName':'测试效果','startingBuff':{'recipient':'self','coefficients':dict.fromkeys(TARGETS,.5),'target':'strength'},'triggerRate':70,'effect':effect}

with tempfile.TemporaryDirectory() as temp:
    path=Path(temp)/'equipment.json'
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(create_app(Path(temp)/'skills.json',path,configuration_file=Path(temp)/'configurations.json',wiki_equipment_file=Path(temp)/'wiki.json'),host='127.0.0.1',port=port,log_level='error'))
    thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
    deadline=time.monotonic()+10
    while not server.started and thread.is_alive() and time.monotonic()<deadline:time.sleep(.02)
    def request(route,method='GET',body=None):
        req=urllib.request.Request(f'http://127.0.0.1:{port}'+route,headers={'Content-Type':'application/json'},data=json.dumps(body).encode() if body is not None else None,method=method)
        try:
            with urllib.request.urlopen(req,timeout=5) as r:return r.status,r.read()
        except urllib.error.HTTPError as e:return e.code,e.read()
    try:
        assert server.started
        for asset in ['/','/js/equipment/model.js','/js/equipment/editor.js','/css/equipment-editor.css']:assert request(asset)[0]==200
        assert '/api/equipment' in json.loads(request('/openapi.json')[1])['paths']
        assert json.loads(request('/api/skills')[1])['skills']==[]
        saved=[]
        for kind in [None,'amplify','trueDamage','immediateAction','debuff','buff']:
            code,raw=request('/api/equipment','POST',sample(kind));assert code==201,raw
            item=json.loads(raw)['item'];saved.append(item)
            assert item['id'].startswith('equipment_')
            assert request('/api/equipment/'+item['id'])[0]==200
        assert len(EquipmentStore(path).read()['equipment'])==6
        for category in ['armor','accessory','stone']:
            code,raw=request('/api/equipment','POST',{**sample(),'category':category});assert code==201
            assert json.loads(raw)['item']['weaponJob']==''
        item=saved[0];changed={**item,'name':'更新后的装备'}
        assert request('/api/equipment/'+item['id'],'PUT',changed)[0]==200
        assert request('/api/equipment','POST',changed)[0]==409
        assert request('/api/equipment/import','POST',{'schemaVersion':1,'equipment':[changed]})[0]==200
        before=path.read_bytes()
        assert request('/api/equipment/import','POST',{'schemaVersion':1,'equipment':[item]})[0]==409
        bad=sample('debuff');bad['effect']['maxStacks']=1000
        assert request('/api/equipment','POST',bad)[0]==400
        assert request('/api/equipment','POST',{**sample(),'triggerRate':101})[0]==400
        assert path.read_bytes()==before
        assert not (Path(temp)/'skills.json').exists()
        # Exercise the Pydantic HTTP boundary, including the first-trigger projection.
        from backend.equipment.validation import AMPLIFICATION_ATTRS,AMPLIFICATION_TARGETS
        for trigger in ('receivedPhysical','receivedMagic'):
            conversions=[{'target':a,'enabled':a=='armor','coefficients':dict.fromkeys(AMPLIFICATION_ATTRS,0)} for a in AMPLIFICATION_TARGETS]
            next(r for r in conversions if r['target']=='armor')['coefficients']['armor']=.15
            payload={**sample(),'category':'accessory','name':'受击护甲增幅 '+trigger,'triggerEnabled':True,'triggerEffects':[{'name':'守护','triggerType':trigger,'probability':100,'effect':{'kind':'amplify','conversions':conversions}}]}
            code,raw=request('/api/equipment','POST',payload);assert code==201,raw
            saved_item=json.loads(raw)['item'];assert saved_item['attackType']==trigger
            assert next(r for r in saved_item['effect']['conversions'] if r['target']=='armor')['coefficients']['armor']==.15
            updated={**saved_item,'name':saved_item['name']+' 修改'}
            code,raw=request('/api/equipment/'+saved_item['id'],'PUT',updated);assert code==200,raw
            reloaded=json.loads(request('/api/equipment/'+saved_item['id'])[1]);assert reloaded['attackType']==trigger
            reloaded['id']='import-'+trigger;reloaded['name']+=' 导入'
            code,raw=request('/api/equipment/import','POST',{'schemaVersion':1,'equipment':[reloaded]});assert code==200,raw
        print('PASS: HTTP create/update/read/import for received physical/magic triggers with armor self-amplification')
        shared={**sample(),'category':'accessory','name':'跨库装备','baseAttributes':{'magic':{'label':'魔力','min':100,'max':300,'value':None,'ownedValue':180}}}
        code,raw=request('/api/equipment','POST',shared);assert code==201,raw
        source_item=json.loads(raw)['item']
        code,raw=request('/api/library-sets/equipment','POST',{'name':'玩家甲','copy':True});assert code==201,raw
        library=json.loads(raw)['item']['id']
        copied=json.loads(request('/api/equipment?library='+library)[1])['equipment']
        player_item=next(row for row in copied if row['name']=='跨库装备')
        player_item['baseAttributes']['magic']['ownedValue']=290
        code,raw=request('/api/equipment/'+player_item['id']+'?library='+library,'PUT',player_item);assert code==200,raw
        assert json.loads(request('/api/equipment/'+source_item['id'])[1])['baseAttributes']['magic']['ownedValue']==180
        wiki_item={**source_item,'id':source_item['wikiId'],'baseAttributes':{'magic':{'label':'魔力','min':100,'max':300,'value':None,'ownedValue':220}}}
        code,raw=request('/api/wiki-equipment/'+source_item['wikiId'],'PUT',wiki_item);assert code==200,raw
        wiki_item=json.loads(raw)['item'];wiki_item['baseAttributes']['magic']['max']=250
        wiki_item['negativeImmunities']['immuneBurn']=True
        code,raw=request('/api/wiki-equipment/'+source_item['wikiId'],'PUT',wiki_item);assert code==200,raw
        assert json.loads(raw)['syncedEquipmentCount']==2
        for route,own,identifier in [('/api/equipment/'+source_item['id'],180,source_item['id']),('/api/equipment/'+player_item['id']+'?library='+library,290,player_item['id'])]:
            row=json.loads(request(route)[1]);assert row['id']==identifier
            assert row['baseAttributes']['magic']['max']==250 and row['baseAttributes']['magic']['ownedValue']==own
            assert row['negativeImmunities']['immuneBurn']
        player_item=json.loads(request('/api/equipment/'+player_item['id']+'?library='+library)[1])
        player_item['baseAttributes']['magic']['ownedValue']=200
        code,raw=request('/api/equipment/'+player_item['id']+'?library='+library,'PUT',player_item);assert code==200,raw
        assert json.loads(raw)['syncedEquipmentCount']==0
        assert next(r for r in json.loads(request('/api/wiki-equipment')[1])['equipment'] if r['id']==source_item['wikiId'])['baseAttributes']['magic']['ownedValue']==220
        player_item['mainAttribute']='magic'
        code,raw=request('/api/equipment/'+player_item['id']+'?library='+library,'PUT',player_item);assert code==200,raw
        assert json.loads(raw)['syncedEquipmentCount']==2
        for route,own in [('/api/equipment/'+source_item['id'],180),('/api/equipment/'+player_item['id']+'?library='+library,200)]:
            row=json.loads(request(route)[1]);assert row['mainAttribute']=='magic' and row['baseAttributes']['magic']['ownedValue']==own
        wiki_saved=next(r for r in json.loads(request('/api/wiki-equipment')[1])['equipment'] if r['id']==source_item['wikiId'])
        assert wiki_saved['mainAttribute']=='magic' and wiki_saved['baseAttributes']['magic']['ownedValue']==220
        for attr in ('strength','technique','speed','constitution'):
            player_item['mainAttribute']=attr
            code,raw=request('/api/equipment/'+player_item['id']+'?library='+library,'PUT',player_item);assert code==200,raw
            assert json.loads(request('/api/equipment/'+source_item['id'])[1])['mainAttribute']==attr
            assert next(r for r in json.loads(request('/api/wiki-equipment')[1])['equipment'] if r['id']==source_item['wikiId'])['mainAttribute']==attr
        assert request('/api/equipment/'+player_item['id']+'?library='+library,'PUT',{**player_item,'mainAttribute':'armor'})[0]==400
        print('PASS: five main attribute labels sync across all same-name libraries; personal values preserved; invalid labels rejected')
        player_item['name']='跨库装备改名';player_item['triggerEffects'][0]['probability']=25
        code,raw=request('/api/equipment/'+player_item['id']+'?library='+library,'PUT',player_item);assert code==200,raw
        assert json.loads(request('/api/equipment/'+source_item['id'])[1])['name']=='跨库装备改名'
        assert next(r for r in json.loads(request('/api/wiki-equipment')[1])['equipment'] if r['id']==source_item['wikiId'])['triggerRate']==25
        print('PASS: shared edits sync default/player/wiki libraries by old name; IDs and personal values preserved, personal-only edits isolated, range changes and rename supported')
        # Copy percentages affect only personal values in the new equipment library.
        attrs=('strength','magic','technique','speed','constitution')
        ranged={a:{'min':100,'max':300,'ownedValue':150} for a in attrs}
        ranged['weaponPower']={'min':532,'max':862,'ownedValue':600}
        ranged['armor']={'min':100,'max':300,'ownedValue':175}
        ranged['resistance']={'min':40,'max':120,'ownedValue':55}
        code,raw=request('/api/equipment','POST',{**sample(),'name':'复制百分比测试','mainAttribute':'speed','baseAttributes':ranged});assert code==201,raw
        original=json.loads(raw)['item']
        code,raw=request('/api/library-sets/equipment','POST',{'name':'百分比副本','copy':True,'attributePercentages':{'main':100,'other':50,'defense':25}});assert code==201,raw
        percent_library=json.loads(raw)['item']['id']
        rows=json.loads(request('/api/equipment?library='+percent_library)[1])['equipment']
        copied=next(r for r in rows if r['name']==original['name'])
        assert copied['id']==original['id'] and copied['wikiId']==original['wikiId'] and copied['mainAttribute']=='speed'
        for a in attrs:assert copied['baseAttributes'][a]['ownedValue']==(300 if a=='speed' else 200)
        assert copied['baseAttributes']['weaponPower']['ownedValue']==697
        assert copied['baseAttributes']['armor']['ownedValue']==150
        assert copied['baseAttributes']['resistance']['ownedValue']==60
        assert json.loads(request('/api/equipment/'+original['id'])[1])==original
        untagged=next(r for r in rows if r['name']==saved[1]['name'])
        assert untagged['mainAttribute']==''
        code,raw=request('/api/library-sets/equipment','POST',{'name':'保留副本','copy':True,'copyFrom':percent_library,'attributePercentages':{}});assert code==201,raw
        preserved=json.loads(request('/api/equipment?library='+json.loads(raw)['item']['id'])[1])['equipment']
        assert next(r for r in preserved if r['name']==original['name'])['baseAttributes']==copied['baseAttributes']
        code,raw=request('/api/library-sets/equipment','POST',{'name':'主属性零副本','copy':True,'attributePercentages':{'main':0}});assert code==201,raw
        zero=json.loads(request('/api/equipment?library='+json.loads(raw)['item']['id'])[1])['equipment']
        zero=next(r for r in zero if r['name']==original['name'])
        assert zero['baseAttributes']['speed']['ownedValue']==100 and zero['baseAttributes']['magic']['ownedValue']==150
        assert zero['baseAttributes']['weaponPower']['ownedValue']==600
        assert zero['baseAttributes']['armor']['ownedValue']==175
        assert zero['baseAttributes']['resistance']['ownedValue']==55
        code,raw=request('/api/library-sets/equipment','POST',{'name':'防御单独副本','copy':True,'attributePercentages':{'other':100,'defense':0}});assert code==201,raw
        defense=json.loads(request('/api/equipment?library='+json.loads(raw)['item']['id'])[1])['equipment']
        defense=next(r for r in defense if r['name']==original['name'])
        assert defense['baseAttributes']['armor']['ownedValue']==100 and defense['baseAttributes']['resistance']['ownedValue']==40
        assert defense['baseAttributes']['weaponPower']['ownedValue']==862 and defense['baseAttributes']['magic']['ownedValue']==300
        assert defense['baseAttributes']['speed']['ownedValue']==150
        code,raw=request('/api/library-sets/equipment','POST',{'name':'非主独立副本','copy':True,'attributePercentages':{'other':50}});assert code==201,raw
        separate=json.loads(request('/api/equipment?library='+json.loads(raw)['item']['id'])[1])['equipment']
        separate=next(r for r in separate if r['name']==original['name'])
        assert separate['baseAttributes']['armor']['ownedValue']==175 and separate['baseAttributes']['resistance']['ownedValue']==55
        before_index=request('/api/library-sets/equipment')[1]
        for bad in ({'main':101},{'other':-1},{'main':True},{'main':'50'},[],{'unknown':50},{'defense':101},{'defense':True}):
            assert request('/api/library-sets/equipment','POST',{'name':'无效副本','copy':True,'attributePercentages':bad})[0]==400
            assert request('/api/library-sets/equipment')[1]==before_index
        print('PASS: equipment copy main/other range percentages, blank preservation, 0/100 boundaries, source isolation and invalid input rejection')
        route='/api/library-sets/equipment/'+percent_library
        assert json.loads(request(route)[1])['attributePercentages']=={'main':100,'other':50,'defense':25}
        baseline=request('/api/equipment')[1]
        code,raw=request(route,'PUT',{'name':'属性已修改','attributePercentages':{'main':80,'other':20,'defense':60}});assert code==200,raw
        edited=next(r for r in json.loads(request('/api/equipment?library='+percent_library)[1])['equipment'] if r['id']==original['id'])
        assert edited['wikiId']==original['wikiId'] and edited['baseAttributes']['speed']['ownedValue']==260
        assert edited['baseAttributes']['magic']['ownedValue']==140 and edited['baseAttributes']['weaponPower']['ownedValue']==598
        assert edited['baseAttributes']['armor']['ownedValue']==220 and edited['baseAttributes']['resistance']['ownedValue']==88
        assert request('/api/equipment')[1]==baseline
        assert json.loads(request(route)[1])['attributePercentages']=={'main':80,'other':20,'defense':60}
        snapshot=request('/api/equipment?library='+percent_library)[1];index_snapshot=request('/api/library-sets/equipment')[1]
        assert request(route,'PUT',{'name':'不该生效','attributePercentages':{'main':101}})[0]==400
        assert request('/api/equipment?library='+percent_library)[1]==snapshot and request('/api/library-sets/equipment')[1]==index_snapshot
        assert request(route,'PUT',{'name':'玩家甲','attributePercentages':{'main':0}})[0]==409
        assert request('/api/equipment?library='+percent_library)[1]==snapshot
        assert request(route,'PUT',{'name':'只改名','attributePercentages':{}})[0]==200
        assert request('/api/equipment?library='+percent_library)[1]==snapshot
        assert request('/api/library-sets/equipment/__default__','PUT',{'name':'默认属性修改','attributePercentages':{'main':0,'defense':100}})[0]==200
        default=next(r for r in json.loads(request('/api/equipment')[1])['equipment'] if r['id']==original['id'])
        assert default['baseAttributes']['speed']['ownedValue']==100 and default['baseAttributes']['armor']['ownedValue']==300
        assert request('/api/library-sets/equipment/__wiki__','PUT',{'name':'百科属性修改','attributePercentages':{'other':30}})[0]==200
        team=json.loads(request('/api/equipment/team?library='+percent_library)[1])['equipment']
        team_item=next(r for r in team if r['id']==original['wikiId'])
        assert team_item['libraryRecordId']==original['id'] and original['id'] in team_item['identityAliases']
        assert team_item['baseAttributes']['speed']['ownedValue']==260
        default_team=next(r for r in json.loads(request('/api/equipment/team')[1])['equipment'] if r['id']==original['wikiId'])
        assert default_team['id']==team_item['id'] and default_team['baseAttributes']['speed']['ownedValue']==100
        print('PASS: team wearing uses encyclopedia ID unchanged across libraries; personal rolls follow selected library')
        print('PASS: in-place name/three percentage update, inferred current values, stable IDs, other library isolation, blank preservation, default/wiki support and no changes on invalid/duplicate name')
        path.write_text('broken',encoding='utf-8')
        assert request('/api/equipment','POST',sample())[0]==500
        assert path.read_text()=='broken'
        print('PASS: all equipment categories and effects; create/read/update/import; validation; persistence; skill isolation; corrupt-file preservation')
    finally:
        server.should_exit=True;thread.join(timeout=5);sock.close()
