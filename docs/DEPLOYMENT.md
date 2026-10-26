# 部署与运行指南

面向一台 Linux 虚拟机或服务器上的小团队演示。默认将前端、API、分析任务、可选 Java 验证任务分别放入容器，源码与结果存在项目专属数据卷中。机器已经安装 Docker 后，部署不再安装宿主机语言环境。

配置文件、修改例子与生效命令见 [配置说明](CONFIGURATION.md)。模型默认关闭，启用时设置 `MICROBIND_LLM_ENABLED=1`。已执行的检查见 [测试说明](VALIDATION.md)。

## 1. 如何避免影响其他部署

隔离的是依赖、进程运行环境、网络名称和应用数据。所有容器都没有 `privileged`、宿主机网络、Docker socket 或宿主机根目录挂载；没有固定 `container_name`；名称由 Compose 项目前缀生成。唯一的文件挂载是本项目的访问令牌。默认仅发布 `127.0.0.1:18080`。

| 进程 | 默认内存上限 | CPU 上限 | 宿主机发布端口 |
| --- | --- | --- | --- |
| frontend | 128 MiB | 0.25 核 | 127.0.0.1:18080 |
| api | 512 MiB | 0.5 核 | 无 |
| worker | 1 GiB | 1 核 | 无 |
| verifier，可选 | 2 GiB | 2 核 | 无 |

默认静态栈内存上限合计约 1.63 GiB；启用验证约 3.63 GiB。起步可给静态演示留出 2 核／4 GiB，完整演示留出 4 核／8 GiB；这些是部署预算建议，尚未经过容器性能测量。上限限制峰值，不代表预留资源或实际恒定占用。Docker、镜像和系统本身仍需要空间。

分析 worker 和 verifier 各处理一项任务；二者可能同时运行。任务默认 1800 秒超时；最多 20 项排队／运行任务。日志轮转；工作进程没有宿主机执行权限。分析进程退出、失败或超时会清理子进程组。

CPU、磁盘 I/O、磁盘容量仍共享。运行时限制不限制镜像构建阶段的开销。多人共用服务器时，建议在另一台机器构建镜像，目标机只做 `docker load` 和启动。如果项目要求更强的硬件资源隔离，给 MicroBind 单独建 VM，再在 VM 内运行此栈。

部署前在 `.env` 改成未被占用的项目名和端口：

```dotenv
COMPOSE_PROJECT_NAME=microbind_team_a
WEB_PORT=18080
BIND_ADDRESS=127.0.0.1
```

不同实例同时运行时，还应使用不同的 `API_IMAGE`、`WEB_IMAGE`、`VERIFY_IMAGE` 标签，防止一个实例重建了另一个实例使用的同名镜像。宿主机 Docker 管理权限由服务器管理员提供；本项目不改变其权限配置。

## 2. 大陆网络在线部署

```bash
cd microbind
bash scripts/init.sh cn verify
# 编辑 .env 的名称、端口、资源预算
bash scripts/deploy.sh online
bash scripts/container-smoke.sh
```

`init.sh` 生成本地配置和随机访问令牌，已有配置不覆盖。`cn` 只设置构建时使用的地址：

| 依赖 | 地址 | 配置项 |
| --- | --- | --- |
| Python | https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple | PIP_INDEX_URL |
| npm | https://registry.npmmirror.com | NPM_REGISTRY |
| Maven | https://maven.aliyun.com/repository/public | MAVEN_REPOSITORY |

不修改用户全局 pip/npm/Maven 配置，不修改 `/etc/docker/daemon.json`，不关闭 TLS 校验。npm 保留锁文件中的版本和 integrity，只在构建层替换 tarball 源域名。Python 运行依赖固定在 `deploy/requirements.lock`。公共镜像站有同步延迟或访问限制时，可换回官方源或单位内部制品库。

**依赖源与容器镜像仓库是两件事。** 上面三个地址不代理 Python、Node、Nginx、Maven 的基础镜像。基础镜像下载失败时，使用组织已验证可访问的镜像仓库，分别配置 `PYTHON_IMAGE`、`NODE_IMAGE`、`NGINX_IMAGE`、`MAVEN_IMAGE`；保持同一版本和兼容目录结构。也可以直接使用下节的离线镜像。

镜像站地址见文末官方说明，具体连通性取决于部署网络。发行验证未覆盖大陆线路；离线导入可减少目标服务器的联网依赖。

## 3. 离线部署

在有网络、与目标机同为 `linux/amd64` 或同为 `linux/arm64` 的构建机上：

```bash
bash scripts/init.sh global verify
bash scripts/deploy.sh online
bash scripts/container-smoke.sh
bash scripts/export-offline.sh out/offline
```

得到 `microbind-images.tar`、`SHA256SUMS` 和含镜像 ID／架构的 `images.txt`。将这三个文件以及源码发布包拷到目标机。不要复制构建机 `.env`、访问令牌或模型密钥。

目标机解压源码，创建自己的配置，然后导入：

```bash
cd microbind
bash scripts/init.sh cn verify
# 修改 .env 的项目名和端口；镜像标签与构建机一致
bash scripts/import-offline.sh /path/to/offline
bash scripts/container-smoke.sh
```

导入先校验 SHA-256，再 `docker load`，最后用 `--no-build --pull never` 启动。verifier 镜像在构建时预热实际 Maven 构建所需依赖；运行时用离线设置，缓存存入自己的 Maven 数据卷。模型调用仍取决于配置的服务；完全离线时关闭智能开关，或接入内网模型。

源码包包含离线打包脚本，不含预构建镜像 tar。需要在构建机执行上述流程。离线导入导出脚本覆盖默认分析栈和 `verify` 配置；若另外启用长期运行的三容器靶场，需要额外保存、加载那三个镜像。

## 4. 打开工作台

同机浏览器访问 `http://127.0.0.1:18080`。远程服务器保持默认绑定，使用 SSH 转发：

```bash
ssh -L 18080:127.0.0.1:18080 用户名@服务器地址
```

登录令牌读取 `secrets/api_token.txt`。令牌目录权限为 0700，文件为 0444，以便只读挂载后非 root 容器能读取；其他宿主机用户不能穿过该目录。令牌仅保存在当前浏览器会话的 sessionStorage 中。

如需多人直接经内网访问，可配置监听地址并在已有 HTTPS 反向代理后转发至本机端口；不需要更改应用代码。当前采用实例共享令牌，适合可信项目组，不具备独立用户、项目级权限和审计身份。正式多人服务再接单位 SSO。

## 5. 智能分析配置

在 `.env` 中配置，默认关闭：

```dotenv
MICROBIND_LLM_ENABLED=1
MICROBIND_LLM_BASE_URL=https://model.example.com/v1
MICROBIND_LLM_MODEL=model-name
MICROBIND_LLM_API_KEY=replace-with-service-key
MICROBIND_SMART_MAX_FINDINGS=8
```

然后更新容器：

```bash
docker compose up -d --no-build --pull never --force-recreate api worker
# 已启用 verifier 时也更新它
docker compose --profile verify up -d --no-build --pull never --force-recreate verifier
```

提供方需支持 OpenAI-compatible `/chat/completions` 及 `tools`／`tool_calls` 格式。这里指协议兼容，不要求使用 OpenAI 服务，也不要求在本机准备 GPU。使用 HTTPS 内网或境内模型服务可以减少外网依赖。只有可信内网模型确实使用明文 HTTP 时，才设置 `MICROBIND_LLM_ALLOW_HTTP=1`；这项选项不会关闭 HTTPS 证书校验。容器中的 `127.0.0.1` 指容器自身，内网模型须填写容器可达的地址。

开启后只复核 `suspected` 与 `needs_review`，默认最多 8 条，每条最多 4 轮工具请求、8 次工具调用和一次最终输出，180 秒总时限；单请求最多 60 秒。任务总时限仍生效。相关源码会发送到配置的模型；密钥不写入前端结果。模型失败时保留静态报告，并单独标记失败。

五个只读工具为 `get_method`、`get_sql`、`get_path`、`get_policy`、`search_methods`。同一工具实现还提供 MCP stdio：

```bash
# 容器内置示例，无需宿主机 Python；stdio 不分配 TTY
docker compose exec -T api microbind-mcp /app/demo/project.yml
# 或在开发虚拟环境中
python -m microbind.mcp_server demo/project.yml
```

MCP 客户端配置示例，`cwd` 填写部署目录：

```json
{"mcpServers":{"microbind":{"command":"docker","args":["compose","exec","-T","api","microbind-mcp","/app/demo/project.yml"],"cwd":"/绝对路径/microbind"}}}
```

内置智能复核直接调用同一只读工具注册表；外部客户端才经 MCP 传输，二者不多绕一次网络。当前没有 IDA 适配器；二进制分析作为后续插件边界。

## 6. 可选的三个靶场服务容器

默认 verifier 在自己的容器内临时启动网关、业务和数据三个 JVM，验证完关闭。需要长期观察三个独立服务容器时：

```bash
docker compose -f compose.yml -f compose.lab.yml --profile lab build lab-data lab-orders lab-gateway
docker compose -f compose.yml -f compose.lab.yml --profile lab up -d --no-build --pull never lab-data lab-orders lab-gateway
curl -H 'Authorization: Bearer alice-demo' http://127.0.0.1:18081/api/safe/101
```

这个可选靶场是修复前版本，独立 lab 网络，只发布本机 18081。三个服务额外合计上限 1.5 GiB／1.5 核；H2 数据随容器重建重置。前端“运行验证”对应 verifier 生成的前后版本，不会修改这些长期服务。停止可选靶场：

```bash
docker compose -f compose.yml -f compose.lab.yml --profile lab stop lab-gateway lab-orders lab-data
```

## 7. 运维与清理

```bash
docker compose ps
docker compose logs --tail=100 api worker verifier
docker compose stop
# 删除本项目容器／网络，保留数据卷
docker compose down
```

不要使用全局 `docker system prune`。页面可删除已经结束的任务及其报告包。源码上传限制为压缩包 50 MiB、解压源码合计 100 MiB、5000 个文件；不等于数据卷总配额。应按项目保留周期清理旧任务、监控 Docker 数据目录容量。上传项目源文件目前保留在卷内，彻底清理一个演示实例可在备份后执行 **本目录的** `docker compose down -v`；这会删除本实例所有项目与结果，不在默认脚本中自动执行。

备份时先停止 api／worker／verifier，再由管理员对 `<项目名>_data` 卷做一致性备份；SQLite WAL 与源码、结果一并保留。升级前也先备份。当前没有跨版本数据库迁移系统。

### 更名版本升级

v0.3.2 的分析规则和数据库表结构没有变化；部署标识、环境变量前缀和数据库文件名已调整。新部署使用 `microbind` 项目名，会创建自己的网络与数据卷。只修改项目名不会自动搬迁历史数据。

已有实例按以下顺序处理：

1. 等待队列任务结束，在旧部署目录停止 api、worker、verifier，备份数据卷、`.env` 和 `secrets/api_token.txt`，保留旧版本目录用于回退。
2. 在新解压目录执行 `bash scripts/init.sh cn verify`（只做静态分析则省略 `verify`）。按新版 `.env.example` 逐项迁入配置值，应用专属变量统一改为 `MICROBIND_` 前缀。保留原有资源限制、端口、模型设置和 `LAB_INTERNAL_KEY`；镜像标签使用新版。需要沿用访问令牌时，将原 `secrets/api_token.txt` 复制到新目录并保持原权限。
3. 需要历史数据时，将旧数据卷的完整备份恢复到新实例的数据卷，保留 `projects/`、`jobs/` 及目录所有权。在所有数据库使用进程停止后，将恢复副本中的主数据库文件改名为 `microbind.db`；若仍有对应 WAL、SHM 文件，一并改为 `microbind.db-wal`、`microbind.db-shm`。只处理备份副本，避免影响回退。
4. 容器内数据挂载点保持 `/data`。本地 Python 部署如移动了数据目录，数据库中已存储的绝对项目路径需要同步调整；更名本身不改写这些记录。历史报告保留生成时内容，需要新名称的报告可重新分析生成。
5. 用新版源码重新构建并启动，重新登录后检查项目列表与已完成任务。确认新实例工作正常，再停用旧前端；同机并行验收时为新实例选不同的 `COMPOSE_PROJECT_NAME` 和 `WEB_PORT`。

不保留历史数据时，可直接按新部署初始化并重新上传项目，无需迁移数据库。更名后也需重新生成离线镜像包；旧镜像不会因为修改标签配置而自动变成新版。

## 8. 不用 Docker 的独立开发环境

按 README 建 `.venv`，不更改系统 Python。先生成本地配置与令牌，再在三个终端中执行以下公共变量和对应命令。开发启动不自动读取 `.env`，模型配置需显式 export。

```bash
source .venv/bin/activate
export MICROBIND_DATA="$PWD/out/dev-server"
export MICROBIND_DEMO="$PWD/demo"
export MICROBIND_TOKEN_FILE="$PWD/secrets/api_token.txt"
# 终端一
uvicorn microbind.server.app:create_app --factory --host 127.0.0.1 --port 8000
# 终端二，同一目录并设置相同变量
python -m microbind.server.worker
# 终端三
cd frontend
npm ci
npm run dev
```

浏览器打开 Vite 输出的本机地址。若启用 Java 验证，API 进程还需 `export MICROBIND_VERIFY_ENABLED=1`，另开终端 `python -m microbind.server.worker --kind verify`，确保 JDK 17／Maven 在该终端可用。`MICROBIND_MAVEN` 和 `MICROBIND_MAVEN_SETTINGS` 可指定 Maven 可执行文件和独立配置文件。

## 官方参考

- [Docker 资源限制](https://docs.docker.com/engine/containers/resource_constraints/)、[Compose 服务配置](https://docs.docker.com/reference/compose-file/services/)、[镜像保存](https://docs.docker.com/reference/cli/docker/image/save/)。
- [TUNA PyPI](https://mirrors.tuna.tsinghua.edu.cn/help/pypi/)、[npmmirror](https://npmmirror.com/)、[阿里云 Maven](https://maven.aliyun.com/mvn/guide)。
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)、[MCP 工具规范](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)。
