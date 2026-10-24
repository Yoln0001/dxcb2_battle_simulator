import json, socket, sys, tempfile, threading, time, urllib.request, urllib.error
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
import uvicorn
from backend.app import create_app
from backend.skills.store import ATTRS
with tempfile.TemporaryDirectory() as temp:
    app=create_app(Path(temp)/'skills.json',Path(temp)/'equipment.json',Path(temp)/'groups.json',Path(temp)/'configurations.json',Path(temp)/'raw.json')
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
        from backend.unclassified_equipment.crawler import parse_equipment,CATEGORIES
        records,counts=parse_equipment((root/'data/sources/bwiki_equipment.html').read_text(encoding='utf-8'))
        assert len(records)==753
        assert counts=={'sword':58,'axe':42,'dagger':49,'staff':62,'gun':41,'hammer':45,'armor':176,'accessory':280}
        first=next(i for i in records if i['name']=='古式刺剑');assert '136-180' in first['attributes'];assert first['effects']==''
        ice=next(i for i in records if i['name']=='冰晶剑');assert '20%' in ice['effects'] and '8秒' in ice['effects']
        assert not any(i['category'] in ('stone','ring') for i in records)
        result=app.state.unclassified_equipment_store.merge(records,counts);assert result['added']==753
        assert app.state.unclassified_equipment_store.merge(records,counts)['added']==0
        code,data=request('GET','/api/unclassified-equipment');assert code==200 and len(data['equipment'])==753
        snapshot=(Path(temp)/'raw.json').read_bytes()
        try:parse_equipment('<html>no equipment</html>')
        except ValueError:pass
        else:raise AssertionError('empty page must reject')
        assert (Path(temp)/'raw.json').read_bytes()==snapshot
        import backend.unclassified_equipment.store as module
        original=module.fetch_equipment
        module.fetch_equipment=lambda:(records,counts)
        try:
            code,result=request('POST','/api/unclassified-equipment/refresh',{});assert code==200 and result['fetched']==753 and result['added']==0
        finally:module.fetch_equipment=original
        print('PASS: eight categories, 753 real entries, names/properties/effects, stable IDs, duplicate-safe refresh and API')
    finally:
        server.should_exit=True;thread.join(5)
