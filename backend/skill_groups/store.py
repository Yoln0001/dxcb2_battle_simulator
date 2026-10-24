from ..skills.store import SkillStore, SkillError
from .validation import validate_group, validate_library
import json

class SkillGroupStore(SkillStore):
    def read(self):
            with self.lock:
                if not self.path.exists():
                    return {'schemaVersion': 2, 'groups': []}
                try:
                    return validate_library(json.loads(self.path.read_text(encoding='utf-8')))
                except (ValueError, OSError) as error:
                    raise SkillError('技能组文件无法读取，请修复或从备份恢复；原文件未覆盖', 500) from error
    
    def save(self, value, update_id=None):
            item = validate_group(value, generate_id=update_id is None)
            if getattr(self, 'skill_store', None):
                if '__wait__' in item['selfBuff']+item['opening']:raise SkillError('等待只能用于子技能组')
                by_id = {skill['id']: skill for skill in self.skill_store.read()['skills']}
                for skill_id in item['selfBuff'] + item['opening'] + [skill_id for group in item['subgroups'] for node in group['skills'] for skill_id in ([node['skillId']]+([case['skillId'] for case in node['decision']['cases']]+[node['decision']['elseSkillId']] if node.get('decision') else []))]:
                    if skill_id=='__wait__':continue
                    if skill_id not in by_id or by_id[skill_id]['job'] != item['job']:
                        raise SkillError('技能不存在或与技能组职业不一致')
                for group in item['subgroups']:
                    for node in group['skills']:
                        for case in node.get('decision',{}).get('cases',[]):
                            buff=case.get('absentBuff')
                            if buff:
                                definition=by_id.get(buff['skillId'],{})
                                effect=definition.get('effect') or {}
                                if definition.get('job')!=item['job'] or effect.get('kind')!='buff' or effect.get('type')!=buff['type'] or definition.get('name')!=buff['skillName']:
                                    raise SkillError('指定增益的技能已变更，请重新选择')
                            if case.get('targetSelection')=='matchedMember':
                                definition=by_id.get(case['skillId'],{})
                                if definition.get('damageType')!='none' or definition.get('healingRecipient')=='allAllies':raise SkillError('对条件命中的成员释放需要单体回复技能')
            if update_id is not None and item['id'] != update_id:
                raise SkillError('路径ID与技能组ID不一致')
            with self.lock:
                data = self.read()
                index = next((i for i, s in enumerate(data['groups']) if s['id'] == item['id']), None)
                if update_id is None and index is not None:
                    raise SkillError('技能组ID已存在，请使用更新接口', 409)
                if update_id is not None and index is None:
                    raise SkillError('技能组不存在', 404)
                if any(s['id'] != item['id'] and s['name'].strip() == item['name'].strip() for s in data['groups']):
                    raise SkillError('技能组名称已存在，请更换名称', 409)
                if index is None:
                    if len(data['groups']) >= 5000:
                        raise SkillError('技能组库最多5000条')
                    data['groups'].append(item)
                else:
                    data['groups'][index] = item
                self._write(data)
                return {**data, 'item': item}
    
    def delete(self,item_id):
        with self.lock:
            data=self.read()
            if not any(g['id']==item_id for g in data['groups']):raise SkillError('技能组不存在',404)
            data['groups']=[g for g in data['groups'] if g['id']!=item_id]
            self._write(data)
            return data

    def import_library(self, value):
            incoming = validate_library(value)
            with self.lock:
                data = self.read()
                existing = {s['id']: s for s in data['groups']}
                for item in incoming['groups']:
                    if item['id'] in existing and existing[item['id']] != item:
                        raise SkillError('同一ID的技能组内容不同，未导入：' + item['name'], 409)
                    existing[item['id']] = item
                result = validate_library({'schemaVersion': 2, 'groups': list(existing.values())})
                names = [item['name'].strip() for item in result['groups']]
                if len(names) != len(set(names)):
                    raise SkillError('技能组名称重复，未导入，请更换名称', 409)
                self._write(result)
                return result
