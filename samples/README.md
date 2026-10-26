# 原始上游源码样例

三个目录用于静态分析与通信适配测试。所有 `upstream/` 文件来自 `provenance.json` 中的固定提交，未修改；新增的 `project.yml` 负责项目接入。NEO 文件遵守其 Apache-2.0 许可，litemall 文件遵守 MIT 许可，许可证随各自样例保存。

- `neo-http`：原始 HTTP Connector Java 文件；5 条预期 Feign 连接。
- `neo-role`：原始 Java/Python 跨服务角色修改示例；当前 MicroBind 不支持完整路径，专门检验覆盖不足提示。
- `litemall`：PCFinder 项目列表中的项目，选择地址/品牌接口及依赖的原始源码子集；不是论文原始真值集，也不是可单独部署的完整商城。

在仓库根目录运行 `python tools/run_paper_samples.py --out out/paper-samples`。脚本先核对逐文件 SHA256，再用当前分析器重新执行。详细范围、版本和结果见 `docs/PAPER_SAMPLE_TESTS.md`。
