# 地下城堡2模拟器

## 启动

- 网站与技能记录接口：在PyCharm运行根目录 `server.py`，打开 http://127.0.0.1:8000/ 。
- 原战力测试：运行根目录 `main.py`，默认100万次；快速测试运行 `python main.py --simulations 1000`。
- 仅查看输入界面：双击 `frontend/index.html`，此模式技能保存在浏览器里。

需要Python 3.10以上；首次运行在项目虚拟环境执行 `python -m pip install -r requirements.txt`。网站后端使用FastAPI + Uvicorn，技能JSON和现有前端保持兼容。

运行 `python server.py --reload` 可在修改后端时自动重启；接口测试页面为 http://127.0.0.1:8000/docs 。

## 目录

```text
战斗模拟器/
├── server.py                 网站启动入口
├── main.py                   战力测试启动入口
├── requirements.txt          Python依赖
├── backend/                  接口实现
│   ├── server.py              Uvicorn启动配置
│   ├── app.py                 FastAPI应用和网页托管
│   ├── api/skills.py           技能路由
│   ├── schemas/skills.py       Pydantic请求数据格式
│   └── skills/store.py        技能校验和文件存储
├── engine/                   战斗计算
│   ├── runner.py              四人配置及统计输出
│   ├── models.py              角色面板及角色接口
│   ├── battle.py              战斗循环
│   ├── formulas.py            伤害公式
│   ├── effects.py             装备效果
│   └── equipment.py           装备参数
├── frontend/                 网页
│   ├── index.html             页面入口
│   ├── css/                   页面样式
│   └── js/                    队伍输入和技能编辑脚本
├── data/                     技能等持久数据
├── tests/                    验证脚本
└── docs/                     使用说明及接口说明
```

技能保存后写入 `data/skills.json`，首次保存自动建立；整理目录不会迁移或覆盖既有数据。
若之前双击页面保存技能，先导出技能库，再在服务地址下导入。
当前技能创建、技能组和战斗计算分别独立；技能组编排和统一时间线尚未接入。

## 验证

- 技能接口：`python tests/verify_skill_api.py`，使用临时数据，测试结束自动停止服务。
- 原版对照：`python tests/verify_equivalence.py`，需要原始参考脚本；若自行修改公式，结果可能不同。

更多说明见 `docs/技能接口说明.md`、`docs/技能创建说明.md`、`docs/界面使用说明.txt`。
修改装备参数后应重新启动程序，让Numba重新读取。

## 自定义装备

页面工具栏点击“装备库”创建装备；服务模式保存到data/equipment.json，双击页面则保存在浏览器。
装备路由：backend/api/equipment.py；格式：backend/schemas/equipment.py；校验与存储：backend/equipment/。
装备界面及模型：frontend/js/equipment/。详情见docs/装备接口说明.md。
