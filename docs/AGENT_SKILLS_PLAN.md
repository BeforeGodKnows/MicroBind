# 技能接口与扩展

技能是执行步骤，任务队列是调度入口。分析器不依赖 HTTP 或 SQLite，页面也不直接调用分析细节。该划分允许 CLI、工作台和后续规划器复用同一能力。

## 当前接口

`src/microbind/workflows/registry.py` 定义 `Skill`、`Context`、注册表、计划生成和执行器；`steps.py` 实现处理函数。`Skill` 声明 ID、版本、所需输入、产生的输出、能力和 handler。`Context` 保存源码与产物目录、项目属性、进度回调、共享结果和事件。

| ID | 输入 | 输出 | 调用条件 |
| --- | --- | --- | --- |
| `source.analyze` | 源码、项目配置 | project、result | 必选 |
| `model.review` | project、result | smart_done、模型意见 | 部署允许且任务开启 smart |
| `repair.propose` | project、result | fixed_source、补丁、复查 | 请求修复或验证 |
| `lab.verify` | result、fixed_source | runtime_done、验证记录 | 仅启用 verifier 的内置 demo |
| `report.export` | result | bundle、报告 | 必选 |

`make_plan` 生成固定顺序；`run_skill` 检查依赖并记录状态。`GET /api/skills` 直接返回注册表，结果中的 `skill_events` 记录实际执行。`permissions` 目前是能力声明；模型开关、可信靶场检查和容器部署承担相应限制，尚无通用插件沙箱。

新增内置技能时，在 `steps.py` 或单独模块实现 handler，再在注册表声明依赖和输出，并为输入缺失、执行失败及正常结果补充测试。仅需要修改的分析适配逻辑，应留在分析器中，不必拆成独立技能。上传项目不能注册可执行代码。

## 模型和 MCP

模型复核通过五个只读工具获取方法、SQL、路径和策略证据；MCP 服务将相同查询能力开放给外部客户端。工具协议解决调用方式，技能定义执行职责，两者不提供自主规划。

后续计划增加受信安装目录、声明文件、输入输出 schema、版本和预算校验。配置格式待执行器实现时一并确定，当前不支持从 `SKILL.md` 或 YAML 自动加载扩展。规划器应选择已注册技能，计划经校验后才交给执行器；运行记录需保留源码、配置和技能版本。

具体优先级和验收条件见 [路线图](ROADMAP.md)。
