# Ladder Buy Manager / 分档买入管理器

一个本地运行的 Streamlit + SQLite MVP，用于记录每个标的的分档买入计划，并根据手动录入的当前价格提示已触发但尚未买入的档位。

## 功能

- 管理标的：新增、编辑、手动更新当前价格、停用。
- 管理档位：新增、编辑、删除任意数量的 LV。
- 状态实时计算：不把颜色或状态写入数据库。
- 总览页：显示 active 标的、当前价格、更新时间、建仓价、建仓时间、已买入档位数量和总档位数量；触发状态通过行颜色提示。
- 详情页：按档位显示已买入、需处理、等待、未更新价格。
- 网络更新价格：总览页操作栏可用刷新按钮从公开数据源更新当前价格。
- 快速创建分档计划：根据锚定价格、首档股数、触发比例和档位数量自动生成 levels，创建前可编辑。
- CSV 备份：导出 instruments 和 levels，并提供基础导入。

## 安装

```bash
pip install -r requirements.txt
```

## 初始化数据库

应用启动时会自动创建 SQLite 数据库：

```bash
streamlit run app.py
```

数据库文件为：

```text
ladder_buy_manager.sqlite3
```

如需插入示例数据：

```bash
python seed.py
```

## 启动

```bash
streamlit run app.py
```

## 行情数据

总览页每行的刷新按钮会从 Yahoo Finance 的公开 chart JSON 接口读取价格，并写入 `current_price` 和 `updated_at`。

- 当前实现优先取 `regularMarketPrice` 和 `regularMarketTime`。
- 如果没有实时字段，则退回最近一根日线的 `close`。
- 这个接口不需要 API key，适合本地手动更新，但不是正式 SLA 数据源。
- 如果以后需要更稳定的报价源，可以替换 `market_data.py`，例如接入 Alpha Vantage、Finnhub 或券商 API。

## 状态规则

- `executed = 1`：灰色，表示已经买入。
- `executed = 0` 且 `current_price <= target_price`：红色，表示已经触发，需要处理。
- `executed = 0` 且 `current_price > target_price`：绿色，表示等待触发。
- `current_price` 为空：未更新价格，不做红绿判断。

## 数据结构

`instruments`

- `id`
- `symbol`
- `name`
- `category`
- `current_price`
- `updated_at`
- `trigger_pct`
- `is_active`
- `notes`

`levels`

- `id`
- `instrument_id`
- `level_index`
- `target_price`
- `planned_amount`
- `executed`
- `executed_at`

`levels.instrument_id` 关联 `instruments.id`，并且同一个 `instrument_id` 下 `level_index` 不能重复。
