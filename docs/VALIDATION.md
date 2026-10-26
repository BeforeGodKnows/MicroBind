# 测试与验证

当前发布版本为 **v0.3.4**。项目以 Linux 为测试和部署环境，已完成容器部署、Python 回归、浏览器操作和 Java 靶场验证。

## v0.3.4 Linux 部署验证

检查日期：2026-10-26。以下结果包含本次免令牌访问和思考开关更新。测试使用的源码包 SHA-256 为 `cb0fa7ae74781e4ab380aa8c1b3cd41db2d37d6f8e1a187da9519ba2130698f2`，发布前另行补齐更新日志和验证记录，功能代码与该测试快照一致。摘要见 [validation-v0.3.4-linux.json](validation-v0.3.4-linux.json) 中的 `feature_update`；该文件同时保留初次部署的 48 项 Python、5 项浏览器验证结果。

| 检查 | 结果 |
| --- | --- |
| Python | 61 项通过，0 失败、0 跳过；Ruff 检查和格式检查通过 |
| 浏览器 | 7 项全部通过：6 项仓库测试及 1 项实例免登录刷新检查，覆盖上传源码、真实队列、证据查看、下载、思考参数和 Java 运行验证 |
| 上游样例 | NEO HTTP、NEO role、litemall 三组断言通过；22 个上游文件的哈希一致 |
| 静态修复 | 8 个补丁、修改 2 个文件，修复后 18 条操作均为 `covered` |
| Java 靶场 | 越权请求生效数 8 → 0；修复后正常请求 18/18，边界检查 4/4 |
| 容器与资源 | 四个服务正常运行；核对了内存、进程数和实际 CFS CPU 配额，并在配额生效后重新通过容器验收 |
| 模型 | 覆盖思考默认值、开启/关闭、队列参数、工具调用续接和缓存隔离；使用本地模拟接口，未调用真实模型服务 |

应用和测试依赖均在独立容器中准备，宿主机已有 Python、Java、Docker、Compose 和 Conda 环境保持原样。遇到旧版 Compose、镜像下载、文件权限和 Maven 临时目录问题时，使用该实例的配置及脚本解决，未修改全局环境。

## v0.3.4 发布前检查

检查日期：2026-10-26。摘要见 [validation-v0.3.4.json](validation-v0.3.4.json)，本地输出保存在 `out/`。

| 检查 | 结果 |
| --- | --- |
| Python | 44 项通过；4 项受现有 Windows 兼容限制，修改前后结果一致 |
| Ruff | `src/`、`tests/`、`tools/` 的检查和格式检查通过 |
| 前端 | 锁定依赖安装、TypeScript 检查和生产构建通过；主包约 1.09 MB，仍有体积提示 |
| 浏览器 | 登录与任务下载、上游样例、技能目录 3 项通过；另外检查了示例、技能、设计和模型配置 4 个页面 |
| 静态修复 | 内置靶场生成 8 个补丁、修改 2 个文件，副本复查中 18 条操作均为 `covered` |
| 上游样例 | NEO HTTP、NEO role、litemall 三组断言通过；22 个上游文件的哈希一致 |
| 源码与文档 | Python 代码结构、上游源码和前端依赖保持原样，文档本地链接通过检查 |
| 发布文件 | 保留 Nginx 配置和 Docker 构建输入检查，版本标识统一为 0.3.4 |

这些发布前检查早于上述 Linux 部署验证。真实模型调用及完整论文基准尚未纳入验证。

## 历史验证记录

- [v0.3.3](validation-v0.3.3.json)：Linux 环境下的 48 项 Python 测试、5 项浏览器测试及 Java 靶场验证记录，包含 Docker 本地构建输入检查。
- [v0.3.2](validation-v0.3.2.json)：项目更名后的验证记录。

历史结果对应各自记录的源码和环境，新版本的完整回归另行记录。样例范围与结果说明见 [样例说明](PAPER_SAMPLE_TESTS.md)。

## 本地复现

以下命令以 Linux 为例。按 README 创建虚拟环境并安装依赖，然后执行：

```bash
ruff check src tests tools
ruff format --check src tests tools
python -m pytest -q
python tools/run_paper_samples.py --out out/paper-samples --export-zips
python -m microbind demo --static-only --out out/local-demo
npm --prefix frontend ci
npm --prefix frontend run build
```

静态演示不会覆盖已有 `fixed-project`，重跑时选择新的 `--out` 目录。Java 回归可独立经队列执行：

```bash
python tools/run_runtime_smoke.py --out out/runtime-smoke --maven mvn
```

Maven 依赖首次需要下载。可用 `--maven-settings /path/to/settings.xml` 指定镜像或已准备的离线缓存。离线运行前，请先准备独立的 Maven 依赖缓存。

## 浏览器交互

```bash
cd frontend
npx playwright install chromium
cd ..
python tools/run_web_smoke.py
# JDK / Maven 可用时，启用真实服务验证：
MICROBIND_E2E_VERIFY=1 MICROBIND_MAVEN=/path/to/maven/bin/mvn python tools/run_web_smoke.py
```

脚本自动准备原始样例 ZIP，启动实际 API、worker 与 Vite，使用本机 8000 和 4173 端口，结束后关闭所启进程。普通模式执行 5 项并跳过 Java 流程；完整模式执行全部 6 项。思考开关的浏览器检查拦截模型任务请求以核对参数，不调用外部模型；API、队列和模型协议的续接另由 Python 测试覆盖。结果写入 `out/validation/`，截图写入 `out/ui-inspection/`。可通过 `MICROBIND_CHROMIUM` 指定已有 Chromium，通过 `MICROBIND_MAVEN_SETTINGS` 指定 Maven 配置。

浏览器交互测试需要可用的 Chromium，生成中文截图还需安装中文字体。前端构建和浏览器交互分别记录检查结果。

## 容器与发布

```bash
bash scripts/init.sh cn verify
bash scripts/deploy.sh online
bash scripts/container-smoke.sh
python tools/package_release.py --out out/release
```

容器验收需要可用的 Docker Engine。GitHub 工作流分别覆盖 Python/Java、前端交互和容器部署；远程执行状态以实际仓库 Actions 结果为准。

发布 ZIP 附 `release-manifest.json`，逐文件记录 SHA-256；另有压缩包 SHA-256 文本。解压到空目录后，可运行样例脚本核对上游文件并重复静态演示。发布包不含旧版报告、依赖目录、访问令牌、模型密钥或本机配置。
