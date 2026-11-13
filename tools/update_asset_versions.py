"""重算 frontend/index.html 中各 JS/CSS 引用的版本号（文件内容 SHA-256 的前 12 位）。

前端静态文件按“永久缓存”下发，浏览器只有在 ?v= 变化时才会重新下载。
修改或格式化 frontend/js、frontend/css 下的文件后运行：

    python tools/update_asset_versions.py
"""

import hashlib
import re
import sys
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
REFERENCE = re.compile(r'((?:src|href)="((?:js|css)/[^"?]+)\?v=)([0-9a-f]+)(")')


def version(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def update(index=FRONTEND / "index.html"):
    text = index.read_bytes().decode("utf-8")
    changed = []

    def replace(match):
        current = version(FRONTEND / match.group(2))
        if current != match.group(3):
            changed.append(match.group(2))
        return match.group(1) + current + match.group(4)

    updated = REFERENCE.sub(replace, text)
    if changed:
        index.write_bytes(updated.encode("utf-8"))
    return changed


if __name__ == "__main__":
    names = update()
    print("已更新 %d 个版本号" % len(names))
    for name in names:
        print("  " + name)
    sys.exit(0)
