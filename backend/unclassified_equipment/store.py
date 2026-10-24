import json
from datetime import datetime,timezone
from copy import deepcopy
from ..skills.store import SkillStore,SkillError
from .crawler import SOURCE_URL,CATEGORIES,fetch_equipment
class UnclassifiedEquipmentStore(SkillStore):
    def read(self):
        with self.lock:
            if not self.path.exists():return {'schemaVersion':1,'sourceUrl':SOURCE_URL,'equipment':[],'counts':{},'updatedAt':None}
            try:
                data=json.loads(self.path.read_text(encoding='utf-8'))
                if data.get('schemaVersion')!=1 or not isinstance(data.get('equipment'),list):raise ValueError()
                return data
            except (ValueError,TypeError) as error:raise SkillError('未分类装备库无法读取，原文件未覆盖',500) from error
    def merge(self,records,counts):
        with self.lock:
            data=self.read();by_id={item['id']:item for item in data['equipment']}
            added=sum(item['id'] not in by_id for item in records)
            for item in records:by_id[item['id']]=deepcopy(item)
            data.update(equipment=list(by_id.values()),sourceUrl=SOURCE_URL,counts={c:sum(i['category']==c for i in by_id.values()) for c,_ in CATEGORIES.values()},updatedAt=datetime.now(timezone.utc).isoformat())
            self._write(data)
            return {**data,'fetchedCounts':counts,'fetched':len(records),'added':added}
    def refresh(self):return self.merge(*fetch_equipment())
