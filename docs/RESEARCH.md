# 技术依据与采用范围

MicroBind 参考了跨服务分析、权限检查识别、数据库条件建模和程序证据组织等工作。下表记录方法与实现的对应关系；固定提交和所读文件保存在 [upstreams.json](upstreams.json)。该记录描述所审阅版本，不代表上游当前版本。

| 工作 | 参考内容 | MicroBind 中的对应实现 | 采用范围 |
| --- | --- | --- | --- |
| [NEO](https://github.com/columbia/neo/tree/65ec4e35a1db67159a9d89a59e3e28d30f665690) | 服务内事实与服务间通信连接，形成统一路径 | `service_edges`、`access_paths` 与参数绑定 | 独立实现；附原始样例；运行过作者离线示例，未复现完整 CodeQL/模型流程 |
| [MScan](https://github.com/LFYSec/MScan/tree/75e411368964e895eba0b0d4f6359d228d47da7b) | Feign 客户端与接收端的框架适配 | `frontend.Project._connect` 和调用实参映射 | 阅读 OpenFeignPlugin；未移植 Tai-e 分析器或执行完整评测 |
| [PCFinder](https://github.com/seclab-fudan/PCFinder/tree/41205551a8110935b80e2c0b010ac0c11f41d579) | 检查条件、身份变量与中断行为 | 拒绝分支、可信主体和路径事实 | 独立实现受支持的检查语义；未运行原算法或其真值评测 |
| [IRIS](https://github.com/iris-sast/iris/tree/3a12f45750f58135bcc58c7fdf4c20786b600e31) | 用程序路径定位源码，组织模型复核上下文 | `report.context_for`、`llm.review` | 参考 v2 的上下文组织；未执行论文模型实验 |
| [LLMxCPG](https://github.com/qcri/llmxcpg/tree/fd7af0df8d2221ec196b85bc460da5cb40f6866c) | 图路径到源码切片的接口分工 | 方法级上下文包和证据索引 | 未集成 Joern，当前片段不是最小 CPG 切片 |
| [BolaRay](https://github.com/BolaRay-d/BolaRay/tree/6b4e7150e1504bd7a28795c577c01997ce53edeb) | SQL 条件、参数和表关系 | SQLGlot 约束解析与 Java 实参绑定 | 未移植 PHP 分析环境或执行其数据集 |
| FixMeUp | 复用已有权限检查进行修复 | guard 复用与局部修复模板 | 方法参考，未复现原工具 |

## 选择这些方法的原因

跨服务分析的困难之一是连接丢失或对象对应错误。NEO 和 MScan 提供了明确的通信建模思路。本项目将服务名、HTTP 方法、路由和参数通道作为可检查字段，把相同对象的证据贯穿到 SQL 和修复计划。跨服务与模型结合已有相关研究，不能仅凭二者组合主张新方法。

PCFinder 对检查语义的处理提醒我们，出现授权调用并不等于操作已受保护。MicroBind 对可解析方法执行条件分支：忽略 `owns()` 的返回值不增加授权事实，拒绝分支结束后才保留相应条件。这一实现便于解释首批归属检查，但尚不能替代广泛的框架检查识别。

数据库条件与身份传播必须一起解释。SQL 中出现 `user_id` 不足以证明归属约束，还需确认实参来自可信主体。BolaRay 的条件表示提供了参考；本项目采用 SQLGlot 接入 Java/MyBatis。litemall 样例表明，动态查询构造仍是当前最直接的覆盖瓶颈。

IRIS 和 LLMxCPG 支持把程序证据与模型复核分开组织。现阶段先保留稳定的源码位置和关系，再让模型补充解释；模型只能引用已有证据 ID。后续是否引入图切片或模型规划，应以真实样例的覆盖、误报和成本比较决定。

## 代码和样例来源

上述工具的分析实现没有直接纳入 MicroBind。随包分发的是 NEO 与 litemall 的未修改测试源码，来源和许可见 [第三方材料](../THIRD_PARTY_NOTICES.md)。PCFinder 用于确认项目列表来源，litemall 的提交由本项目自行固定，不是论文指定实验版本。

[BACAgent](https://github.com/LFYSec/BACAgent/tree/1e872eb57e9f05422e4b4c096c97f446706de30d) 在所读提交中为待发布说明，未从中集成实现。完整论文基线、真实模型增益和复杂业务策略推断仍需单独开展实验。

需要重新阅读固定版本时，可执行：

```bash
python tools/fetch_upstreams.py --name neo --out out/upstreams
```

下载脚本不执行上游代码。NEO 离线示例的独立环境和运行命令见 [样例说明](PAPER_SAMPLE_TESTS.md)。
