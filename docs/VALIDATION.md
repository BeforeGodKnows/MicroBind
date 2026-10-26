# 测试与验证

当前发布版本为 **v0.3.4**。项目以 Linux 为测试和部署环境；本次完成了文档、界面文案及发布文件检查，完整 Linux 回归将在服务器环境就绪后执行。

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

本地浏览器检查使用真实 API 和分析执行器，通过临时适配脚本运行；尚未重新验证完整 Linux worker、源码上传、Java 运行验证和 Docker 容器部署。真实模型调用及完整论文基准也未纳入本次检查。

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
# JDK / Maven 可用时，启用第五项真实服务验证：
MICROBIND_E2E_VERIFY=1 MICROBIND_MAVEN=/path/to/maven/bin/mvn python tools/run_web_smoke.py
```

脚本自动准备原始样例 ZIP，启动实际 API、worker 与 Vite，使用本机 8000 和 4173 端口，结束后关闭所启进程。普通模式执行 4 项并跳过 Java 流程；完整模式执行全部 5 项。结果写入 `out/validation/`，截图写入 `out/ui-inspection/`。可通过 `MICROBIND_CHROMIUM` 指定已有 Chromium，通过 `MICROBIND_MAVEN_SETTINGS` 指定 Maven 配置。

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
