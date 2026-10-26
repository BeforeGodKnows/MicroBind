# MicroBind

MicroBind 是一个 Java 微服务授权分析与修复工具。它沿 Spring 接口、Feign 调用和 MyBatis SQL 跟踪用户身份与业务对象，检查授权条件是否作用于实际读写的数据，并生成修复补丁。

通过 Web 工作台，可以导入项目源码、查看调用链和 SQL、下载分析报告与补丁。分析、修复和内置靶场验证也支持命令行运行。

当前版本：**v0.3.4** · [MIT License](LICENSE) · [更新日志](CHANGELOG.md)

## 主要功能

- **跨服务分析**：连接 Spring 接口与 Feign 调用，跟踪参数从入口到 SQL 的传递过程。
- **授权检查**：核对对象归属、租户范围和角色要求，区分缺少检查、对象不一致和身份来源不可信等问题。
- **证据查看**：展示调用路径、参数绑定、SQL 条件及源码位置，记录无法解析的语法和调用。
- **补丁生成**：复用已有授权检查，调整对象参数或 SQL 条件。在源码副本上应用补丁并重新分析。
- **运行验证**：在内置订单靶场中比较修复前后的 HTTP 响应和数据库状态，检查正常业务是否受影响。
- **模型复核**：可选接入支持工具调用的模型，通过只读工具查询源码证据。模型复核默认关闭；启用后可切换思考模式，思考默认开启。

目前支持 Java 8 语法子集、常见 Spring 路由、Feign 调用和 MyBatis 静态 SQL。动态 SQL、自定义身份注入和复杂调用仍有未支持的情况，报告会列出相关路径。分析结果需要结合项目的业务授权规则判断，详见 [设计说明](docs/ARCHITECTURE.md)。

## Docker 快速启动

准备一台已安装 Docker Engine 和 Compose v2 的 Linux 服务器，在仓库根目录运行：

```bash
bash scripts/init.sh cn verify
# 检查 .env 中的项目名、监听地址和端口
bash scripts/deploy.sh online
bash scripts/container-smoke.sh
```

`cn` 使用中国大陆常用依赖源，`verify` 启用内置 Java 靶场验证。初始化脚本生成 `.env` 和随机访问令牌，保留已有配置。只需要静态分析时，使用 `bash scripts/init.sh cn`。

部署后访问 `http://127.0.0.1:18080`，登录令牌保存在 `secrets/api_token.txt`。远程服务器可通过 SSH 转发访问：

```bash
ssh -N -L 18080:127.0.0.1:18080 用户名@服务器地址
```

同一服务器运行多个实例时，请分别设置 `.env` 中的 `COMPOSE_PROJECT_NAME`、`WEB_PORT` 和应用镜像标签。逐步配置、内网访问和常见问题见 [服务器部署示例](docs/LOCAL_SERVER.md)；资源限制、离线部署和备份见 [部署指南](docs/DEPLOYMENT.md)。

修改 `.env` 后，运行 `docker compose up -d --no-build --pull never` 更新容器；修改源码或构建依赖后，重新运行 `bash scripts/deploy.sh online`。容器提供所需的 Python、Node 和 Java 环境。

### 内网访问：免令牌

可信内网中可关闭登录，在 `.env` 中设置：

```dotenv
BIND_ADDRESS=192.168.1.10
MICROBIND_AUTH_REQUIRED=0
```

将地址替换为服务器实际内网 IP，重新创建容器后，访问 `http://服务器内网IP:18080` 即可进入工作台。所有可访问实例的人都能上传源码、提交任务、查看和删除结果。源码上传和内置靶场的执行限制仍然生效。

### 外网访问：启用令牌

仓库默认要求令牌。对外提供访问时，保持以下配置，并通过已有的 HTTPS 反向代理转发至本机端口：

```dotenv
BIND_ADDRESS=127.0.0.1
MICROBIND_AUTH_REQUIRED=1
```

初始化脚本生成随机令牌，部署者在服务器上读取：

```bash
cat secrets/api_token.txt
```

将文件中的完整内容输入登录页。业务 API 使用 `Authorization: Bearer <实例令牌>`。如果调整了 secret 的挂载路径，以实际文件为准；令牌不要写入源码或提交到仓库。实例令牌与 DeepSeek 等模型服务的 API Key 是两个独立凭证。

以上配置修改后需重新创建容器，单纯 `restart` 不会重新读取环境变量。外网实例应保留令牌验证；当前共享令牌不区分用户，需要独立账号或项目权限时，应在入口接入相应的认证服务。

### 接入 DeepSeek Flash

模型功能仍默认关闭。需要使用时，在服务端配置：

```dotenv
MICROBIND_LLM_ENABLED=1
MICROBIND_LLM_BASE_URL=https://api.deepseek.com/v1
MICROBIND_LLM_MODEL=deepseek-flash
MICROBIND_LLM_API_KEY=replace-with-your-deepseek-key
```

重新创建 API、worker 和 verifier 容器后，在提交分析时开启“智能复核”。“思考模式”默认开启，可按本次任务关闭；后端会将选择写入模型请求。当前思考开关支持 DeepSeek，其他兼容模型在尚未适配时禁用该开关。模型密钥只配置在服务端，关闭工作台令牌不会免除模型服务的鉴权。更多说明见 [模型配置](docs/CONFIGURATION.md#可选模型复核)。

### 从旧版升级

升级前请备份数据卷和本地配置，再根据新版 `.env.example` 迁入原有设置并重新构建镜像。MicroBind 从 v0.3.2 起使用 `microbind` 命令及 `MICROBIND_` 环境变量前缀。更早版本还需迁移数据卷和数据库文件名，具体步骤见 [升级说明](docs/DEPLOYMENT.md#更名版本升级)。

## 分析自己的项目

1. 将 `config/project.example.yml` 复制到待分析源码根目录，命名为 `project.yml`。
2. 填写服务路径、可信身份方法和业务授权规则。
3. 将配置和源码打成 ZIP，在工作台选择“导入源码 ZIP”，然后提交分析任务。

也可以直接从命令行分析：

```bash
python -m microbind check-config /path/to/source/project.yml
python -m microbind scan /path/to/source/project.yml --out out/my-project
```

字段说明和完整示例见 [配置说明](docs/CONFIGURATION.md)。上传项目仅执行静态分析；运行验证目前限于内置靶场。

## 文档

| 文档 | 内容 |
| --- | --- |
| [服务器部署示例](docs/LOCAL_SERVER.md) | 首次部署、修改配置、访问工作台 |
| [部署指南](docs/DEPLOYMENT.md) | 资源限制、离线镜像、升级与备份 |
| [配置说明](docs/CONFIGURATION.md) | 环境变量、项目规则和模型配置 |
| [设计说明](docs/ARCHITECTURE.md) | 分析方法、修复策略和模块结构 |
| [测试与验证](docs/VALIDATION.md) | 测试记录、复现命令和未验证项目 |
| [样例说明](docs/PAPER_SAMPLE_TESTS.md) | NEO、litemall 样例的来源与分析结果 |
| [技能接口](docs/AGENT_SKILLS_PLAN.md) | 执行步骤、注册方式和扩展计划 |
| [研究参考](docs/RESEARCH.md) | 参考工作及具体采用范围 |
| [开发计划](docs/ROADMAP.md) | 近期工作和验证方式 |

## 本地开发与测试

需要 Python 3.11+、Node 24。Java 运行验证还需要 JDK 17 和 Maven 3.9。

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

前后端启动、浏览器测试和 Java 回归测试见 [测试说明](docs/VALIDATION.md)。测试输出保存在 `out/`，源码包不包含这些运行产物。

内置靶场包含 18 个场景，其中 8 个预设越权场景，用于检查修复结果及正常请求。仓库还提供 NEO 通信样例、跨语言样例和 litemall 源码子集，用于验证框架适配。这些样例尚不足以衡量真实项目上的误报率和召回率。

## 参与贡献

欢迎通过 [Issues](https://github.com/BeforeGodKnows/MicroBind/issues) 报告问题或提出建议，也欢迎提交代码和文档改进。开发与提交要求见 [贡献指南](CONTRIBUTING.md)，安全问题请按 [安全政策](SECURITY.md) 报告。

## 许可证

MicroBind 采用 [MIT License](LICENSE)。`samples/*/upstream/` 中的样例保留各自的上游许可和版权，详见 [第三方材料](THIRD_PARTY_NOTICES.md)。
