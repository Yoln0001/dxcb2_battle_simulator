from pathlib import Path
import json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.wiki_equipment.store import WikiEquipmentStore
if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    raw=json.loads((root/'data/unclassified_equipment.json').read_text(encoding='utf-8'))['equipment']
    result=WikiEquipmentStore(root/'data/wiki_equipment.json').classify_missing(raw)
    print(json.dumps({'added':result['added'],'progress':result['progress']},ensure_ascii=True))
