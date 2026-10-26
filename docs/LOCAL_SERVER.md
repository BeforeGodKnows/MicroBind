# 本地服务器部署示例

本示例在 Linux 服务器上使用 Docker Compose 部署 MicroBind v0.3.4，启用内置 Java 靶场验证，保持模型复核关闭。部署过程中主要修改仓库根目录的 `.env`。

## 1. 获取源码并初始化

在服务器上确认 Docker Engine 可用，当前账号有使用权限：

```bash
docker version
docker compose version
git clone --branch v0.3.4 https://github.com/BeforeGodKnows/MicroBind.git microbind
cd microbind
bash scripts/init.sh cn verify
```

也可以解压 `MicroBind_v0.3.4.zip` 源码包，然后进入 `microbind/` 目录初始化。`init.sh` 生成 `.env`、随机 `LAB_INTERNAL_KEY` 和 `secrets/api_token.txt`，并设置大陆常用依赖源。已有 `.env` 时直接编辑。Python、Node、Java 和 Maven 由容器提供。

## 2. 编辑根目录的 .env

用编辑器打开 `microbind/.env`，例如 `nano .env`。修改已有的对应行，保留其他配置，尤其保留脚本生成的 `LAB_INTERNAL_KEY`。不要用下方片段覆盖整个文件。

```dotenv
COMPOSE_PROJECT_NAME=microbind_local
BIND_ADDRESS=127.0.0.1
WEB_PORT=18080

API_IMAGE=microbind-local-api:0.3.4
WEB_IMAGE=microbind-local-web:0.3.4
VERIFY_IMAGE=microbind-local-verify:0.3.4

MICROBIND_VERIFY_ENABLED=1
COMPOSE_PROFILES=verify
MICROBIND_LLM_ENABLED=0
```

| 配置项 | 说明 |
| --- | --- |
| `COMPOSE_PROJECT_NAME` | 此服务器上未被其他 Compose 部署使用的名称；上例是 `microbind_local`，生成专属容器、网络和卷 |
| `WEB_PORT` | 未占用的宿主机端口；18080 被占用可改为 18082，访问地址同步改 |
| `BIND_ADDRESS` | 保留 127.0.0.1 时通过 SSH 访问；需要内网直连时填写服务器实际内网 IP，见下文 |
| 三个 `*_IMAGE` | 本实例自己的镜像标签；同机多个 MicroBind 实例分别使用不同标签，离线导入则必须匹配已导入镜像标签 |
| `MICROBIND_VERIFY_ENABLED`、`COMPOSE_PROFILES` | `1` 和 `verify` 启用内置靶场的真实服务验证 |
| `MICROBIND_LLM_ENABLED` | 先保留 0，模型地址、名称和密钥可留空 |

资源先沿用这些默认值，按服务器余量调整：

```dotenv
API_MEMORY=512m
API_CPUS=0.5
WORKER_MEMORY=1g
WORKER_CPUS=1.0
WEB_MEMORY=128m
WEB_CPUS=0.25
VERIFY_MEMORY=2g
VERIFY_CPUS=2.0
MICROBIND_JOB_TIMEOUT=1800
```

启用运行验证后，容器内存上限合计约 3.63 GiB，建议先准备 4 核、8 GiB 的可用资源。该配置尚未做最低资源测试。镜像构建不受容器运行上限约束，磁盘容量和 I/O 仍与同机服务共享。

只需要源码分析和静态修复时，改成：

```dotenv
MICROBIND_VERIFY_ENABLED=0
COMPOSE_PROFILES=
```

若 verifier 已经启动，先运行 `docker compose --profile verify stop verifier`，再改这两个配置并更新容器。

## 3. 检查依赖源

执行过 `cn` 初始化后，`.env` 已包含以下值，一般无需再改：

```dotenv
PIP_INDEX_URL=https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple
NPM_REGISTRY=https://registry.npmmirror.com
MAVEN_REPOSITORY=https://maven.aliyun.com/repository/public
```

这三个地址用于下载编程语言依赖，不负责下载 Docker 基础镜像。若构建在 `FROM` 或拉取基础镜像阶段失败，在同一个 `.env` 中修改 `PYTHON_IMAGE`、`NODE_IMAGE`、`NGINX_IMAGE`、`MAVEN_IMAGE`，使用单位可达镜像仓库中对应版本的镜像；地址由实际镜像仓库决定，请先确认所选镜像仓库和版本可用。原始默认值为：

```dotenv
PYTHON_IMAGE=python:3.12-slim-bookworm
NODE_IMAGE=node:24-bookworm-slim
NGINX_IMAGE=nginxinc/nginx-unprivileged:1.28-alpine
MAVEN_IMAGE=maven:3.9.9-eclipse-temurin-17
```

目标服务器不能联网时，按 [离线部署](DEPLOYMENT.md#3-离线部署) 在可联网、架构相同的机器构建并导出镜像。源码包不包含预构建镜像。上述设置只影响本项目，不修改服务器全局 pip、npm、Maven 或 Docker 配置。

## 4. 构建、启动和检查

仍在 `microbind/` 目录中运行：

```bash
docker compose config --quiet
bash scripts/deploy.sh online
docker compose ps
bash scripts/container-smoke.sh
cat secrets/api_token.txt
```

最后一条显示网页登录令牌。`container-smoke.sh` 会实际提交内置靶场及上游样例任务；启用 `verify` 时会检查真实 Java 服务的修复前后效果。成功结束时输出包含 `"passed": true`。失败时查看：

```bash
docker compose logs --tail=100 api worker verifier frontend
```

发布包会检查 Dockerfile 所需的本地文件是否齐全。各版本实际执行的测试见 [测试记录](VALIDATION.md)；部署完成后，仍请在目标服务器上运行容器检查脚本。

## 5. 从自己的电脑打开页面

默认保留 `BIND_ADDRESS=127.0.0.1`。在自己的电脑上运行下面命令，把 `用户名`、`服务器IP` 换成实际值，保持 SSH 会话打开：

```bash
ssh -N -L 18080:127.0.0.1:18080 用户名@服务器IP
```

浏览器访问 `http://127.0.0.1:18080`，输入刚才读取的令牌。若服务器 `WEB_PORT` 是 18082，则改为 `ssh -N -L 18080:127.0.0.1:18082 用户名@服务器IP`，本机浏览器地址仍使用 18080。

需要项目组直接通过可信内网访问时，把 `.env` 中的 `BIND_ADDRESS` 改为服务器实际内网 IP。例如服务器的地址确实为 `192.168.1.100` 时：

```dotenv
BIND_ADDRESS=192.168.1.100
WEB_PORT=18080
```

更新容器后访问 `http://192.168.1.100:18080`。请将示例 IP 替换为服务器的实际地址，并确认防火墙允许项目组电脑访问该端口。只发布这个前端入口，浏览器的 `/api` 请求由容器内 Nginx 转发到 API，无需在前端代码里填写服务器或后端 IP。跨公网访问使用 SSH 转发或单位现有 HTTPS 入口。

## 6. 应用配置修改

只改端口、监听地址、资源限制或模型参数：

```bash
docker compose up -d --no-build --pull never
```

改源码、构建依赖源、基础镜像或未构建过的应用镜像标签：

```bash
bash scripts/deploy.sh online
```

`docker compose restart` 不会重新读取 `.env`。部署后保持 `COMPOSE_PROJECT_NAME` 稳定，修改它会切换到另一组网络和数据卷。

## 7. 接入自己的项目

先用内置订单项目确认部署正常，不需要修改 `demo/project.yml`。分析自己的源码时，将 `config/project.example.yml` 复制到待分析源码根目录，命名为 `project.yml`，修改以下内容：

- `services`：实际服务名、源码相对路径及是否为用户可达入口。
- `trusted_identity`：从认证上下文读取用户、租户和角色的完整方法名。
- `policies`：实际数据库表、归属列、租户列或角色要求。
- `repair`：初期保留 `{}`，确定可复用的授权检查后再填写。

将源码和这份 `project.yml` 打成 ZIP，在工作台导入。外部项目只执行静态分析。完整字段示例见 [配置说明](CONFIGURATION.md#接入源码)。
