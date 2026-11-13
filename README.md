# 地下城堡2模拟器

## 启动

- 网站与接口：在PyCharm运行根目录 `server.py`，打开 http://127.0.0.1:8000/ 。
- 原战力测试：运行根目录 `main.py`，默认100万次；快速测试运行 `python main.py --simulations 1000`。
- 仅查看输入界面：双击 `frontend/index.html`，此模式数据保存在浏览器里。

需要Python 3.10以上；首次运行在项目虚拟环境执行 `python -m pip install -r requirements.txt`。网站后端使用FastAPI + Uvicorn，批量模拟内核使用Numba。

`server.py` 默认在修改后端代码后自动重启；只是使用而不改代码时，运行 `python server.py --no-reload` 可避免重启并保留内存缓存。接口测试页面为 http://127.0.0.1:8000/docs 。服务只接受本机访问。

## 功能

- 队伍配置：角色面板、装备、魔石、战利品、圣迹、辉印、域之环、契约，以及可保存的配置库。
- 技能与技能组：技能库、技能组编排（条件、跳转、等待）。
- 敌方：Boss库，可设置面板、免疫、技能组和团灭规则。
- 单次模拟：0.1秒步进，返回时间表和状态快照。
- 批量模拟：后台任务、进度和取消，统计通过率、期望伤害、分位数和各角色特效触发次数。
- 单次和批量模拟各只有一个入口：所选Boss设置了技能组时自动包含Boss攻击，否则按普通模拟计算。
- TAS战斗播放器：手动或自动逐步操作并可回溯。
- 装备资料：从BWIKI抓取的未分类装备、整理后的百科装备库。
- 玩家库：各类库可建立多份独立副本，按配置选择使用。

## 目录

```text
dxcb2_battle_simulator/
├── server.py                 网站启动入口
├── main.py                   原战力测试启动入口
├── requirements.txt          Python依赖
├── backend/                  接口实现
│   ├── server.py              Uvicorn启动配置
│   ├── app.py                 FastAPI应用、各库初始化、路由注册、网页托管
│   ├── batch_jobs.py          批量模拟后台任务
│   ├── library_store.py       各条目库共用的读写逻辑
│   ├── api/                   各接口路由（battle、tas、skills、equipment、bosses等）
│   │   └── library_routes.py   各条目库共用的增删改查路由
│   ├── schemas/               Pydantic请求数据格式
│   ├── skills/                技能校验和文件存储（含读取缓存）
│   ├── skill_groups/          技能组校验和存储
│   ├── equipment/             自定义装备校验和存储
│   ├── wiki_equipment/        百科装备库及整理
│   ├── unclassified_equipment/ BWIKI装备抓取
│   ├── configurations/        队伍配置库及面板计算
│   ├── contracts/、rings/     契约、域之环
├── engine/                   战斗计算
│   ├── runner.py 等           原战力测试（main.py使用）
│   └── runtime/               网站使用的战斗引擎
│       ├── initialization.py   开战初始化
│       ├── simulation.py       单次模拟
│       ├── boss_simulation.py  含Boss攻击的模拟
│       ├── batch.py            批量模拟统计
│       ├── tas.py              TAS战斗
│       └── compiled/           Numba批量内核
├── frontend/                 网页
│   ├── index.html             页面入口
│   ├── css/                   页面样式
│   └── js/                    各功能脚本
├── data/                     持久数据（JSON）
│   ├── player_libraries/      玩家库副本
│   └── sources/               BWIKI抓取的原始页面
├── tools/                    装备抓取和整理的命令行工具
├── tests/                    验证脚本和性能基准
└── docs/                     使用说明及接口说明
```

各库保存后写入 `data/` 下对应的JSON文件，首次保存自动建立；写入采用先写临时文件再替换的方式，读取失败时不会覆盖原文件。
若之前双击页面保存过技能，先导出技能库，再在服务地址下导入。

## 验证

所有脚本从项目根目录运行，每个脚本独立执行，成功时打印 `PASS`。

- 后端和引擎：`python tests/verify_xxx.py`。名称带 `_api` 的脚本会用临时数据启动服务，结束后自动停止。
- 前端：`node tests/verify_xxx.cjs`，不需要浏览器。
- 性能基准：`python tests/benchmark_batch.py` 等。
- 原版对照：`python tests/verify_equivalence.py`，需要原始参考脚本（不在本仓库中）；若自行修改公式，结果可能不同。

## 说明文档

- 界面：`docs/界面使用说明.txt`
- 技能与技能组：`docs/技能创建说明.md`、`docs/技能接口说明.md`、`docs/技能组说明.md`
- 装备：`docs/装备接口说明.md`
- 战斗：`docs/战斗初始化说明.md`、`docs/单次模拟说明.md`、`docs/批量模拟说明.md`、`docs/tas.md`

修改 `engine/equipment.py` 中的装备参数后应重新启动程序，让Numba重新读取。
