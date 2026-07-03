# Ladder Buy Manager / 分档买入管理器需求说明

## 1. 项目目标

本项目用于管理股票、ETF、加密资产或私募资产的**分档买入计划**。

它不是完整的投资组合管理系统，也不负责盈亏统计、收益率分析、交易同步或自动交易。盈亏、实际成交价、实际成交金额等信息由券商或交易所系统查看即可。

本软件只解决一个核心问题：

> 当前价格是否已经跌到某个买入档位，而该档位尚未标记为已买入？

如果已经触发，则在界面中标红，提醒用户手动去券商或交易所执行买入。

---

## 2. 核心使用场景

用户为每个标的设置多个买入档位，例如：

- Lv1：第一笔买入，计划投入 5000 美元；
- Lv2：价格下跌到某个水平，计划投入 2500 美元；
- Lv3：继续下跌，计划投入 1250 美元；
- Lv4：继续下跌，计划投入 625 美元；
- Lv5：继续下跌，计划投入 312.5 美元；
- 后续可能继续增加 Lv6、Lv7 等。

用户每天手动刷新每个标的的当前价格。系统根据当前价格和各 Lv 的目标价格进行颜色提示。

---

## 3. 设计原则

1. **不要做宽表。**
   - 不要设计 `L1_price`, `L2_price`, `L3_price` 这样的字段。
   - 每个标的的每个 Lv 都应该是一条独立数据。

2. **使用父子表结构。**
   - `instruments` 表保存标的主数据。
   - `levels` 表保存每个标的下面的买入档位。

3. **每支标的可以有不同数量的 Lv。**
   - HSAI 可以有 6 个 Lv；
   - CRM 可以有 5 个 Lv；
   - BTC 可以有 8 个 Lv；
   - SGOV 可以没有 Lv。

4. **状态机极简化。**
   - 每个 level 只有一个执行状态：`executed = 0 / 1`。
   - 不需要复杂状态如 pending、triggered、paused、skipped。
   - 前端根据价格和 `executed` 实时判断颜色。

5. **只记录是否已买入。**
   - 点击“已买入”后，系统只记录：
     - `executed = 1`
     - `executed_at = 当前日期`
   - 不要求填写实际买入价、实际买入金额、手续费或备注。

6. **颜色即提醒。**
   - 不做独立提醒系统。
   - 不发邮件、不推送、不创建 alert 表。
   - 总览页和详情页通过颜色直接提示。

---

## 4. 数据库设计

推荐使用 SQLite 作为第一版数据库。

### 4.1 instruments 表

每支标的一条记录。

```sql
CREATE TABLE instruments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL UNIQUE,
    name TEXT,
    category TEXT,
    asset_type TEXT,
    current_price REAL,
    updated_at TEXT,
    is_active INTEGER DEFAULT 1,
    notes TEXT
);
```

字段说明：

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER | 主键 |
| symbol | TEXT | 标的代码，如 HSAI、CRM、CAT、BTC、OPENAI |
| name | TEXT | 标的名称 |
| category | TEXT | 分类，如 中概反转、软件成长、军工ETF、现金池 |
| asset_type | TEXT | stock / etf / crypto / private / cash |
| current_price | REAL | 用户手动更新的当前价格 |
| updated_at | TEXT | 当前价格更新时间 |
| is_active | INTEGER | 是否启用，1 为启用，0 为停用 |
| notes | TEXT | 可选备注 |

---

### 4.2 levels 表

每个标的、每个 Lv 一条记录。

```sql
CREATE TABLE levels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instrument_id INTEGER NOT NULL,
    level_index INTEGER NOT NULL,
    target_price REAL NOT NULL,
    planned_amount REAL NOT NULL,
    executed INTEGER DEFAULT 0,
    executed_at TEXT,
    FOREIGN KEY (instrument_id) REFERENCES instruments(id),
    UNIQUE (instrument_id, level_index)
);
```

字段说明：

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER | 主键 |
| instrument_id | INTEGER | 所属标的 id |
| level_index | INTEGER | 档位编号，例如 1、2、3、4、5、6 |
| target_price | REAL | 触发价格 |
| planned_amount | REAL | 该档计划投入金额 |
| executed | INTEGER | 是否已买入，0 未买，1 已买 |
| executed_at | TEXT | 点击“已买入”时自动记录的日期 |

关键约束：

```sql
UNIQUE (instrument_id, level_index)
```

这保证同一个标的下面不能重复创建两个 Lv2。

---

## 5. 示例数据结构

### 5.1 instruments 示例

| id | symbol | name | category | asset_type | current_price | updated_at |
|---:|---|---|---|---|---:|---|
| 1 | HSAI | Hesai Group | 中概反转 | stock | 13.80 | 2026-07-02 |
| 2 | CRM | Salesforce | 软件成长 | stock | 245.00 | 2026-07-02 |
| 3 | SGOV | iShares 0-3 Month Treasury Bond ETF | 现金池 | etf | 100.35 | 2026-07-02 |

### 5.2 levels 示例

HSAI 的 Lv 数据：

| id | instrument_id | level_index | target_price | planned_amount | executed | executed_at |
|---:|---:|---:|---:|---:|---:|---|
| 1 | 1 | 1 | 18.00 | 5000 | 1 | 2026-07-01 |
| 2 | 1 | 2 | 14.40 | 2500 | 0 | NULL |
| 3 | 1 | 3 | 11.52 | 1250 | 0 | NULL |
| 4 | 1 | 4 | 9.22 | 625 | 0 | NULL |
| 5 | 1 | 5 | 7.37 | 312.5 | 0 | NULL |

如果以后为 HSAI 增加 Lv6：

```sql
INSERT INTO levels (
    instrument_id,
    level_index,
    target_price,
    planned_amount,
    executed
)
VALUES (
    1,
    6,
    5.90,
    156.25,
    0
);
```

---

## 6. 颜色判断规则

颜色不要存入数据库，应该由前端实时计算。

### 6.1 level 行颜色规则

```text
if executed == 1:
    灰色，表示已经买入

else if current_price <= target_price:
    红色，表示已经触发但尚未买入，需要立即处理

else:
    绿色，表示尚未触发，继续等待
```

推荐使用 `<=`，而不是 `<`。价格等于目标价时，也应视为触发。

### 6.2 前端伪代码

```js
function getLevelStatus(currentPrice, level) {
  if (level.executed === 1) {
    return "executed";     // 灰色
  }

  if (currentPrice === null || currentPrice === undefined) {
    return "unknown";      // 未更新价格
  }

  if (currentPrice <= level.target_price) {
    return "triggered";    // 红色
  }

  return "pending";        // 绿色
}
```

颜色映射：

```js
const levelColor = {
  executed: "gray",
  triggered: "red",
  pending: "green",
  unknown: "white"
};
```

---

## 7. 总览页逻辑

总览页每支标的一行。只要某支标的下面存在任意一个已触发但未执行的 Lv，这支标的整行就应该标红。

### 7.1 总览页判断逻辑

```js
function instrumentNeedsAction(instrument) {
  if (instrument.current_price === null || instrument.current_price === undefined) {
    return false;
  }

  return instrument.levels.some(level =>
    level.executed === 0 &&
    instrument.current_price <= level.target_price
  );
}
```

### 7.2 待处理金额

```js
function getPendingBuyAmount(instrument) {
  if (instrument.current_price === null || instrument.current_price === undefined) {
    return 0;
  }

  return instrument.levels
    .filter(level =>
      level.executed === 0 &&
      instrument.current_price <= level.target_price
    )
    .reduce((sum, level) => sum + level.planned_amount, 0);
}
```

### 7.3 待处理 Lv

```js
function getTriggeredLevels(instrument) {
  if (instrument.current_price === null || instrument.current_price === undefined) {
    return [];
  }

  return instrument.levels
    .filter(level =>
      level.executed === 0 &&
      instrument.current_price <= level.target_price
    )
    .map(level => `Lv${level.level_index}`);
}
```

---

## 8. 页面设计

### 8.1 总览页

总览页用于快速查看哪些标的需要处理。

建议列：

| 标的 | 名称 | 分类 | 当前价格 | 更新时间 | 已买入 Lv | 待处理 Lv | 待处理金额 | 状态 |
|---|---|---|---:|---|---|---|---:|---|
| HSAI | Hesai Group | 中概反转 | 13.80 | 2026-07-02 | Lv1 | Lv2 | 2500 | 需处理 |
| CRM | Salesforce | 软件成长 | 245.00 | 2026-07-02 | Lv1 | - | 0 | 正常 |
| SGOV | iShares 0-3 Month Treasury Bond ETF | 现金池 | 100.35 | 2026-07-02 | - | - | - | 现金池 |

总览页颜色：

- 如果该标的存在红色 Lv，则整行标红；
- 如果没有触发项，则正常显示；
- 已停用标的可以隐藏或灰色显示；
- 现金池 SGOV 可以单独显示，但不参与触发判断。

---

### 8.2 标的详情页

详情页显示某支标的下面所有 Lv。

顶部信息：

```text
标的：HSAI
名称：Hesai Group
分类：中概反转
当前价格：13.80
更新时间：2026-07-02
待处理 Lv：Lv2
待处理金额：2500
```

Lv 表格：

| Lv | 触发价格 | 计划投入 | 是否已买入 | 执行日期 | 状态 | 操作 |
|---:|---:|---:|---|---|---|---|
| Lv1 | 18.00 | 5000 | 是 | 2026-07-01 | 已买入 | 撤销 |
| Lv2 | 14.40 | 2500 | 否 | - | 需处理 | 标记已买入 |
| Lv3 | 11.52 | 1250 | 否 | - | 等待 | 标记已买入 |
| Lv4 | 9.22 | 625 | 否 | - | 等待 | 标记已买入 |
| Lv5 | 7.37 | 312.5 | 否 | - | 等待 | 标记已买入 |

详情页颜色：

- `executed = 1`：灰色；
- `executed = 0` 且 `current_price <= target_price`：红色；
- `executed = 0` 且 `current_price > target_price`：绿色。

---

### 8.3 标的管理页

用于新增、编辑、停用标的。

字段：

- symbol
- name
- category
- asset_type
- current_price
- notes
- is_active

功能：

- 新增标的；
- 编辑标的信息；
- 更新当前价格；
- 停用标的；
- 删除标的，第一版可以不做物理删除，只设置 `is_active = 0`。

---

### 8.4 Lv 管理功能

每个标的详情页应该可以新增、编辑、删除 Lv。

新增 Lv 字段：

- level_index
- target_price
- planned_amount

编辑 Lv 字段：

- target_price
- planned_amount
- executed

删除 Lv：

- 第一版可以直接删除；
- 或者不提供删除，只允许编辑。

---

## 9. 核心操作

### 9.1 手动更新当前价格

用户在总览页或标的管理页手动输入当前价格。

```sql
UPDATE instruments
SET current_price = ?,
    updated_at = DATE('now')
WHERE id = ?;
```

如果需要记录具体时间，可以使用：

```sql
UPDATE instruments
SET current_price = ?,
    updated_at = DATETIME('now')
WHERE id = ?;
```

第一版建议只记录日期即可。

---

### 9.2 标记某个 Lv 已买入

用户点击“标记已买入”。

```sql
UPDATE levels
SET executed = 1,
    executed_at = DATE('now')
WHERE id = ?;
```

不需要弹窗，不需要填写成交价或金额。

---

### 9.3 撤销已买入

防止误点，需要提供撤销按钮。

```sql
UPDATE levels
SET executed = 0,
    executed_at = NULL
WHERE id = ?;
```

---

### 9.4 新增 Lv

```sql
INSERT INTO levels (
    instrument_id,
    level_index,
    target_price,
    planned_amount,
    executed
)
VALUES (?, ?, ?, ?, 0);
```

如果同一标的下已经存在相同的 `level_index`，由于唯一约束，会插入失败。前端需要提示：

```text
该标的下已经存在相同 Lv，请修改 Lv 编号。
```

---

## 10. 推荐接口设计

如果使用前后端分离，可以提供如下 API。

### 10.1 获取总览数据

```http
GET /api/instruments
```

返回：

```json
[
  {
    "id": 1,
    "symbol": "HSAI",
    "name": "Hesai Group",
    "category": "中概反转",
    "asset_type": "stock",
    "current_price": 13.8,
    "updated_at": "2026-07-02",
    "is_active": 1,
    "levels": [
      {
        "id": 1,
        "level_index": 1,
        "target_price": 18.0,
        "planned_amount": 5000,
        "executed": 1,
        "executed_at": "2026-07-01"
      },
      {
        "id": 2,
        "level_index": 2,
        "target_price": 14.4,
        "planned_amount": 2500,
        "executed": 0,
        "executed_at": null
      }
    ]
  }
]
```

---

### 10.2 新增标的

```http
POST /api/instruments
```

请求体：

```json
{
  "symbol": "ITA",
  "name": "iShares U.S. Aerospace & Defense ETF",
  "category": "军工ETF",
  "asset_type": "etf",
  "current_price": 150.0,
  "notes": "军工长期成长仓"
}
```

---

### 10.3 更新当前价格

```http
PATCH /api/instruments/{instrument_id}/price
```

请求体：

```json
{
  "current_price": 13.8
}
```

---

### 10.4 获取单个标的详情

```http
GET /api/instruments/{instrument_id}
```

返回该标的及其全部 Lv。

---

### 10.5 新增 Lv

```http
POST /api/instruments/{instrument_id}/levels
```

请求体：

```json
{
  "level_index": 6,
  "target_price": 5.9,
  "planned_amount": 156.25
}
```

---

### 10.6 更新 Lv

```http
PATCH /api/levels/{level_id}
```

请求体示例：

```json
{
  "target_price": 14.4,
  "planned_amount": 2500
}
```

---

### 10.7 标记 Lv 已买入

```http
POST /api/levels/{level_id}/execute
```

行为：

```text
executed = 1
executed_at = 当前日期
```

---

### 10.8 撤销 Lv 已买入

```http
POST /api/levels/{level_id}/undo
```

行为：

```text
executed = 0
executed_at = null
```

---

## 11. 推荐技术栈

第一版推荐快速实现，不要过度工程化。

### 方案 A：最简单版本

```text
Python + Streamlit + SQLite
```

优点：

- 开发最快；
- 表格展示简单；
- 本地运行即可；
- 适合 20 支以内标的、100 个 Lv 左右的数据规模。

### 方案 B：标准 Web 版本

```text
FastAPI + SQLite + React/Vue
```

优点：

- 后续可扩展；
- 手机或局域网访问更方便；
- 前后端职责清晰。

如果目标是尽快可用，建议先做方案 A。后续稳定后再迁移到方案 B。

---

## 12. Streamlit MVP 页面建议

如果用 Streamlit，建议文件结构：

```text
ladder_buy_manager/
├── app.py
├── db.py
├── models.py
├── logic.py
├── portfolio.db
└── README.md
```

### app.py

负责页面展示：

- 总览页；
- 标的详情页；
- 新增标的；
- 新增 Lv；
- 更新价格；
- 标记已买入 / 撤销。

### db.py

负责数据库连接和 SQL 操作。

### logic.py

负责颜色和状态判断：

```python
def get_level_status(current_price, target_price, executed):
    if executed:
        return "executed"
    if current_price is None:
        return "unknown"
    if current_price <= target_price:
        return "triggered"
    return "pending"
```

---

## 13. 需要避免的功能

第一版明确不要做：

- 不统计盈亏；
- 不计算平均成本；
- 不导入 IBKR 交易记录；
- 不接实时行情；
- 不做复杂提醒；
- 不自动交易；
- 不做相关性分析；
- 不做资金曲线；
- 不记录实际成交价；
- 不记录实际成交金额；
- 不记录手续费。

核心原则：

> 只做分档买入计划的执行提示。

---

## 14. 第一版验收标准

第一版完成后，应满足以下条件：

1. 可以新增标的；
2. 可以为标的新增任意数量的 Lv；
3. 可以手动更新标的当前价格；
4. 总览页能显示全部标的；
5. 总览页能把存在“已触发未买” Lv 的标的整行标红；
6. 详情页能显示该标的全部 Lv；
7. 详情页能按规则将 Lv 显示为灰色、红色、绿色；
8. 点击“标记已买入”后，该 Lv 变为灰色，并自动记录日期；
9. 可以撤销“已买入”；
10. 可以新增 Lv6、Lv7 等，不需要修改表结构。

---

## 15. 当前颜色语义总结

```text
灰色：executed = 1，已经买入。
红色：executed = 0 且 current_price <= target_price，已经触发，需要处理。
绿色：executed = 0 且 current_price > target_price，尚未触发，继续等待。
白色/默认色：current_price 为空，价格未更新。
```

---

## 16. 项目一句话总结

Ladder Buy Manager 是一个极简的分档买入执行表：

> 每支标的有当前价格，每个 Lv 有触发价格和计划投入金额；如果当前价格低于未执行 Lv 的触发价格，就把该 Lv 和总览页对应标的标红，提醒用户手动买入。买完后点击“已买入”，该 Lv 变灰。
