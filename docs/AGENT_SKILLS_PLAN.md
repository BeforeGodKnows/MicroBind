# 技能接口与扩展

MicroBind 将分析、复核、修复、验证和报告导出分别注册为技能，由任务执行器按顺序调用。分析器独立于 HTTP 和 SQLite，CLI 与工作台复用同一套处理逻辑。

## 当前接口

`src/microbind/workflows/registry.py` 定义 `Skill`、`Context`、注册表和执行器，`steps.py` 实现具体处理函数。`Skill` 包含 ID、版本、输入、输出、操作能力和 handler；`Context` 保存源码目录、输出目录、项目属性、进度回调、共享结果及执行记录。

| ID | 输入 | 输出 | 执行条件 |
| --- | --- | --- | --- |
| `source.analyze` | 源码、项目配置 | project、result | 每次执行 |
| `model.review` | project、result | smart_done、模型意见 | 服务端启用模型，且任务开启 smart |
| `repair.propose` | project、result | fixed_source、补丁、复查结果 | 请求修复或运行验证 |
| `lab.verify` | result、fixed_source | runtime_done、验证记录 | 启用 verifier，且项目为内置 demo |
| `report.export` | result | bundle、报告 | 每次执行 |

`make_plan` 根据任务选项生成固定顺序，`run_skill` 检查依赖、调用 handler 并记录状态。`GET /api/skills` 返回注册表内容，任务结果中的 `skill_events` 保存实际执行记录。

`permissions` 列出技能需要的操作能力。当前限制由模型开关、内置靶场检查和容器配置实现，尚未提供通用插件沙箱。

## 添加内置技能

1. 在 `steps.py` 或独立模块中实现 handler。
2. 在注册表中声明输入、输出和所需能力。
3. 补充输入缺失、执行失败和正常完成的测试。

框架解析和分析规则仍放在分析器中，仅在需要独立执行步骤时新增技能。上传项目不能注册或执行自定义技能代码。

## 模型与 MCP

模型复核使用五个只读工具查询方法、SQL、路径和策略。MCP 服务将相同的证据查询工具提供给外部客户端。模型意见单独保存在结果中，不改写静态分析结论。

## 扩展计划

计划增加可信安装目录、技能声明文件、输入输出 schema，以及版本和执行上限校验。目前不支持从 `SKILL.md` 或 YAML 自动加载扩展。

任务规划器将从已注册技能中选择步骤，计划通过依赖和执行上限校验后再运行。运行记录需要保留源码、配置和技能版本，便于复现。具体顺序见 [开发计划](ROADMAP.md)。
