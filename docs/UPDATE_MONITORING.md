# 自动更新监控与处置（OPS-008 / CR-026）

## 更新与验收

原定时更新保持工作日08:13 UTC（北京时间16:13），GitHub不保证准点。
使用Python 3.11、固定ubuntu-24.04和requirements.lock；先pip check、测试、lint、构建，
再检查six/pandas/tushare导入、Token和Tushare SSE交易日历。任何错误停止发布。
升级依赖应在独立分支更新两个requirements文件并通过全部检查，不在定时任务中自动升级。

生成后检查三个榜单交易日、完整行数/重复代码/价格、errors、七个数据文件生成时间，以及可用股票K线日期和收盘价。
自选股/创业板池采集错误、榜单数量不完整、未声明的价格缺失或默认盈利榜财报缺失阻止发布。
按原小市值榜业务规则，明确记录的单股history/financial及business缺失不换股、不填零，保留原排名与空值；
写入发布清单warnings、页面提示并保留独立告警，不把局部缺失误判为整站不更新。
辅助信息原有缺失标注规则保留，其显式errors也进入告警。
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
- 同类持续故障在上次Issue活动至少23小时后提醒一次；原因改变时立即更新一次，恢复时评论并关闭对应Issue。
- 发布成功但局部数据仍缺失时，deployment故障可恢复，freshness/数据可用性告警继续保留并列明股票与环节。
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

## 诊断产物与重试

生成数据在完整性检查前上传为dashboard-data，保留3天；同日缓存仅保存已有不含凭证的源响应目录。
失败时可从Actions下载产物检查errors；生成器也直接打印受影响代码与环节。
手动运行Deploy Dashboard可填写reuse_data_run_id，复用该次运行的产物，避免只修检查逻辑或前端时重新采集一小时。
复用前实时查询交易日历，拒绝过期交易日，保留原生成时间；仍执行全部完整性检查、发布标识/哈希及上线验证。
未填写输入时正常全量更新；缓存按北京时间同日和锁定依赖隔离，不替代业务上的最新数据校验。

## 覆盖边界

独立工作流仍与更新任务共用GitHub Actions；Actions整体停摆、工作流被禁用或仓库权限不足时，Issue告警也可能无法执行。
外部心跳监控需另接外部服务，目前未配置。首次推送后验证一次实际部署和监控；故障分支通过离线模拟测试，
不为演练故意破坏线上数据或发送虚假故障通知。

## 实施与验收记录（2026-11-08）

对应OPS-008 / CR-026 / ADR-020，指标公式与股票池筛选口径不变。

| 文件 | 修改目的 |
| --- | --- |
| requirements.txt、requirements.lock | 显式声明six并固定经过测试的完整依赖集合 |
| .github/workflows/deploy.yml | 前置检查、数据门禁、产物/缓存、复用、发布与线上哈希验收 |
| .github/workflows/monitor.yml | 独立日检、发布故障事件及GitHub Issue通知 |
| scripts/update_health.py、scripts/report_update_alert.py | 日历/完整性/哈希验证、错误摘要、告警去重和恢复 |
| scripts/generate_dashboard.py、scripts/generate_small_cap_dashboard.py | 无有效自选股时失败退出、打印明确的单股缺失记录 |
| src/UpdateHealthNotice.tsx、src/main.tsx | 过期/不可验证/局部缺失提示 |
| src/App.tsx、src/GrowthMarketPage.tsx、src/SmallCapMarketPage.tsx | 榜单请求禁用浏览器数据缓存 |
| tests/test_update_health.py | 14项监控回归及真实本地HTTP发布/篡改/明确缺失检测 |
| README.md、docs/REQUIREMENTS.md、docs/DECISIONS.md、docs/CHANGE_REQUESTS.md、docs/CHANGELOG.md、本文件 | 配置、验收、决定与维护流程 |

- 113项Python及11项Node测试、pip check、完整锁定版本与导入、lint/build及差异检查通过。
- Chrome在390/1280px检查正常、过期、不可验证及局部缺失四种状态；真实线上页面交易日正确、缺失提示一致、无横向溢出。未做手机真机验证。
- [全量发布42469663318](https://github.com/icefly1991/feng-team-stock-dashboard/actions/runs/42469663318)成功，自选股111只/两种复权、创业板池95只、小市值250/100名均为2026-11-06行情。
- [快速复用发布42474145494](https://github.com/icefly1991/feng-team-stock-dashboard/actions/runs/42474145494)跳过重新采集，完成113项测试、产物下载、最新日历复查、完整性和上线验证；发布标识为42474145494.1。独立客户端逐个核对七个JSON哈希，原文件生成时间全部保留。
- [Issue #2](https://github.com/icefly1991/feng-team-stock-dashboard/issues/2)已由自动化记录发布恢复并关闭；同一故障重复运行未重复建Issue。
- [Issue #1详细诊断](https://github.com/icefly1991/feng-team-stock-dashboard/issues/1#issuecomment-6720668457)保留两项历史数据覆盖告警：汉维科技920957有37个历史日线日期缺有效复权因子（2021-12-23至2022-06-14），惠同新材920751有254个（2021-11-08至2022-12-23）。已只读重放确认Missing adjustment factor；保留空值和当前口径，待数据补全或另行确认历史区间策略后重新生成，不能宣称完全健康。
