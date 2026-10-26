# MicroBind（持续开发维护中）

Java 微服务授权分析与修复工作台 **v0.3.2**。

MicroBind 从 Spring、Feign 和 MyBatis 源码中追踪用户身份、被检查对象和实际数据操作，找出授权条件缺失或对象不一致的路径，生成修复候选，并在源码副本上复查。React 工作台提供项目导入、任务管理、证据查看和报告下载；FastAPI 与独立 worker 执行分析。

项目面向授权分析研究和内部代码审查。当前支持 Java 8 语法子集、常见 Spring 路由、Feign 调用以及 MyBatis 静态 SQL。动态 SQL、自定义身份注入和复杂调用解析仍有覆盖缺口，报告会单独列出。模型复核默认关闭，基础分析与内置靶场验证不依赖模型。

## 功能与设计

- **按对象判断授权**：检查中的对象、跨服务传递的对象、SQL 使用的对象分别保留，不因参数名称相似就视为相同。
- **保留路径证据**：报告展示调用链、SQL、已成立条件及源码位置，区分 `suspected`、`covered`、`needs_review`。
- **在副本中修复**：支持参数绑定、可信身份、已有检查复用和 SQL 租户约束等小范围修改，应用前校验源文件哈希。
- **验证业务效果**：内置订单靶场检查修复前后的 HTTP 响应和数据库状态。上传的外部项目只做静态分析。
- **分步执行**：分析、模型复核、修复、靶场验证和报告导出注册为独立技能。当前执行固定工作流。

采用显式业务策略，是因为源码通常不能完整表达共享资源、租户例外等权限约定；采用小范围补丁，是为了把修改与已有证据对应起来。具体算法、模块职责和取舍见 [设计说明](docs/ARCHITECTURE.md)。

## Docker 快速启动

需要 Linux、Docker Engine 和 Compose v2。以下命令使用中国大陆常用依赖源，并启用内置 Java 靶场验证：

```bash
cd microbind
bash scripts/init.sh cn verify
# 按下面的表格检查 .env
bash scripts/deploy.sh online
bash scripts/container-smoke.sh
```

只需要静态分析时，初始化使用 `bash scripts/init.sh cn`。初始化脚本生成 `.env` 和随机访问令牌，不覆盖已有文件。默认地址为 `http://127.0.0.1:18080`，登录令牌位于 `secrets/api_token.txt`。

### 需要修改的文件

| 文件 | 配置项 | 修改方法 |
| --- | --- | --- |
| `.env` | `COMPOSE_PROJECT_NAME`、`WEB_PORT` | 多实例部署时改成不同的名称和空闲端口，例如 `microbind_team_a`、`18082` |
| `.env` | `API_IMAGE`、`WEB_IMAGE`、`VERIFY_IMAGE` | 多实例分别使用独有标签；离线部署时与导入镜像的标签一致 |
| `.env` | `BIND_ADDRESS` | 默认保留 `127.0.0.1`，通过 SSH 转发访问；内网直连时填写服务器地址 |
| `.env` | `*_MEMORY`、`*_CPUS` | 按服务器剩余资源调整；详细默认值见部署指南 |
| `.env` | `MICROBIND_VERIFY_ENABLED`、`COMPOSE_PROFILES` | 静态模式为 `0` 和空值；靶场验证为 `1` 和 `verify` |
| `.env` | `PIP_INDEX_URL`、`NPM_REGISTRY`、`MAVEN_REPOSITORY` | `cn` 初始化已设置；源不可达时替换为单位制品库或官方源 |
| `.env` | `PYTHON_IMAGE`、`NODE_IMAGE`、`NGINX_IMAGE`、`MAVEN_IMAGE` | 基础镜像下载失败时，改为可达仓库中的同版本镜像 |
| 待分析源码根目录的 `project.yml` | 服务路径、可信身份、表策略 | 从 `config/project.example.yml` 复制，再按实际代码填写；见 [配置说明](docs/CONFIGURATION.md) |
| `frontend/vite.config.ts` | 开发代理地址 | 仅本地开发 API 不在 `127.0.0.1:8000` 时修改 |

演示项目不需要改 `demo/project.yml`。`.env.example` 是模板，部署读取根目录 `.env`。模型保持 `MICROBIND_LLM_ENABLED=0` 即可。

修改 `.env` 后执行 `docker compose up -d --no-build --pull never` 重新创建受影响容器；修改源码或构建依赖后，重新运行 `scripts/deploy.sh online`。关闭验证服务前执行 `docker compose --profile verify stop verifier`。

远程访问示例：

```bash
ssh -L 18080:127.0.0.1:18080 user@server
```

容器使用独立网络和数据卷，不安装宿主机 Python、Node 或 Java，也不修改 Docker 全局配置。CPU、磁盘和内核仍然共享，构建阶段的开销需另行安排。[部署指南](docs/DEPLOYMENT.md) 包含资源限制、大陆依赖源、离线镜像、升级与备份。源码包不含预构建镜像。

### 从旧版升级

首次使用按上面的快速启动操作即可。

已有部署请先备份，在新解压目录按 `.env.example` 创建 `.env`，逐项迁入原有配置值，更新镜像标签并重新构建。不要直接沿用旧 `.env`。浏览器需重新输入访问令牌；保留 `secrets/api_token.txt` 时令牌不变。需要保留历史项目和任务时，还须处理数据卷和数据库文件名，详见 [升级说明](docs/DEPLOYMENT.md#更名版本升级)。

## 本地开发与测试

需要 Python 3.11+、Node 24；Java 运行验证另需 JDK 17 和 Maven 3.9。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r deploy/requirements.lock
python -m pip install -e '.[server,mcp,test,dev]'
python -m pytest -q
python tools/run_paper_samples.py --out out/paper-samples --export-zips
python -m microbind demo --static-only --out out/demo
npm --prefix frontend ci
npm --prefix frontend run build
```

前后端启动、浏览器交互和 Java 回归命令见 [测试说明](docs/VALIDATION.md)。测试产物统一写入 `out/`，不随源码提交。

自建靶场的基线包含 18 个场景，其中 8 个预设越权场景；修复后验证正常请求和数据访问约束。随包还提供 NEO 通信样例、NEO 跨语言样例及 litemall 源码子集，用于检查框架适配和覆盖缺口。它们不是完整论文基准，不能据此给出真实项目误报率或召回率。具体范围和复现方式见 [样例说明](docs/PAPER_SAMPLE_TESTS.md)。

## 后续方向

近期优先恢复 MyBatis Example 查询条件、自定义身份解析器和接口实现调用，在现有 litemall 子集上补充正反例。随后完善技能的版本、启停和预算管理，再评估可选规划器。IDA 接口保留给 JNI 或本地二进制场景，当前 Java 路线不依赖它。见 [路线图](docs/ROADMAP.md) 和 [技能接口](docs/AGENT_SKILLS_PLAN.md)。

## 参与与许可

问题报告、代码修改和验证要求见 [贡献指南](CONTRIBUTING.md)；漏洞报告见 [安全政策](SECURITY.md)。研究来源及采用范围见 [技术依据](docs/RESEARCH.md)。

MicroBind 代码采用 [MIT License](LICENSE)。`samples/*/upstream/` 保留各自上游许可和版权，详见 [第三方材料](THIRD_PARTY_NOTICES.md)。发布记录见 [CHANGELOG](CHANGELOG.md)。
