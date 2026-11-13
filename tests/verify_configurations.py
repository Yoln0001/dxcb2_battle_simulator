import json, socket, sys, tempfile, threading, time, urllib.request, urllib.error
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
import uvicorn
from backend.app import create_app
from backend.skills.store import ATTRS
with tempfile.TemporaryDirectory() as temp:
    app=create_app(Path(temp)/'skills.json',Path(temp)/'equipment.json',Path(temp)/'groups.json',Path(temp)/'configurations.json',trophy_file=Path(temp)/'trophies.json',people_file=Path(temp)/'people.json',stone_file=Path(temp)/'stones.json')
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(app,log_level='error'));thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
    deadline=time.monotonic()+10
    while not server.started and time.monotonic()<deadline:time.sleep(.02)
    def request(method,route,body=None):
        req=urllib.request.Request(f'http://127.0.0.1:{port}'+route,method=method,headers={'Content-Type':'application/json'},data=json.dumps(body).encode() if body is not None else None)
        try:
            with urllib.request.urlopen(req,timeout=5) as response:return response.status,json.loads(response.read())
        except urllib.error.HTTPError as error:return error.code,json.loads(error.read())
    try:
        config={'schemaVersion':1,'battle':{'duration':200,'simulations':100},'target':{'race':'傀儡','magicVulnerability':1},'characters':[{'name':f'角色 {i+1}','enabled':True,'firstStrike':False,'job':'寒霜法师','skillGroup':'saved-skill-group','stats':{'magic':12000+i,'constitution':3000},'equipment':{'weapon':'staff'},'contract':'不激活','negativeEffect':'无','skillMultiplier':1,'lifetime':200} for i in range(4)]}
        draft=json.loads(json.dumps(config));draft['configurationType']='special'
        for c in draft['characters']:
            c.update(job='',skillGroup='',equipment={},specialSources={'selectedPerson':None})
        draft['characters'][0]['equipment']={'weapon':'unfinished-gear'}
        code,saved_draft=request('POST','/api/configurations',{'name':'未选人物草稿','configuration':draft})
        assert code==201,saved_draft
        draft_id=saved_draft['item']['id'];draft_saved=saved_draft['item']['configuration']
        assert draft_saved['characters'][0]['equipment']=={'weapon':'unfinished-gear'}
        assert draft_saved['characters'][0]['specialSources']['selectedPerson'] is None
        assert not any(draft_saved['characters'][0]['stats'].values())
        assert draft_saved['characters'][0]['panelCalculationError']
        from backend.configurations.special import prepare_configuration
        from backend.skills.store import SkillError
        try:prepare_configuration(draft_saved,[])
        except SkillError:pass
        else:raise AssertionError('Simulation preparation must still reject incomplete equipment')
        code,updated=request('PUT','/api/configurations/'+draft_id,{'name':'草稿修改','configuration':draft_saved})
        assert code==200,updated
        assert next(i for i in request('GET','/api/configurations')[1]['configurations'] if i['id']==draft_id)['configuration']==updated['item']['configuration']
        assert request('DELETE','/api/configurations/'+draft_id)[0]==200
        print('PASS: incomplete draft create/update/reload without people; strict simulation preparation preserved')
        code,result=request('POST','/api/configurations',{'name':'队伍一','configuration':config});assert code==201,result
        first=result['item'];assert first['configuration']==config
        code,result=request('POST','/api/configurations',{'name':'队伍一 副本','configuration':config});assert code==201,result
        second=result['item'];assert second['id']!=first['id']
        changed=json.loads(json.dumps(config));changed['characters'][0]['stats']['magic']=1
        assert request('PUT','/api/configurations/'+second['id'],{'name':'修改副本','configuration':changed})[0]==200
        stored=request('GET','/api/configurations')[1];assert stored['configurations'][0]['configuration']==config
        assert request('POST','/api/configurations',{'name':'队伍一','configuration':config})[0]==409
        before_rename=request('GET','/api/configurations')[1]
        code,renamed=request('PUT','/api/configurations/'+first['id']+'/name',{'name':'圣者的幻影'})
        assert code==200 and renamed['item']['name']=='圣者的幻影',renamed
        assert renamed['item']['id']==first['id'] and renamed['item']['configuration']==config
        assert renamed['activeId']==before_rename['activeId'] and len(renamed['configurations'])==len(before_rename['configurations'])
        assert request('PUT','/api/configurations/'+first['id']+'/name',{'name':'修改副本'})[0]==409
        assert request('PUT','/api/configurations/'+first['id']+'/name',{'name':' '})[0]==400
        assert request('PUT','/api/configurations/missing/name',{'name':'未知'})[0]==404
        assert request('PUT','/api/configurations/'+first['id']+'/name',{'name':'队伍一'})[0]==200
        print('PASS: name-only update preserves team, ID, library, active selection; duplicate/empty/missing rejected')
        assert request('POST','/api/configurations',{'name':'坏配置','configuration':{}})[0]==400
        assert request('PUT','/api/configurations/missing',{'name':'未知','configuration':config})[0]==404
        assert request('POST','/api/configurations/'+first['id']+'/activate',{})[0]==200
        assert request('POST','/api/configurations',{'name':'导入配置','configuration':config,'activate':False})[0]==201
        from backend.configurations.store import ConfigurationStore
        restored=ConfigurationStore(Path(temp)/'configurations.json').read()
        assert restored['activeId']==first['id'];assert len(restored['configurations'])==3
        assert restored['configurations'][0]['configuration']['characters'][0]['skillGroup']=='saved-skill-group'
        assert request('DELETE','/api/configurations/'+second['id'])[0]==200
        assert app.state.configuration_store.read()['activeId']==first['id']
        assert request('DELETE','/api/configurations/'+second['id'])[0]==404
        assert request('DELETE','/api/configurations/'+first['id'])[0]==200
        stored=app.state.configuration_store.read();assert stored['activeId']=='';assert len(stored['configurations'])==1
        last=stored['configurations'][0]['id'];assert request('DELETE','/api/configurations/'+last)[0]==200
        empty=ConfigurationStore(Path(temp)/'configurations.json').read();assert empty['configurations']==[] and empty['initialized']
        special=json.loads(json.dumps(config));special['configurationType']='special'
        for c in special['characters']:
            c['equipment']={};c['specialSources']={'day10':{'magic':1000},'contract':{'magic':10},'holy':{'magic':100},'trophies':{'magic':20}}
        code,result=request('POST','/api/configurations',{'name':'特殊队伍','configuration':special});assert code==201,result
        assert result['item']['configuration']['characters'][0]['stats']['magic']==2160
        sid=result['item']['id'];assert next(i for i in request('GET','/api/configurations')[1]['configurations'] if i['id']==sid)['configuration']['characters'][0]['specialSources']['day10']['magic']==1000
        code,tr=request('POST','/api/trophies',{'name':'测试战利品','attributes':{'magic':5,'hitRate':3}});assert code==201,tr
        tid=tr['item']['id'];assert request('POST','/api/trophies',{'name':'测试战利品','attributes':{}})[0]==409
        assert request('POST','/api/trophies',{'name':'坏属性','attributes':{'unknown':1}})[0]==400
        assert request('POST','/api/trophies',{'name':'坏数值','attributes':{'magic':-1}})[0]==400
        special['characters'][0]['specialSources']['selectedTrophies']=[tr['item'],tr['item']]
        code,result=request('PUT','/api/configurations/'+sid,{'name':'特殊队伍','configuration':special});assert code==200,result
        assert result['item']['configuration']['characters'][0]['stats']['magic']==2340 and result['item']['configuration']['characters'][0]['stats']['hitRate']==11
        assert request('PUT','/api/trophies/'+tid,{'name':'修改战利品','attributes':{'magic':10}})[0]==200
        assert request('DELETE','/api/trophies/'+tid)[0]==200
        assert request('DELETE','/api/trophies/'+tid)[0]==404
        code,result=request('PUT','/api/configurations/'+sid,{'name':'特殊队伍','configuration':special});assert code==200 and result['item']['configuration']['characters'][0]['stats']['magic']==2340
        payload={'name':'测试人物','job':'寒霜法师','attributes':{'strength':123,'magic':456,'technique':789,'speed':100,'constitution':200,'armor':50,'resistance':60}}
        code,result=request('POST','/api/people',payload);assert code==201,result
        pid=result['item']['id'];assert result['item']['attributes']==payload['attributes']
        assert request('POST','/api/people',payload)[0]==409
        assert request('POST','/api/people',{**payload,'job':'未知职业'})[0]==400
        assert request('POST','/api/people',{**payload,'attributes':{'magic':-1}})[0]==400
        payload['attributes']['magic']=999;assert request('PUT','/api/people/'+pid,payload)[0]==200
        from backend.api.people import PeopleStore
        assert PeopleStore(Path(temp)/'people.json').read()['people'][0]['attributes']['magic']==999
        assert request('GET','/api/people')[1]['people'][0]['job']=='寒霜法师'
        assert request('DELETE','/api/people/'+pid)[0]==200 and request('DELETE','/api/people/'+pid)[0]==404
        stone={'name':'我的魔石','kind':'古精灵之石','attributes':{'magic':20,'hitRate':8}}
        code,result=request('POST','/api/stones',stone);assert code==201,result
        stone_id=result['item']['id'];assert result['item']['attributes']['magic']==20
        special['characters'][0]['specialSources']['selectedStone']=result['item']
        code,saved=request('PUT','/api/configurations/'+sid,{'name':'特殊队伍','configuration':special});assert code==200,saved
        assert saved['item']['configuration']['characters'][0]['specialSources']['stone']['hitRate']==8
        assert saved['item']['configuration']['characters'][0]['stats']['hitRate']==19
        assert request('PUT','/api/stones/'+stone_id,{**stone,'attributes':{'magic':25}})[0]==200
        assert request('POST','/api/stones',{**stone,'kind':'未知'})[0]==400
        assert request('DELETE','/api/stones/'+stone_id)[0]==200
        for kind,key,entry in [('people','people',{'name':'玩家人物','job':'寒霜法师','attributes':{'magic':100}}),('stones','stones',{'name':'玩家魔石','kind':'古精灵之石','attributes':{'magic':20}}),('trophies','trophies',{'name':'玩家战利品','attributes':{'magic':10}})]:
            code,new=request('POST','/api/library-sets/'+kind,{'name':'玩家甲'});assert code==201,new
            lid=new['item']['id'];assert request('GET','/api/'+kind+'?library='+lid)[1][key]==[]
            code,original=request('POST','/api/'+kind+'?library='+lid,entry);assert code==201,original
            code,copied=request('POST','/api/library-sets/'+kind,{'name':'玩家乙','copy':True,'copyFrom':lid});assert code==201,copied
            other=copied['item']['id'];rows=request('GET','/api/'+kind+'?library='+other)[1][key];assert len(rows)==1 and rows[0]['id']!=original['item']['id']
            changed={**entry,'attributes':{'magic':999}};assert request('PUT','/api/'+kind+'/'+rows[0]['id']+'?library='+other,changed)[0]==200
            assert request('GET','/api/'+kind+'?library='+lid)[1][key][0]['attributes']['magic']==entry['attributes']['magic']
            assert request('GET','/api/'+kind+'?library=missing')[0]==404
        gear_payload=json.loads((root/'data/equipment.json').read_text(encoding='utf-8'))['equipment'][0]
        code,library=request('POST','/api/library-sets/equipment',{'name':'玩家装备'});assert code==201,library
        lid=library['item']['id'];gear_payload['id']='test-player-gear'
        assert request('POST','/api/equipment?library='+lid,gear_payload)[0]==201
        assert any(i['id']=='test-player-gear' for i in request('GET','/api/library-sets/equipment/catalog')[1]['equipment'])
        code,copied=request('POST','/api/library-sets/equipment',{'name':'玩家装备副本','copy':True,'copyFrom':lid});assert code==201,copied
        other=copied['item']['id'];assert request('GET','/api/equipment?library='+other)[1]['equipment'][0]['id']=='test-player-gear'
        assert request('GET','/api/equipment')[1]['equipment']==[]
        with_libraries=json.loads(json.dumps(config));with_libraries['librarySelections']={'equipment':lid,'people':'','stones':'','trophies':''}
        code,saved=request('POST','/api/configurations',{'name':'保存玩家库','configuration':with_libraries});assert code==201,saved
        assert saved['item']['configuration']['librarySelections']==with_libraries['librarySelections']
        restored=request('GET','/api/configurations')[1];assert next(i for i in restored['configurations'] if i['id']==saved['item']['id'])['configuration']['librarySelections']['equipment']==lid
        with_libraries['librarySelections']['equipment']='missing';assert request('POST','/api/configurations',{'name':'不存在的库','configuration':with_libraries})[0]==404
        print('PASS: configuration preserves selected player libraries and validates missing references')
        boss={'name':'测试Boss','race':'龙','partyWipe':{'enabled':True,'time':123.5},'skillGroup':{'name':'火龙技能组','skills':[{'name':'龙息','damageType':'magic','targeting':'all','cooldown':3,'coefficients':{'magic':2}}]},'attributes':{'hitPoint':200000,'strength':400,'magic':500,'technique':600,'speed':700,'constitution':800,'armor':900,'resistance':1000},'targetRules':{'magicVulnerability':1.2,'immuneBurn':True}}
        code,created=request('POST','/api/bosses',boss);assert code==201,created
        zeros=dict.fromkeys(('strength','magic','technique','speed','constitution','hitPoint'),0)
        debuff={'kind':'debuff','type':'burn','applicationRate':150,'baseValue':100,'duration':8,'coefficients':{'strength':0,'magic':2,'technique':0,'speed':0}}
        buff={'kind':'buff','type':'magic','triggerRate':75,'baseValue':10,'duration':12,'recipient':'self','skillType':'damage','conversions':[{'target':k,'enabled':k=='magic','coefficients':{**zeros,'magic':.5}} for k in ('strength','magic','technique','speed')]}
        effects_boss={**boss,'name':'特效Boss','skillGroup':{'name':'附加特效组','skills':[{**boss['skillGroup']['skills'][0],'effect':debuff},{'name':'强化','damageType':'none','effect':buff,'healingRecipient':'allAllies'}]}}
        code,effects_saved=request('POST','/api/bosses',effects_boss);assert code==201,effects_saved
        effects_id=effects_saved['item']['id'];effects=request('GET','/api/bosses')[1]['bosses'][-1]['skillGroup']['skills']
        assert effects[0]['effect']['applicationRate']==150 and effects[0]['effect']['coefficients']['magic']==2
        assert effects[1]['effect']['conversions'][1]['coefficients']['magic']==.5
        assert effects[1]['healingRecipient']=='allAllies'
        bad={**effects_boss,'name':'错误特效','skillGroup':{'name':'错误','skills':[{'name':'错误','effect':{**buff,'triggerRate':101}}]}}
        assert request('POST','/api/bosses',bad)[0]==400
        assert request('DELETE','/api/bosses/'+effects_id)[0]==200
        print('PASS: Boss buff/debuff details persist, share player validation and reject invalid probabilities')
        boss_id=created['item']['id'];assert created['item']['attributes']['armor']==900
        assert created['item']['attributes']['hitPoint']==8000
        assert created['item']['partyWipe']=={'enabled':True,'time':123.5,'strategy':'all'}
        assert created['item']['hasSkills'] is True
        assert 'magicVulnerability' not in created['item']['targetRules']
        code,no_skills=request('POST','/api/bosses',{'name':'无技能Boss','hasSkills':False});assert code==201,no_skills
        assert no_skills['item']['hasSkills'] is True and no_skills['item']['skillGroup']['skills']==[]
        assert request('DELETE','/api/bosses/'+no_skills['item']['id'])[0]==200
        assert request('POST','/api/bosses',boss)[0]==409
        assert request('POST','/api/bosses',{**boss,'name':'错误Boss','attributes':{'magic':-1}})[0]==400
        assert request('PUT','/api/bosses/'+boss_id,{**boss,'name':'更新Boss'})[0]==200
        code,boss_library=request('POST','/api/library-sets/bosses',{'name':'Boss副本库','copy':True});assert code==201,boss_library
        bid=boss_library['item']['id'];assert request('GET','/api/bosses?library='+bid)[1]['bosses'][0]['id']!=boss_id
        cfg=json.loads(json.dumps(config));cfg['librarySelections']={'bosses':bid};cfg['target'].update(name=boss['name'],skillGroup=boss['skillGroup'],attributes=boss['attributes'],selectedBoss=created['item'])
        code,boss_saved=request('POST','/api/configurations',{'name':'保存Boss信息','configuration':cfg});assert code==201,boss_saved
        assert boss_saved['item']['configuration']['target']['selectedBoss']['id']==boss_id
        assert request('DELETE','/api/bosses/'+boss_id)[0]==200
        assert request('GET','/api/bosses')[1]['bosses']==[]
        copied_boss=request('GET','/api/bosses?library='+bid)[1]['bosses'][0]
        assert copied_boss['partyWipe']=={'enabled':True,'time':123.5,'strategy':'all'}
        assert copied_boss['skillGroup']['skills'][0]['name']=='龙息'
        copied_boss['skillGroup']['skills'][0]['name']='副本龙息'
        assert request('PUT','/api/bosses/'+copied_boss['id']+'?library='+bid,copied_boss)[0]==200
        assert boss_saved['item']['configuration']['target']['selectedBoss']['skillGroup']['skills'][0]['name']=='龙息'
        assert request('POST','/api/bosses',{**boss,'name':'技能无效','skillGroup':{'name':'错误','skills':[{'name':'错误技能','cooldown':-1}]}})[0]==400
        print('PASS: Boss CRUD, panel attributes, target rules, skill group, named copies and configuration snapshot')
        for kind in ('equipment','stones','people','trophies','bosses'):
            code,tmp=request('POST','/api/library-sets/'+kind,{'name':'待管理库'});assert code==201,tmp
            managed=tmp['item']['id'];before=request('GET','/api/'+kind+'?library='+managed)[1]
            code,renamed=request('PUT','/api/library-sets/'+kind+'/'+managed,{'name':'已重命名'});assert code==200,renamed
            assert next(i for i in renamed['libraries'] if i['id']==managed)['name']=='已重命名'
            assert request('GET','/api/'+kind+'?library='+managed)[1]==before
            assert request('POST','/api/library-sets/'+kind,{'name':'已重命名'})[0]==409
            assert request('PUT','/api/library-sets/'+kind+'/'+managed,{'name':' '})[0]==400
            assert request('DELETE','/api/library-sets/'+kind+'/'+managed)[0]==200
            assert not any(i['id']==managed for i in request('GET','/api/library-sets/'+kind)[1]['libraries'])
            assert request('GET','/api/'+kind+'?library='+managed)[0]==404
            assert request('DELETE','/api/library-sets/'+kind+'/'+managed)[0]==404
        print('PASS: four library rename/delete, stable IDs/data, duplicate names and missing-library rejection')
        print('PASS: four named libraries, full copies, independent IDs/edits, default isolation and equipment catalog')
        print('PASS: stone library CRUD, type validation and special configuration attribute snapshot')
        print('PASS: people API CRUD, profession validation, seven attributes and persistent storage')
        print('PASS: trophy CRUD, validation, selected snapshots, additive bonuses and configuration persistence')
        print('PASS: configuration API create, update, independent copy, import/export JSON, active restore, rejection and persistence')
        code,result=request('POST','/api/configurations/libraries',{'name':'常规攻略','configurationType':'regular'});assert code==201,result
        cid=result['library']['id']
        code,saved=request('POST','/api/configurations',{'name':'库内配置','configuration':config,'libraryId':cid});assert code==201,saved
        assert saved['item']['libraryId']==cid
        code,copied=request('POST','/api/configurations/libraries',{'name':'常规攻略备份','configurationType':'regular','copy':True,'copyFrom':cid});assert code==201,copied
        assert len([i for i in copied['configurations'] if i['libraryId']==copied['library']['id']])==1
        assert request('PUT','/api/configurations/libraries/'+cid,{'name':'新库名'})[0]==200
        assert request('DELETE','/api/configurations/libraries/'+cid)[0]==200
        assert request('DELETE','/api/configurations/libraries/default_regular')[0]==400
        print('PASS: configuration library HTTP create/copy/rename/delete and scoped configuration save')
    finally:
        server.should_exit=True;thread.join(5)
