# 测试与验证

v0.3.2，验证日期 2026-10-26。可移植摘要保存在 [validation-v0.3.2.json](validation-v0.3.2.json)，完整测试输出由下列命令写入本机 `out/`，不包含在源码包中。

## 已执行检查

| 检查 | 结果 | 范围 |
| --- | --- | --- |
| Python | 47 项通过 | 分析、修复、配置、API、技能、模型协议及发布包边界 |
| Ruff | 检查与格式检查通过 | `src/`、`tests/`、`tools/` |
| 前端 | 干净安装、TypeScript 检查和 Vite 构建通过 | 保留约 1.09 MB 主包的体积提示，后续可按路由拆分 |
| 浏览器 | 5 项通过，0 跳过 | 真实 API/worker：提交、证据、下载、样例、上传、技能目录及 Java 运行验证 |
| 内置靶场 | 越权效果 8 → 0；正常请求 18/18；边界 4/4 | 页面提交任务，经队列执行 Spring/Feign/MyBatis/H2，检查 HTTP 与数据库效果 |
| 静态修复 | 8 个候选，修改 2 个文件；修复后 18 条 covered | 内置样例的副本复查 |
| 上游样例 | 三组预期断言通过，22 个源文件/许可文件与原包一致 | NEO HTTP、NEO role、litemall 子集；含不支持路径提示 |
| 部署配置 | 三组 Compose 配置解析、6 个 shell 脚本语法检查通过 | 静态、verify、verify + lab；没有启动 Docker 容器 |
| 更名检查 | 发布源码与路径无旧项目名；三个新命令入口可用 | Python 包、前端、报告、MCP、部署配置与文档；前端锁定依赖未变化 |

验证环境为 Linux、Python 3.12.14、Node 24.22.1、JDK 17.0.20、Maven 3.9.9、Playwright 1.64.1，浏览器使用 Chrome for Testing 141.0.7390.37。模型部署开关关闭；协议测试使用测试替身，没有调用真实模型。

Docker 镜像构建/启动、大陆网络连通性、远程 GitHub Actions、真实模型增益、完整论文基准及 IDA 集成均未验证。原始样例的具体结论见 [样例说明](PAPER_SAMPLE_TESTS.md)。

## 本地复现

按 README 创建虚拟环境并安装依赖，然后执行：

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

Maven 依赖首次需要下载。可用 `--maven-settings /path/to/settings.xml` 指定镜像或已准备的离线缓存。发布验证使用已预热的独立 Maven 缓存。

## 浏览器交互

```bash
cd frontend
npx playwright install chromium
cd ..
python tools/run_web_smoke.py
# JDK / Maven 可用时，启用第五项真实服务验证：
MICROBIND_E2E_VERIFY=1 MICROBIND_MAVEN=/path/to/maven/bin/mvn python tools/run_web_smoke.py
```

脚本自动准备原始样例 ZIP，启动实际 API、worker 与 Vite，使用本机 8000 和 4173 端口，结束后关闭所启进程。普通模式执行 4 项并跳过 Java 流程；完整模式执行全部 5 项。结果写入 `out/validation/`，截图写入 `out/ui-inspection/`。可通过 `MICROBIND_CHROMIUM` 指定已有 Chromium，通过 `MICROBIND_MAVEN_SETTINGS` 指定 Maven 配置。

浏览器依赖或下载不可用时应记为未执行，不以单纯前端构建替代交互测试。中文截图需本机具备中文字体。

## 容器与发布

```bash
bash scripts/init.sh cn verify
bash scripts/deploy.sh online
bash scripts/container-smoke.sh
python tools/package_release.py --out out/release
```

容器验收需要可用的 Docker Engine。GitHub 工作流分别覆盖 Python/Java、前端交互和容器部署；远程执行状态以实际仓库 Actions 结果为准。

发布 ZIP 附 `release-manifest.json`，逐文件记录 SHA-256；另有压缩包 SHA-256 文本。解压到空目录后，可运行样例脚本核对上游文件并重复静态演示。发布包不含旧版报告、依赖目录、访问令牌、模型密钥或本机配置。
