# armadaDatabase

本项目提供了一个用于抓取 [Inteleria](https://www.inteleria.com/) 英雄页面基本资料与属性数据的轻量级工具集，并基于抓取结果构建 SQLite 本地数据库及简易的回合制战斗模拟器。

## 功能概览

- **页面解析**：无需额外依赖，通过内置的 HTML 解析器提取英雄的 Basic Info 与 Stats 表格。
- **数据存储**：将解析后的信息保存到 SQLite 数据库（默认 `champions.db`）。
- **命令行工具**：提供 `scraper` CLI 用于从本地 HTML 文件或网页地址导入数据，支持自动下载网页、批量导入、数据列表、展示与删除操作。
- **战斗模拟器**：`simulator` CLI 根据数据库中的属性（HP/ATK/DEF/SPD/暴击等）执行 deterministic 的回合制对战演算。

## 安装与测试

```bash
pip install -e .[dev]
pytest
```

## 使用示例

### 1. 采集英雄资料

```bash
python -m inteleria.scraper ingest --file path/to/abbess.html --slug abbess
python -m inteleria.scraper ingest --url https://www.inteleria.com/champion-list/abbess/
python -m inteleria.scraper download --output-dir saved_pages --slug abbess
```

> **提示**：`download` 子命令会自动下载并保存网页，以便离线导入。若直接抓取网页受限，可先手动保存网页再使用 `--file` 导入。

查看数据库中的英雄：

```bash
python -m inteleria.scraper list
```

展示指定英雄的详细数据：

```bash
python -m inteleria.scraper show abbess
```

### 1.1 批量导入 HellHades 名单

可使用 HellHades 英雄榜单一次性导入多个英雄：

```bash
python -m inteleria.scraper bulk --hellhades-file path/to/tier-list.html --inteleria-dir saved_pages
```

上述命令会读取保存的 HellHades 列表，依次加载 `saved_pages/<slug>.html` 内对应的 Inteleria 页面并写入数据库。
若未提前下载 Inteleria 页面，可移除 `--inteleria-dir`，工具会自动根据 slug 下载网页。
若希望在导入的同时缓存页面，可增加 `--save-html-dir saved_pages`。

也可以直接让工具完成“名单 + 页面”双重下载：

```bash
python -m inteleria.scraper download --output-dir saved_pages --hellhades-url https://hellhades.com/raid/tier-list/
python -m inteleria.scraper bulk --hellhades-url https://hellhades.com/raid/tier-list/ --inteleria-dir saved_pages
```

### 1.2 一键初始化 / 更新数据库

仓库提供了 `scripts/update_database.sh`，用于按照 HellHades 名单自动下载 Inteleria 英雄页面并写入数据库：

```bash
bash scripts/update_database.sh
```

默认会在项目根目录生成（或更新）`champions.db`，并将下载的 HTML 页面缓存在 `downloaded_pages/`。可通过环境变量进行定制：

| 环境变量 | 说明 | 默认值 |
| --- | --- | --- |
| `HELLHADES_URL` | HellHades 名单地址 | `https://hellhades.com/raid/tier-list/` |
| `CHAMPION_DB` | SQLite 数据库路径 | `champions.db` |
| `INTELERIA_CACHE_DIR` | HTML 缓存目录 | `downloaded_pages` |
| `LIMIT` | 限制导入的英雄数量（用于调试） | 空（全部导入） |

示例：

```bash
HELLHADES_URL=https://hellhades.com/raid/tier-list/ CHAMPION_DB=data/my.db bash scripts/update_database.sh
```

### 2. 运行战斗模拟

```bash
python -m inteleria.simulator abbess galek --seed 42 --show-log
```

模拟器会根据两名英雄的速度决定出手顺序，并依据攻击/防御/暴击属性计算伤害，直至一方 HP 为 0 或达到设定轮数。

## 开发说明

- HTML 解析位于 `src/inteleria/parser.py`，使用 `html.parser` 构建轻量树状结构以避免额外依赖。
- 数据库存储封装在 `src/inteleria/database.py`。
- 战斗逻辑位于 `src/inteleria/simulator.py`，默认暴击率/伤害会自动从百分比转换为小数。

欢迎根据实际数据结构调整解析逻辑或扩展更复杂的战斗模型。
