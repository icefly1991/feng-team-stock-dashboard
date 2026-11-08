# 自动更新监控与处置（OPS-008 / CR-026）

## 更新与验收

原定时更新保持工作日08:13 UTC（北京时间16:13），GitHub不保证准点。
使用Python 3.11、固定ubuntu-24.04和requirements.lock；先pip check、测试、lint、构建，
再检查six/pandas/tushare导入、Token和Tushare SSE交易日历。任何错误停止发布。
升级依赖应在独立分支更新两个requirements文件并通过全部检查，不在定时任务中自动升级。

生成后检查三个榜单交易日、完整行数/重复代码/价格、errors、七个数据文件生成时间，以及所有当前股票K线日期和收盘价。
核心榜单有采集错误时不发布残缺数据；辅助信息原有缺失标注规则保留。
生成update-health.json，包含本次run_id.attempt、交易日、日历和七个JSON的SHA256。
构建job输出发布标识供部署job使用；仅重跑失败的部署job时仍验证原构建产物，不会错误比较新的重跑次数。
上线后读取真实Pages地址，检查本次发布标识、文件内容哈希与核心榜单。
CDN传播最多检查5次、间隔20秒；HTTP请求有超时和有限重试。失败保留此前有效部署或已发布数据，报告异常；不伪造更新时间。
若部署本身成功、后验检查失败，Pages可能已上线新版本；监控不会自动回滚，需按日志处置。

## 独立检查

Monitor Dashboard Updates在北京时间每天08:07（计划时间，可能延迟）检查线上数据，也在部署成功后检查。
只使用Python标准库，不安装数据处理依赖。实时查询独立交易日历，检查前一自然日及以前最近开市日。
周末和节假日按真实开市日处理；日历权限/网络/覆盖缺失单独报错，不猜工作日、不拿旧日历当健康证明。
线上文件应与发布清单完全一致，三个榜单交易日不早于应有日期。

前端每5分钟刷新发布清单，交易日次日08:00后显示更新延迟提醒。
未来日历只在清单覆盖范围内使用，超过覆盖范围明确提示无法确认；各页原有行情/生成时间保留。

## GitHub告警

- deployment：Deploy Dashboard完成为失败、取消或超时，workflow_run触发告警；成功且后验通过才恢复。
- freshness：线上不可访问、清单缺失/不一致、交易日过期或日历不可用，创建独立告警。
- 每类只维护一个由github-actions[bot]创建且带固定隐藏标记的未关闭Issue；指派仓库所有者。
- 同类持续故障在上次Issue活动至少23小时后提醒一次；恢复时评论并关闭对应Issue。
- 失败步骤和日志链接写入deployment告警；freshness附具体检查错误与日志。失败日志不附Token或API响应。
- GitHub通知/邮件取决于用户设置。请在仓库Watch设置中开启Issues，或订阅告警Issue，并在个人Notifications中启用邮件。
- 未配置独立SMTP/短信/微信渠道，不承诺邮件必达。请以GitHub通知和Issue为准。

## 人工干预

1. 打开告警Issue中的Actions日志，确认是依赖、权限、接口、数据还是上线验证失败。
2. 依赖缺失：在两个requirements文件显式声明并固定版本，通过测试后推送。
3. Token/权限：在仓库Settings → Secrets and variables → Actions检查TUSHARE_TOKEN；不把Token贴到Issue。
4. 数据接口异常：等待源恢复，手动运行Deploy Dashboard；不要用旧文件改日期绕过检查。
5. 修复后手动运行Deploy Dashboard；发布验证和Monitor Dashboard Updates将自动记录恢复。
6. 可手动运行Monitor Dashboard Updates复查；若报警步骤自身失败，需查看该工作流的失败通知。

## 覆盖边界

独立工作流仍与更新任务共用GitHub Actions；Actions整体停摆、工作流被禁用或仓库权限不足时，Issue告警也可能无法执行。
外部心跳监控需另接外部服务，目前未配置。首次推送后验证一次实际部署和监控；故障分支通过离线模拟测试，
不为演练故意破坏线上数据或发送虚假故障通知。
