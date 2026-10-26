# Third-party materials

MicroBind 的分析器、前后端与任务编排代码由本项目实现。以下目录分发上游测试源码，保留原文和许可。

| 路径 | 来源 | 许可 |
| --- | --- | --- |
| `samples/neo-http/upstream/`、`samples/neo-role/upstream/` | [columbia/neo](https://github.com/columbia/neo)，提交 `65ec4e35a1db67159a9d89a59e3e28d30f665690` | Apache-2.0；各目录附上游 LICENSE |
| `samples/litemall/upstream/` | [linlinjava/litemall](https://github.com/linlinjava/litemall)，提交 `a1ef964a718b7277925b19ea26afe78ea3a1d325` | MIT；保留原版权与 LICENSE |

各样例的 `provenance.json` 列出原始路径和 SHA-256；`project.yml` 是本项目新增接入配置。分析报告中的上游源码片段仍受其原许可约束。根目录 MIT 许可不替代这些目录的许可。

PCFinder 仅作为项目列表来源引用，没有复制其分析实现或标注数据。其他研究来源及采用范围见 [技术依据](docs/RESEARCH.md)。Python/npm 依赖没有包含在源码 ZIP 中，安装后遵守各自许可。
