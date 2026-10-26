# 上游样例与测试范围

本页记录三组上游样例的分析结果，用于检查框架适配和未支持路径的提示。测试关闭模型复核，仅运行静态分析。

## 样例与结果

| 样例 | 来源与范围 | 已观察到的结果 | 验证目标 |
| --- | --- | --- | --- |
| `neo-http` | NEO 原始 TestHTTPConnector.java，按类分配逻辑服务 | 7 个入口、5 条 Feign 连接、0 条 SQL 操作 | 端点连接及参数绑定；该文件未提供授权问题的预期标注 |
| `neo-role` | NEO 原始 Java Controller、Python handler、服务清单 | 1 个 Java 入口、0 条完整数据操作 | Python/RestTemplate 缺口可见，不将零操作解释为安全 |
| `litemall` | 地址、品牌接口及相关 Service、Mapper、Domain、Example 等源码子集 | 13 个 Java 文件、6 个入口、8 条操作；1 covered、7 needs_review | 静态 include、返回数据依赖及未建模查询条件 |

NEO 提交为 `65ec4e35a1db67159a9d89a59e3e28d30f665690`；litemall 提交为 `a1ef964a718b7277925b19ea26afe78ea3a1d325`。逐文件路径、SHA-256 和来源说明位于 `samples/*/provenance.json`。`upstream/` 中源码保持原文，接入配置位于各样例的 `project.yml`。

litemall 出现在 PCFinder 提交 `41205551a8110935b80e2c0b010ac0c11f41d579` 的 `dataset/dataset.txt` 中，但列表未指定其 commit；对应的权限检查标注 JSON 只列出 PublicCMS、flyCms，未包含 litemall。因此这些结果是 MicroBind 对固定源码子集的观察，无法据此计算 PCFinder 基准上的准确率。

`neo-http` 的一个 Java 文件被三个逻辑服务范围加载，报告中的 `java_files=3` 是加载次数。`litemall` 子集不是可独立部署的完整商城。样例源码的许可见 [第三方材料](../THIRD_PARTY_NOTICES.md)。

## litemall 分析结果

| 入口 | 操作数 | 状态 | 原因 |
| --- | ---: | --- | --- |
| `GET /wx/brand/detail` | 1 | covered | 公开品牌查询；静态 include 与返回 Map 的数据依赖能够恢复 |
| `GET /wx/brand/list` | 1 | needs_review | 分页、Example 和动态列选择未完整建模 |
| `GET /wx/address/detail` | 1 | needs_review | 自定义 `@LoginUser` 与 Example 条件未完整恢复 |
| `GET /wx/address/list` | 1 | needs_review | 尚不能完整连接用户身份与查询条件 |
| `POST /wx/address/delete` | 1 | needs_review | 查询结果到后续删除对象的对应关系不足 |
| `POST /wx/address/save` | 3 | needs_review | 动态 SQL 和实体写入未完整建模，部分表名不能可靠解析 |

地址接口已经包含用户范围查询。7 条待确认记录主要来自尚未解析的参数身份、Example 条件以及查询结果与写入对象的关系，需要人工核对。后续适配会同时增加对象一致和对象不一致的测试，验证分析结论是否正确。

## 复测

```bash
python tools/run_paper_samples.py --out out/paper-samples --export-zips
```

脚本先核对源文件哈希，再执行分析和断言，输出各样例报告及 `summary.json`。`--export-zips` 生成 NEO HTTP 与 litemall 源码 ZIP，可通过工作台导入；NEO role 包含 Python，使用预装样例入口。测试既检查已支持功能的结果，也检查不支持路径是否得到提示；这组测试不统计漏洞检出率。

## NEO 原工具离线示例

NEO 的 `examples/run_demo.py` 使用预置的服务内数据流连接跨服务路径。固定版本的离线示例曾运行得到 8 个节点、7 条边和 1 条 Java → Python 路径，未执行 CodeQL、模型或完整约束验证。这是 NEO 自带示例的结果，MicroBind 的样例结果列在上表中。

可在独立环境重复运行：

```bash
python3 -m venv .venv-neo
.venv-neo/bin/python -m pip install PyYAML==6.0.3 python-dotenv==1.1.1 ijson==3.4.0
mkdir -p out/upstreams
git clone https://github.com/columbia/neo.git out/upstreams/neo
git -C out/upstreams/neo checkout 65ec4e35a1db67159a9d89a59e3e28d30f665690
.venv-neo/bin/python tools/run_neo_offline.py --repo out/upstreams/neo --out out/neo-original
```

脚本核对提交和已跟踪文件的改动。无法访问 GitHub 时，可在可联网机器取得固定版本，再传入 `--repo`。MicroBind 随包样例的静态复测无需下载上游仓库。

MScan、PCFinder、IRIS、LLMxCPG、BolaRay 和 FixMeUp 的完整工具/数据集没有在本项目中复现；采用范围见 [技术依据](RESEARCH.md)。
