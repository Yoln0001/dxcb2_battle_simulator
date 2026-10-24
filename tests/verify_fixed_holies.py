import sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.api.holies import HolyStore,presets
with tempfile.TemporaryDirectory() as d:
    store=HolyStore(Path(d)/'holies.json');store._write({'schemaVersion':1,'holies':[]});assert len(store.read()['holies'])==6
    rows=presets();extra={**rows[0],'id':'duplicate','attributes':{'strength':123}}
    store._write({'schemaVersion':1,'holies':rows+[extra]});data=store.read();assert len(data['holies'])==6 and data['legacyHolies'][0]['id']=='duplicate'
    selected=data['holies'][0];selected['attributes']['strength']=999
    store.save(selected,selected['id']);assert len(store.read()['holies'])==6 and store.read()['legacyHolies'][0]['id']=='duplicate'
print('PASS: empty libraries initialize all six professions; historical duplicates are archived and preserved after edits')
