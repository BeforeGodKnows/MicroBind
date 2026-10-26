# 研究参考与实现

我们在实现 MicroBind 时，参考了跨服务分析、权限检查识别、数据库条件解析和源码证据组织等工作。下表列出具体借鉴点和实现范围，所使用的提交及文件记录在 [upstreams.json](upstreams.json)。

| 工作 | 参考内容 | MicroBind 中的对应实现 | 采用范围 |
| --- | --- | --- | --- |
| [NEO](https://github.com/columbia/neo/tree/65ec4e35a1db67159a9d89a59e3e28d30f665690) | 服务内事实与服务间通信连接，形成统一路径 | `service_edges`、`access_paths` 与参数绑定 | 独立实现；附原始样例；运行过作者离线示例，未复现完整 CodeQL/模型流程 |
| [MScan](https://github.com/LFYSec/MScan/tree/75e411368964e895eba0b0d4f6359d228d47da7b) | Feign 客户端与接收端的框架适配 | `frontend.Project._connect` 和调用实参映射 | 阅读 OpenFeignPlugin；未移植 Tai-e 分析器或执行完整评测 |
| [PCFinder](https://github.com/seclab-fudan/PCFinder/tree/41205551a8110935b80e2c0b010ac0c11f41d579) | 检查条件、身份变量与中断行为 | 拒绝分支、可信主体和路径事实 | 独立实现受支持的检查语义；未运行原工具或基于原始标注的评测 |
| [IRIS](https://github.com/iris-sast/iris/tree/3a12f45750f58135bcc58c7fdf4c20786b600e31) | 用程序路径定位源码，组织模型复核上下文 | `report.context_for`、`llm.review` | 参考 v2 的上下文组织；未执行论文模型实验 |
| [LLMxCPG](https://github.com/qcri/llmxcpg/tree/fd7af0df8d2221ec196b85bc460da5cb40f6866c) | 图路径到源码切片的接口分工 | 方法级上下文包和证据索引 | 未集成 Joern，当前片段不是最小 CPG 切片 |
| [BolaRay](https://github.com/BolaRay-d/BolaRay/tree/6b4e7150e1504bd7a28795c577c01997ce53edeb) | SQL 条件、参数和表关系 | SQLGlot 约束解析与 Java 实参绑定 | 未移植 PHP 分析环境或执行其数据集 |
| FixMeUp | 复用已有权限检查进行修复 | guard 复用与局部修复模板 | 方法参考，未复现原工具 |

## 分析方法

跨服务调用需要同时解析接收端和参数对应关系。参考 NEO 和 MScan 的通信分析方式，MicroBind 根据服务名、HTTP 方法、路由和参数位置连接服务，再跟踪同一对象如何传入 SQL 和修复位置。

参考 PCFinder 对权限检查的处理，MicroBind 会继续检查调用之后的控制流。例如，忽略 `owns()` 的返回值不会增加授权条件；只有拒绝分支终止后，后续路径才能使用相应条件。目前主要支持可解析的归属和角色检查，仍需补充更多框架适配。

数据库条件需要与参数来源一起判断。SQL 中存在 `user_id` 条件时，还要确认实参是否来自可信身份。参考 BolaRay 的条件表示，MicroBind 使用 SQLGlot 解析 MyBatis SQL，再绑定 Java 调用实参。litemall 样例中的 Example 和动态 SQL 仍未完整支持。

参考 IRIS 和 LLMxCPG 对路径上下文的组织，MicroBind 为模型提供带源码位置的证据，要求复核意见引用已有证据 ID。图切片和模型规划尚未集成，后续会通过真实样例比较覆盖率、误报和调用成本。

## 代码和样例来源

MicroBind 的分析代码独立实现，仓库分发了 NEO 和 litemall 的部分测试源码，上游文件保持原文，来源及许可见 [第三方材料](../THIRD_PARTY_NOTICES.md)。litemall 来自 PCFinder 的项目列表，源码版本由我们自行固定。

[BACAgent](https://github.com/LFYSec/BACAgent/tree/1e872eb57e9f05422e4b4c096c97f446706de30d) 在所读提交中为待发布说明，未从中集成实现。完整论文基准、真实模型的分析收益及复杂业务规则推断尚未完成评估。

下载固定版本的参考仓库：

```bash
python tools/fetch_upstreams.py --name neo --out out/upstreams
```

下载脚本不执行上游代码。NEO 离线示例的独立环境和运行命令见 [样例说明](PAPER_SAMPLE_TESTS.md)。
