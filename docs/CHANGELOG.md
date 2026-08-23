# Changelog

本文档记录已经完成并进入项目的变化。

## Unreleased

### Added

- [REQ-001] 建立项目文档治理体系，包括 `PROJECT_RULES.md`、`docs/REQUIREMENTS.md`、`docs/DECISIONS.md`、`docs/CHANGE_REQUESTS.md` 和 `docs/CHANGELOG.md`
- [ADR-006] 记录在仓库内维护正式规则、需求、决策与变更流程的长期决定
- [DATA-006] 增加基于最近 252 个交易日最低 `low` 的“距52周低点”指标
- [DATA-007] 增加当前收盘价在 52 周最高 `high` 与最低 `low` 之间的线性位置指标
- [UI-006] 增加“距52周低点”和“52周内位置”两个榜单选项

### Changed

- [REQ-001] 将 `README.md` 从模板内容改为项目入口文档，并加入运行、部署和文档索引说明

### Fixed

- [REQ-001] 补齐项目当前真实运行方式、数据入口和自动部署方式的文档说明，避免继续依赖聊天记忆
- [UI-006] 修复新增 52 周指标造成的表头竖排、指标单元格换行及错误保留高点列的问题
- [UI-006] 修复 52 周内位置的正号、颜色和进度条比例语义

### Removed

- 移除与当前项目无关的 Vite 模板型 README 内容
