"""通用条目库：魔石、战利品、人物、Boss等“按名称唯一、整条替换”的库共用同一套读写逻辑。"""

import json

from .skills.store import SkillStore, SkillError


class LibraryStore(SkillStore):
    """子类只需声明key（JSON中的列表键）、label（提示用名称）和validate（条目校验函数）。"""

    key = ""
    label = ""
    limit = 5000
    validate = None

    def read(self):
        with self.lock:
            if not self.path.exists():
                return {"schemaVersion": 1, self.key: []}
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if data.get("schemaVersion") != 1 or not isinstance(data.get(self.key), list):
                    raise ValueError()
                return {
                    "schemaVersion": 1,
                    self.key: [self.validate(item, item["id"]) for item in data[self.key]],
                }
            except (ValueError, KeyError, TypeError) as error:
                raise SkillError(self.label + "库读取失败，原文件未覆盖", 500) from error

    def save(self, payload, item_id=None):
        item = self.validate(payload, item_id)
        with self.lock:
            data = self.read()
            items = data[self.key]
            if item_id and not any(i["id"] == item_id for i in items):
                raise SkillError(self.label + "不存在", 404)
            if any(i["name"] == item["name"] and i["id"] != item["id"] for i in items):
                raise SkillError(self.label + "名称已存在", 409)
            if not item_id and len(items) >= self.limit:
                raise SkillError(f"{self.label}库最多{self.limit}条")
            data[self.key] = [i for i in items if i["id"] != item["id"]] + [item]
            self._write(data)
            return {**data, "item": item}

    def delete(self, item_id):
        with self.lock:
            data = self.read()
            if not any(i["id"] == item_id for i in data[self.key]):
                raise SkillError(self.label + "不存在", 404)
            data[self.key] = [i for i in data[self.key] if i["id"] != item_id]
            self._write(data)
            return data


class IdLibraryStore(SkillStore):
    """域之环、契约等“按ID判重、原位替换”的库；read由子类实现（各自带预设和迁移）。"""

    key = ""
    label = ""
    validate = None

    def save(self, payload, item_id=None):
        item = self.validate(payload, item_id)
        with self.lock:
            data = self.read()
            index = next((n for n, i in enumerate(data[self.key]) if i["id"] == item["id"]), None)
            if item_id and index is None:
                raise SkillError(self.label + "不存在", 404)
            if not item_id and index is not None:
                raise SkillError(self.label + "ID已存在", 409)
            if index is None:
                data[self.key].append(item)
            else:
                data[self.key][index] = item
            self._write(data)
            return {**data, "item": item}

    def delete(self, item_id):
        with self.lock:
            data = self.read()
            rows = [i for i in data[self.key] if i["id"] != item_id]
            if len(rows) == len(data[self.key]):
                raise SkillError(self.label + "不存在", 404)
            data[self.key] = rows
            self._write(data)
            return data
