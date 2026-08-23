# Feng Team Stock Dashboard

## 项目简介

`feng-team-stock-dashboard` 是一个个人股票数据看板项目，面向 A 股自选股的趋势位置观察与指标对比。

项目当前采用静态站点方案：

1. Python 脚本拉取并计算数据
2. 生成前端可直接读取的 JSON
3. React 页面负责展示
4. GitHub Actions 构建并部署到 GitHub Pages

项目当前确认的核心目标：

- 快速查看股票相对年线的位置
- 快速查看股票年初至今涨跌幅
- 快速查看股票距离 52 周高点的位置
- 快速查看股票距离 52 周低点的位置
- 快速查看股票在 52 周高低区间内的位置
- 支持前复权与不复权两种数据口径切换
- 兼顾桌面端与移动端可读性

本项目不是高频交易系统、自动交易系统、券商终端、实时行情系统，也不直接生成投资建议。

## 核心功能

- 从 `Tushare` 获取股票日线数据
- 在 Python 数据层统一计算核心指标
- 生成 `public/data/dashboard.json`
- 前端支持按指标查看和排序
- 前端支持 `qfq` 与 `none` 两种复权口径切换
- 页面展示汇总统计
- GitHub Actions 自动构建并部署 GitHub Pages

当前已确认的顶部汇总统计项：

- 自选股总数
- 当日上涨家数
- 当日下跌家数

## 技术栈

- React 19
- TypeScript
- Vite
- Tailwind CSS
- Framer Motion
- Python 3.11
- Tushare
- GitHub Actions
- GitHub Pages

## 数据流程

```text
Tushare
-> Python 获取日线数据
-> Python 计算指标并导出 JSON
-> React 读取 public/data/dashboard.json
-> Vite 构建静态站点
-> GitHub Actions 部署到 GitHub Pages
```

补充说明：

- 核心指标当前由 [`scripts/data_pipeline/indicators.py`](./scripts/data_pipeline/indicators.py) 统一计算
- JSON 输出由 [`scripts/generate_dashboard.py`](./scripts/generate_dashboard.py) 触发
- 当前输出文件为 [`public/data/dashboard.json`](./public/data/dashboard.json)

## 本地运行

前端开发：

```bash
npm ci
npm run dev
```

前端检查与构建：

```bash
npm run lint
npm run build
```

Python 数据生成：

```bash
python -m pip install -r requirements.txt
python scripts/generate_dashboard.py
```

必需环境变量：

- `TUSHARE_TOKEN`

当前仓库说明：

- 存在 `npm run lint`
- 存在 `npm run build`
- 当前没有单独定义 `npm run typecheck`
- 当前没有定义 `npm test`

## 数据更新

- 数据生成入口：[`scripts/generate_dashboard.py`](./scripts/generate_dashboard.py)
- 当前输出文件：[`public/data/dashboard.json`](./public/data/dashboard.json)

当前确认存在的顶层 JSON 字段：

- `updated_at`
- `adjustments`
- `errors`，仅在有错误时出现

当前工作流会在以下场景触发：

- 推送到 `main`
- 手动触发 `workflow_dispatch`
- 工作日定时触发一次

当前仓库中的定时配置为工作日 `08:13 UTC`，约等于北京时间 `16:13`。

注意：

- GitHub Actions `schedule` 不保证严格准点执行
- 文档和需求不应把该时间表述为精确到分钟的承诺

## 构建和部署

- 前端构建命令：`npm run build`
- Pages 工作流文件：[`deploy.yml`](./.github/workflows/deploy.yml)
- Vite `base` 当前配置为 `/feng-team-stock-dashboard/`
- 对应配置文件：[`vite.config.ts`](./vite.config.ts)

说明：

- 可以确认项目面向 GitHub Pages 子路径部署
- 仓库中未直接写明完整公开站点 URL
- README 不对完整站点地址做猜测，请以仓库 Pages 配置为准

## 项目文档

- [项目长期规则](./PROJECT_RULES.md)
- [当前需求](./docs/REQUIREMENTS.md)
- [技术与产品决策](./docs/DECISIONS.md)
- [需求变更记录](./docs/CHANGE_REQUESTS.md)
- [版本变化记录](./docs/CHANGELOG.md)
- [指标口径补充说明](./docs/metric-definitions.md)

## 开发规则

开发或让 AI 修改本项目之前，先阅读：

1. `PROJECT_RULES.md`
2. `docs/REQUIREMENTS.md`
3. `docs/DECISIONS.md`
4. `docs/CHANGE_REQUESTS.md`

执行规则：

1. 所有功能性改动都应关联需求编号
2. 如果已确认需求需要修改，应先建立 Change Request
3. 聊天记录、临时想法和 AI 对话不能直接覆盖正式需求
4. 未经过正式记录的“优化”“美化”“顺手重构”不能直接改变指标口径、数据结构、部署流程或页面核心结构

可直接复用给 AI 的任务模板：

```text
请先阅读：

1. PROJECT_RULES.md
2. docs/REQUIREMENTS.md
3. docs/DECISIONS.md
4. docs/CHANGE_REQUESTS.md

本次任务只处理需求：<需求编号>

任务目标：
<具体目标>

允许修改：
<文件或目录>

禁止修改：
<文件、数据口径或功能>

验收标准：
1. ...
2. ...
3. ...

如果本次指令与已有需求冲突，请先指出冲突，不要直接覆盖原需求。

完成后请输出：
1. 修改文件列表
2. 每个文件的修改原因
3. 对应需求编号
4. 验收结果
5. 测试结果
6. 数据口径是否变化
7. 尚未解决的问题
```

## 免责说明

- 本项目用于个人研究、观察和记录，不构成投资建议
- 数据依赖第三方数据源和自动化任务，可能存在延迟、缺失或失败情况
- 页面展示的时间和数值应结合数据口径与生成时间一起理解，不能默认视为实时行情
