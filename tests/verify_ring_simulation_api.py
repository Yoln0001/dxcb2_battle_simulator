import sys,json,tempfile,socket,threading,time,urllib.request
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import uvicorn
from backend.app import create_app
from backend.rings.store import presets
from backend.configurations.special import prepare_configuration

def run():
 with tempfile.TemporaryDirectory() as directory:
  temp=Path(directory)
  app=create_app(temp/'skills.json',temp/'equipment.json',temp/'groups.json',configuration_file=temp/'config.json')
  app.state.skill_store.save({'schemaVersion':1,'id':'ice','name':'测试','job':'寒霜法师','damageType':'magic','cooldown':-1,'hitRate':100,'criticalRate':0,'coefficients':{k:(1 if k=='magic' else 0) for k in ['strength','magic','technique','speed','constitution','hitPoint','weaponPower']},'raceBonus':{'race':'none','multiplier':0},'effect':None})
  app.state.group_store.save({'schemaVersion':2,'id':'loop','name':'测试循环','job':'寒霜法师','entry':'node','subgroups':[{'id':'sub','nextGroup':'sub','skills':[{'id':'node','skillId':'ice','next':''}]}],'opening':[],'selfBuff':[]})
  sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
  server=uvicorn.Server(uvicorn.Config(app,log_level='error'));thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
  deadline=time.monotonic()+10
  while not server.started and time.monotonic()<deadline:time.sleep(.02)
  def req(path,body=None):
   request=urllib.request.Request(f'http://127.0.0.1:{port}'+path,method='POST' if body is not None else 'GET',data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
   with urllib.request.urlopen(request) as response:return json.load(response)
  try:
   ring=next(r for r in presets() if r['kind']=='fire');ring.update(mainValue=0,secondaryValue=0,gain='physicalMagicDamage',gainValue=24.8)
   config={'configurationType':'special','seed':9,'battle':{'duration':2,'simulations':2},'target':{'hitPoint':1000000},'characters':[{'enabled':True,'job':'寒霜法师','equipment':{},'skillGroup':'loop','contract':'不激活','selectedRing':ring if i==0 else None,'stats':{'physicalDamage':24.8,'magicDamage':26.6},'specialSources':{'day10':{'magic':100,'constitution':100,'speed':100},'holyCustom':True,'imprintCustom':True,'trophies':{'magicDamage':1.8,'hitRate':100}}} for i in range(4)]}
   # Unsaved browser payload contains preview stats but no backend preview marker.
   initialized=req('/api/battle/initialize',config)
   assert initialized['characters'][0]['stats']['physicalDamage']==24.8
   assert initialized['characters'][0]['stats']['magicDamage']==26.6
   first=req('/api/battle/simulate-single',config)
   for frame in first['timeline']:
    stats=frame['snapshot']['characters'][0]['stats']
    assert stats['physicalDamage']==24.8 and stats['magicDamage']==26.6,stats
   prepared=prepare_configuration(config,[])
   second=req('/api/battle/simulate-single',prepared)
   assert first['total_damage']==second['total_damage'] and first['timeline']==second['timeline']
   job=req('/api/battle/simulate-batch',config);deadline=time.monotonic()+30
   while True:
    result=req('/api/battle/batch/'+job['job_id'])
    if result['status']!='running':break
    assert time.monotonic()<deadline
    time.sleep(.05)
   assert result['status']=='complete',result
   assert result['result']['engine']=='numba_njit',result
   assert abs(result['result']['expected_damage']-first['total_damage'])<1e-8,(result,first['total_damage'])
   print('PASS: unsaved HTTP initialize/single/batch and prepared payload retain 24.8% physical, 26.6% magic without duplicate ring gains')
  finally:server.should_exit=True;thread.join(5);sock.close()
if __name__=='__main__':run()
