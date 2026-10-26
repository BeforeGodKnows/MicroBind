# 上游样例与测试范围

这些样例用于确认框架适配器能处理哪些真实输入，并检查未覆盖路径能否被报告。运行时关闭模型，不执行被分析的 Java/Python 服务。

## 输入与预期

| 样例 | 来源与范围 | 已观察到的结果 | 验证目标 |
| --- | --- | --- | --- |
| `neo-http` | NEO 原始 TestHTTPConnector.java，按类分配逻辑服务 | 7 个入口、5 条 Feign 连接、0 条 SQL 操作 | 端点连接及参数绑定；该文件没有授权真值 |
| `neo-role` | NEO 原始 Java Controller、Python handler、服务清单 | 1 个 Java 入口、0 条完整数据操作 | Python/RestTemplate 缺口可见，不将零操作解释为安全 |
| `litemall` | 地址、品牌接口及相关 Service、Mapper、Domain、Example 等源码子集 | 13 个 Java 文件、6 个入口、8 条操作；1 covered、7 needs_review | 静态 include、返回数据依赖及未建模查询条件 |

NEO 提交为 `65ec4e35a1db67159a9d89a59e3e28d30f665690`；litemall 提交为 `a1ef964a718b7277925b19ea26afe78ea3a1d325`。逐文件路径、SHA-256 和来源说明位于 `samples/*/provenance.json`。`upstream/` 中源码保持原文，接入配置位于各样例的 `project.yml`。

litemall 出现在 PCFinder 提交 `41205551a8110935b80e2c0b010ac0c11f41d579` 的 `dataset/dataset.txt` 中，但列表未指定其 commit；所读权限检查真值 JSON 标注 PublicCMS、flyCms，不包含 litemall。因此这些结果是 MicroBind 对固定源码子集的观察，不能用于计算 PCFinder 基准上的精度。

`neo-http` 的一个 Java 文件被三个逻辑服务范围加载，报告中的 `java_files=3` 是加载次数。`litemall` 子集不是可独立部署的完整商城。样例源码的许可见 [第三方材料](../THIRD_PARTY_NOTICES.md)。

## litemall 的具体观察

| 入口 | 操作数 | 状态 | 原因 |
| --- | ---: | --- | --- |
| `GET /wx/brand/detail` | 1 | covered | 公开品牌查询；静态 include 与返回 Map 的数据依赖能够恢复 |
| `GET /wx/brand/list` | 1 | needs_review | 分页、Example 和动态列选择未完整建模 |
| `GET /wx/address/detail` | 1 | needs_review | 自定义 `@LoginUser` 与 Example 条件未完整恢复 |
| `GET /wx/address/list` | 1 | needs_review | 尚不能完整连接用户身份与查询条件 |
| `POST /wx/address/delete` | 1 | needs_review | 查询结果到后续删除对象的对应关系不足 |
| `POST /wx/address/save` | 3 | needs_review | 动态 SQL 和实体写入未完整建模，部分表名不能可靠解析 |

地址代码中已有用户范围查询，7 条待确认记录不能直接计为漏洞。接下来需要恢复参数解析器的身份来源、Example 条件和值，以及查询对象到写入对象的关系。新增适配器应同时覆盖对象一致与不一致的用例，不能只看待确认数量下降。

## 复测

```bash
python tools/run_paper_samples.py --out out/paper-samples --export-zips
```

脚本先核对源文件哈希，再执行分析和断言，输出各样例报告及 `summary.json`。`--export-zips` 生成 NEO HTTP 与 litemall 源码 ZIP，可通过工作台导入；NEO role 包含 Python，使用预装样例入口。兼容性断言通过包括正确报告不支持的范围，不代表漏洞检出成功。

## NEO 原工具离线示例

作者的 `examples/run_demo.py` 使用预置服务内流进行拼接。此前固定版本运行得到 8 个节点、7 条边和 1 条 Java → Python 路径；未执行 CodeQL、模型或完整约束验证。该记录独立于 MicroBind 对上述样例的分析。

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
