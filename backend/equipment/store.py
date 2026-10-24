from ..skills.store import SkillStore, SkillError
from .validation import validate_equipment, validate_library
import json

class EquipmentStore(SkillStore):
    def read(self):
            with self.lock:
                if not self.path.exists():
                    return {'schemaVersion': 1, 'equipment': []}
                try:
                    return validate_library(json.loads(self.path.read_text(encoding='utf-8')))
                except (ValueError, OSError) as error:
                    raise SkillError('装备文件无法读取，请修复或从备份恢复；原文件未覆盖', 500) from error
    
    def save(self, value, update_id=None):
            item = validate_equipment(value, generate_id=update_id is None)
            if update_id is not None and item['id'] != update_id:
                raise SkillError('路径ID与装备ID不一致')
            with self.lock:
                data = self.read()
                index = next((i for i, s in enumerate(data['equipment']) if s['id'] == item['id']), None)
                if update_id is None and index is not None:
                    raise SkillError('装备ID已存在，请使用更新接口', 409)
                if update_id is not None and index is None:
                    raise SkillError('装备不存在', 404)
                if index is None:
                    if len(data['equipment']) >= 5000:
                        raise SkillError('装备库最多5000条')
                    data['equipment'].append(item)
                else:
                    data['equipment'][index] = item
                self._write(data)
                return {**data, 'item': item}
    
    def delete(self,item_id):
        with self.lock:
            data=self.read()
            item=next((i for i in data['equipment'] if i['id']==item_id),None)
            if item is None:raise SkillError('装备不存在',404)
            data['equipment']=[i for i in data['equipment'] if i['id']!=item_id]
            self._write(data)
            return data

    def import_library(self, value):
            incoming = validate_library(value)
            with self.lock:
                data = self.read()
                existing = {s['id']: s for s in data['equipment']}
                for item in incoming['equipment']:
                    if item['id'] in existing and existing[item['id']] != item:
                        raise SkillError('同一ID的装备内容不同，未导入：' + item['name'], 409)
                    existing[item['id']] = item
                result = validate_library({'schemaVersion': 1, 'equipment': list(existing.values())})
                self._write(result)
                return result
