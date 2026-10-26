# 配置说明

所有仓库内路径相对于 MicroBind 根目录。部署参数写入 `.env`，被分析项目的业务规则写入该项目根目录的 `project.yml`。

## 部署参数

首次执行 `bash scripts/init.sh cn verify`，然后编辑 `.env`。单实例可保留默认名称；共享服务器上的独立实例可采用：

```dotenv
COMPOSE_PROJECT_NAME=microbind_team_a
BIND_ADDRESS=127.0.0.1
WEB_PORT=18082
API_IMAGE=microbind-team-a-api:0.3.2
WEB_IMAGE=microbind-team-a-web:0.3.2
VERIFY_IMAGE=microbind-team-a-verify:0.3.2
MICROBIND_VERIFY_ENABLED=1
COMPOSE_PROFILES=verify
MICROBIND_LLM_ENABLED=0
```

静态模式将 `MICROBIND_VERIFY_ENABLED` 改为 `0`、`COMPOSE_PROFILES` 留空。初始化只在 `.env` 不存在时执行；已有实例直接编辑此文件。

资源默认值：

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

这些限制作用于运行中的容器，构建镜像时不受它们约束。访问令牌由初始化写入 `secrets/api_token.txt`，无需写入前端代码。修改环境变量后执行：

```bash
docker compose up -d --no-build --pull never
```

`docker compose restart` 不重新读取环境变量。改动依赖源、基础镜像或代码后运行 `bash scripts/deploy.sh online`。详细镜像和网络设置见 [部署指南](DEPLOYMENT.md)。

## 接入源码

将 `config/project.example.yml` 复制到待分析源码根目录，命名为 `project.yml`。下例假设两个服务的源码及资源目录分别在 `order-service/src` 和 `data-service/src`：

```yaml
name: my-order-system
services:
  - name: orders
    path: order-service/src
    exposed: true
  - name: data
    path: data-service/src
    exposed: false
trusted_identity:
  com.example.security.CurrentUser.userId: user
  com.example.security.CurrentUser.tenantId: tenant
  com.example.security.CurrentUser.role: role
policies:
  orders:
    single: {owner: owner_id}
    collection: {tenant: tenant_id}
  users:
    write: {role: ADMIN}
    read: {role: ADMIN}
  products:
    read: {public: true}
repair: {}
analysis:
  max_depth: 30
  max_states: 128
```

| 字段 | 含义及填写要求 |
| --- | --- |
| `services[].path` | 相对于 `project.yml`，包含相关 Controller、Service、Feign、Mapper/XML 的目录 |
| `services[].name` | 与 `@FeignClient(name="...")` 的服务名一致 |
| `services[].exposed` | 该服务是否包含用户可到达的业务入口；经网关可达的服务也属于入口，与 Docker 端口发布无关 |
| `trusted_identity` | 完整类名和方法名，值为 `user`、`tenant` 或 `role`；方法应从认证上下文取身份 |
| `policies` | 键为 SQL 表名；`owner`/`tenant` 指实际列名，`role` 指业务角色；只有公开读接口配置 `public: true` |
| `repair` | 初始保留 `{}`；确定入口已有可调用的授权检查后，再填写 guard 和身份表达式 |
| `analysis` | 调用深度及状态预算；Web 上传的上限为 `30/128`，更小的正整数保留 |

`owner_guard: auth.requireOwner`、`role_guard: auth.requireAdmin` 和 `current_user: CurrentUser.userId()` 是修复配置示例，必须对应入口中实际存在且可调用的方法。请求参数和任意请求头不能仅凭配置成为可信身份。当前自定义 `@LoginUser` 参数解析器不会自动识别。

`trust_boundary` 用于记录网关和身份过滤器的证据位置，配置本身不验证部署边界。`include_classes` 用于一个文件包含多个逻辑服务的样例；普通项目无需填写。非 Java 服务可声明 `language`，分析器会报告不支持的范围。

检查并运行：

```bash
python -m microbind check-config /path/to/source/project.yml
python -m microbind scan /path/to/source/project.yml --out out/my-project
```

配置检查会报告字段错误、缺失路径、找不到的身份方法及入口等问题。通过 Web 接入时，将源码目录压缩为 ZIP，保留一份 `project.yml`：

```bash
zip -r my-project.zip project.yml order-service data-service \
  -x '*/target/*' '*/.git/*' '*/node_modules/*'
```

也可使用桌面归档工具。修改配置后重新上传，旧项目记录不会自动同步。上传源码仅用于分析，不执行其构建或运行脚本。

## 可选模型复核

基础流程不需要模型。启用时在 `.env` 填写实际服务参数：

```dotenv
MICROBIND_LLM_ENABLED=1
MICROBIND_LLM_BASE_URL=https://model.example.com/v1
MICROBIND_LLM_MODEL=model-name
MICROBIND_LLM_API_KEY=replace-with-service-key
MICROBIND_LLM_ALLOW_HTTP=0
MICROBIND_SMART_MAX_FINDINGS=8
```

`model.example.com` 和其余值是占位示例。重新创建容器后，再在任务中开启“智能复核”。服务须支持 Chat Completions 的工具调用协议；只读证据工具包括方法、SQL、路径、策略及方法搜索。无鉴权的本地模型可留空密钥；只有确需明文 HTTP 的可信内网端点才将 `ALLOW_HTTP` 改为 `1`。

模型将收到相关源码证据，返回意见单独展示，不覆盖静态状态。关闭部署开关时，UI 禁用选项，API 拒绝 `smart=true`。模型密钥只在后端配置，不进入前端打包文件。
