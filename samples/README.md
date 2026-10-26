# 上游源码样例

本目录提供三组静态分析样例，用于测试接口连接、参数绑定及当前不支持的语法和调用。`upstream/` 中的文件来自 `provenance.json` 记录的固定提交，保留上游原文；`project.yml` 是 MicroBind 的接入配置。

- `neo-http`：NEO 的 HTTP Connector Java 文件，包含 5 条预期 Feign 连接。
- `neo-role`：NEO 的 Java/Python 跨服务角色修改示例，用于检查跨语言分析缺口是否得到报告。
- `litemall`：地址、品牌接口及相关源码子集，用于测试 MyBatis 适配。该项目出现在 PCFinder 的项目列表中；本目录使用自行固定的版本，不包含论文中的预期结果标注，也不是完整商城。

在仓库根目录运行：

```bash
python tools/run_paper_samples.py --out out/paper-samples
```

脚本先核对逐文件 SHA-256，再执行分析。版本、预期结果和复现命令见 [样例说明](../docs/PAPER_SAMPLE_TESTS.md)。

NEO 文件使用 Apache-2.0 许可，litemall 文件使用 MIT 许可，各样例目录均保留许可证。
