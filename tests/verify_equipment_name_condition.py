from pathlib import Path
import sys
from copy import deepcopy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.runtime.simulation import SkillSequence, resolve_equipment_conditions
from backend.skill_groups.validation import validate_group

condition = {"equipmentName": "Shadow Heart", "effectIndex": 0, "effectName": "Shadow Buff"}
group = {
    "schemaVersion": 2,
    "id": "group",
    "name": "name condition",
    "job": "岩浆法师",
    "entry": "heal",
    "subgroups": [
        {
            "id": "start",
            "nextGroup": "start",
            "skills": [{"id": "heal", "skillId": "h", "next": "fire", "jumpCondition": condition}],
        },
        {"id": "end", "nextGroup": "end", "skills": [{"id": "fire", "skillId": "f", "next": ""}]},
    ],
}
skills = {key: {"job": "岩浆法师"} for key in ["h", "f"]}
row = {"name": "Shadow Buff"}
item = {"id": "copied-id", "name": "Shadow Heart", "triggerEffects": [row]}
saved = validate_group(group)
assert saved["subgroups"][0]["skills"][0]["jumpCondition"] == condition
seq = SkillSequence(saved, skills, "岩浆法师")
seq.advance([])
assert seq.current == "heal"
seq.advance([(dict(item, name="Other Heart"), None, row)])
assert seq.current == "heal"
seq.advance([(item, None, row)])
assert seq.current == "fire"
legacy = deepcopy(group)
legacy["subgroups"][0]["skills"][0]["jumpCondition"] = dict(
    equipmentId="original", effectIndex=0, effectName="Shadow Buff"
)
resolved = resolve_equipment_conditions(legacy, {}, {"original": dict(item, id="original")})
seq = SkillSequence(resolved, skills, "岩浆法师")
seq.advance([(item, None, row)])
assert seq.current == "fire"
assert "equipmentName" not in legacy["subgroups"][0]["skills"][0]["jumpCondition"]
print(
    "PASS: name-only persistence, copied IDs, wrong names, no proc, legacy compatibility and immutable groups"
)
