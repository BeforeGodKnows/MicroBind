import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Alert,
  Button,
  Card,
  ConfigProvider,
  Descriptions,
  Drawer,
  Empty,
  Input,
  Layout,
  Menu,
  Select,
  Space,
  Statistic,
  Switch,
  Table,
  Tabs,
  Tag,
  Typography,
  Upload,
  App as AntApp,
  Spin,
  Popconfirm,
} from "antd";
import zhCN from "antd/locale/zh_CN";
import {
  api,
  download,
  token,
  type Project,
  type Job,
  type Result,
  type Capabilities,
} from "./api";
import "./style.css";
import { SamplesGuide, SkillCatalog } from "./modules/Extensions";

const labels: Record<string, string> = {
  suspected: "疑似缺陷",
  covered: "已满足授权要求",
  needs_review: "待确认",
  queued: "排队中",
  running: "分析中",
  succeeded: "已完成",
  failed: "失败",
  cancelled: "已取消",
};
const colors: Record<string, string> = {
  suspected: "volcano",
  covered: "green",
  needs_review: "gold",
  queued: "default",
  running: "blue",
  succeeded: "green",
  failed: "red",
};
const reasons: Record<string, string> = {
  missing_owner: "缺少对象归属约束",
  object_mismatch: "检查与操作对象不一致",
  untrusted_subject: "授权身份由请求方提供",
  missing_tenant: "缺少租户范围约束",
  missing_role: "缺少角色检查",
  unknown_policy: "策略需要确认",
};
const status = (s: string) => <Tag color={colors[s]}>{labels[s] || s}</Tag>;
const json = (v: unknown) => (
  <pre className="code">{JSON.stringify(v, null, 2)}</pre>
);

function MicroBind() {
  const { message } = AntApp.useApp();
  const [logged, setLogged] = useState(!!token()),
    [credential, setCredential] = useState(""),
    [section, setSection] = useState("workspace");
  const [authRequired, setAuthRequired] = useState(true),
    [checkingAccess, setCheckingAccess] = useState(true);
  const [projects, setProjects] = useState<Project[]>([]),
    [jobs, setJobs] = useState<Job[]>([]),
    [caps, setCaps] = useState<Capabilities | null>(null);
  const [project, setProject] = useState("demo"),
    [smart, setSmart] = useState(false),
    [thinking, setThinking] = useState(true),
    [repair, setRepair] = useState(true),
    [verify, setVerify] = useState(false);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [selected, setSelected] = useState<Job | null>(null),
    [result, setResult] = useState<Result | null>(null),
    [finding, setFinding] = useState<any>(null),
    [filter, setFilter] = useState("all");
  const refresh = async () => {
    const [p, j, c] = await Promise.all([
      api<Project[]>("/projects"),
      api<Job[]>("/jobs"),
      api<Capabilities>("/capabilities"),
    ]);
    setProjects(p);
    setJobs(j);
    setCaps(c);
    setError("");
  };
  useEffect(() => {
    let active = true;
    api<{ auth_required?: boolean }>("/health")
      .then((health) => {
        if (!active) return;
        setAuthRequired(health.auth_required !== false);
        if (health.auth_required === false) {
          sessionStorage.removeItem("microbind-token");
          setLogged(true);
        }
      })
      .catch((e) => active && setError(e.message))
      .finally(() => active && setCheckingAccess(false));
    return () => {
      active = false;
    };
  }, []);
  useEffect(() => {
    if (!logged) return;
    let active = true;
    const run = () => refresh().catch((e) => active && setError(e.message));
    run();
    const t = setInterval(run, 4000);
    return () => {
      active = false;
      clearInterval(t);
    };
  }, [logged]);
  const current = jobs.find((j) => j.id === selected?.id) || selected;
  useEffect(() => {
    if (!current || !["succeeded", "failed"].includes(current.status)) return;
    let active = true;
    api<Result>("/jobs/" + current.id + "/result")
      .then((r) => active && setResult(r))
      .catch((e) => current.status === "succeeded" && setError(e.message));
    return () => {
      active = false;
    };
  }, [current?.id, current?.status]);
  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    try {
      await fn();
    } catch (e) {
      message.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const login = () =>
    act(async () => {
      sessionStorage.setItem("microbind-token", credential.trim());
      try {
        await refresh();
        setLogged(true);
      } catch (e) {
        sessionStorage.removeItem("microbind-token");
        throw e;
      }
    });
  const start = () =>
    act(async () => {
      const j = await api<Job>("/jobs", {
        method: "POST",
        body: JSON.stringify({
          project_id: project,
          kind: verify ? "verify" : "scan",
          smart,
          thinking,
          repair,
        }),
      });
      setSelected(j);
      setResult(null);
      await refresh();
      message.success("任务已提交");
    });
  const view = (j: Job) => {
    setSelected(j);
    setResult(null);
    setFilter("all");
  };
  const context = result?.contexts.find((c) => c.finding_id === finding?.id);
  const model = result?.smart.results.find(
    (c: any) => c.finding_id === finding?.id,
  );
  const patch = result?.repair?.plan.patches.find(
    (p: any) =>
      p.finding_id === finding?.id ||
      p.id === finding?.id ||
      JSON.stringify(p.endpoint) === JSON.stringify(finding?.endpoint),
  );
  if (checkingAccess)
    return (
      <div className="login">
        <Spin size="large" />
      </div>
    );
  if (!logged)
    return (
      <div className="login">
        <Card style={{ width: 420 }}>
          <div className="brand">
            <span>MicroBind</span>
            <Tag>v0.3.4</Tag>
          </div>
          <Typography.Title level={3}>微服务授权分析</Typography.Title>
          <Typography.Paragraph type="secondary">
            输入此 MicroBind 实例的访问令牌，请向部署者获取。
            这是工作台的登录凭证，与模型 API Key 无关。
          </Typography.Paragraph>
          {error && (
            <Alert
              title={error}
              type="error"
              showIcon
              style={{ marginBottom: 16 }}
            />
          )}
          <Input.Password
            aria-label="访问令牌"
            placeholder="输入访问令牌"
            value={credential}
            onChange={(e) => setCredential(e.target.value)}
            onPressEnter={login}
          />
          <Button
            block
            type="primary"
            loading={busy}
            onClick={login}
            style={{ marginTop: 20 }}
          >
            进入工作台
          </Button>
        </Card>
      </div>
    );
  return (
    <Layout className="shell">
      <Layout.Sider width={220} breakpoint="lg" collapsedWidth="64">
        <div className="brand inverse">
          <span>MicroBind</span>
        </div>
        <div className="sidebar-note">微服务授权分析工作台</div>
        <Menu
          theme="dark"
          selectedKeys={[section]}
          onClick={(e) => setSection(e.key)}
          items={[
            { key: "workspace", label: "分析工作台" },
            { key: "samples", label: "示例项目" },
            { key: "skills", label: "技能与执行流程" },
            { key: "method", label: "设计与参考" },
            { key: "settings", label: "模型与部署" },
          ]}
        />
        <div className="sidebar-footer">
          MicroBind · v0.3.4
          <br />
          源码分析 / 补丁生成 / 运行验证
        </div>
      </Layout.Sider>
      <Layout>
        <Layout.Header className="header">
          <Space>
            <b>
              {section === "workspace"
                ? "项目与分析任务"
                : section === "method"
                  ? "设计与参考"
                  : section === "samples"
                    ? "示例项目"
                    : section === "skills"
                      ? "技能与执行流程"
                      : "模型与部署"}
            </b>
            <Tag>Java · Spring · MyBatis</Tag>
          </Space>
          {authRequired ? (
            <Button
              size="small"
              onClick={() => {
                sessionStorage.removeItem("microbind-token");
                setLogged(false);
              }}
            >
              退出
            </Button>
          ) : (
            <Tag>内网免登录</Tag>
          )}
        </Layout.Header>
        <Layout.Content className="content">
          {error && (
            <Alert
              title={error}
              type="error"
              showIcon
              closable
              onClose={() => setError("")}
              style={{ marginBottom: 20 }}
            />
          )}
          {section === "samples" && (
            <SamplesGuide
              onSelect={(id) => {
                setProject(id);
                setVerify(false);
                setRepair(false);
                setSmart(false);
                setSelected(null);
                setResult(null);
                setSection("workspace");
              }}
            />
          )}
          {section === "skills" && <SkillCatalog />}
          {section === "workspace" && (
            <>
              <div className="page-intro">
                <div>
                  <Typography.Title level={2}>
                    分析微服务中的授权检查
                  </Typography.Title>
                  <Typography.Paragraph type="secondary">
                    从服务入口到
                    SQL，核对授权检查与数据操作的对象，并查看修复建议。
                  </Typography.Paragraph>
                </div>
                <Tag color="blue">异步分析</Tag>
              </div>
              <Card
                title="提交分析"
                extra={
                  <Upload
                    accept=".zip"
                    showUploadList={false}
                    beforeUpload={(file) => {
                      act(async () => {
                        const body = new FormData();
                        body.append("file", file);
                        const p = await api<Project>("/projects", {
                          method: "POST",
                          body,
                        });
                        setProject(p.id);
                        setVerify(false);
                        await refresh();
                        message.success("源码导入成功");
                      });
                      return false;
                    }}
                  >
                    <Button loading={busy}>导入源码 ZIP</Button>
                  </Upload>
                }
              >
                <div className="run-form">
                  <div className="project-select">
                    <label>分析项目</label>
                    <Select
                      aria-label="分析项目"
                      value={project}
                      onChange={(v) => {
                        setProject(v);
                        setVerify(false);
                      }}
                      options={projects.map((p) => ({
                        value: p.id,
                        label: p.name,
                      }))}
                      style={{ width: "100%" }}
                    />
                  </div>
                  <div>
                    <label>
                      智能复核{" "}
                      <Switch
                        size="small"
                        checked={smart}
                        onChange={setSmart}
                        aria-label="智能复核"
                        disabled={!caps?.smart_configured}
                      />
                    </label>
                    <small>
                      {caps?.smart_configured
                        ? "通过源码查询工具复核结果"
                        : caps?.smart_enabled
                          ? "配置模型地址与名称"
                          : "服务器已关闭模型功能"}
                    </small>
                  </div>
                  <div>
                    <label>
                      思考模式{" "}
                      <Switch
                        size="small"
                        checked={thinking}
                        onChange={setThinking}
                        aria-label="思考模式"
                        disabled={!smart || !caps?.thinking_supported}
                      />
                    </label>
                    <small>
                      {caps?.thinking_supported
                        ? "默认开启，仅对本次模型复核生效"
                        : "配置支持思考模式的模型后可切换"}
                    </small>
                  </div>
                  <div>
                    <label>
                      生成补丁{" "}
                      <Switch
                        size="small"
                        checked={repair}
                        onChange={setRepair}
                        disabled={verify}
                      />
                    </label>
                    <small>生成源码副本并重新分析</small>
                  </div>
                  <div>
                    <label>
                      运行验证{" "}
                      <Switch
                        size="small"
                        checked={verify}
                        aria-label="运行验证"
                        onChange={(v) => {
                          setVerify(v);
                          if (v) setRepair(true);
                        }}
                        disabled={!caps?.verify_enabled || project !== "demo"}
                      />
                    </label>
                    <small>检查内置靶场的请求和数据</small>
                  </div>
                  <Button
                    type="primary"
                    size="large"
                    loading={busy}
                    onClick={start}
                  >
                    开始分析
                  </Button>
                </div>
                <p className="hint">
                  导入包需包含一份 project.yml
                  和源码；上传项目只做静态分析。开启智能复核后，相关源码片段会发送至服务端配置的模型。
                </p>
              </Card>
              <Card
                title="任务记录"
                className="block"
                extra={
                  <Button size="small" onClick={() => act(refresh)}>
                    刷新
                  </Button>
                }
              >
                <Table<Job>
                  size="small"
                  rowKey="id"
                  dataSource={jobs}
                  pagination={{ pageSize: 5 }}
                  scroll={{ x: 700 }}
                  columns={[
                    {
                      title: "任务",
                      render: (_, j) => (
                        <>
                          <a onClick={() => view(j)}>{j.id.slice(0, 8)}</a>
                          <div className="hint">
                            {projects.find((p) => p.id === j.project_id)?.name}
                          </div>
                        </>
                      ),
                    },
                    {
                      title: "类型",
                      render: (_, j) => (
                        <Space>
                          {j.kind === "verify" ? "分析与运行验证" : "源码分析"}
                          {j.options.smart && <Tag>智能</Tag>}
                        </Space>
                      ),
                    },
                    {
                      title: "状态",
                      render: (_, j) => (
                        <>
                          {status(j.status)}
                          <small>{j.stage}</small>
                        </>
                      ),
                    },
                    {
                      title: "创建时间",
                      render: (_, j) =>
                        new Date(j.created * 1000).toLocaleString("zh-CN", {
                          hour12: false,
                        }),
                    },
                    {
                      title: "操作",
                      render: (_, j) => (
                        <Space>
                          <Button size="small" onClick={() => view(j)}>
                            查看
                          </Button>
                          {j.status === "queued" ? (
                            <Button
                              size="small"
                              onClick={() =>
                                act(async () => {
                                  await api("/jobs/" + j.id + "/cancel", {
                                    method: "POST",
                                  });
                                  await refresh();
                                })
                              }
                            >
                              取消
                            </Button>
                          ) : (
                            j.status !== "running" && (
                              <Popconfirm
                                title="删除这项任务及其结果？"
                                onConfirm={() =>
                                  act(async () => {
                                    await api("/jobs/" + j.id, {
                                      method: "DELETE",
                                    });
                                    if (selected?.id === j.id) {
                                      setSelected(null);
                                      setResult(null);
                                    }
                                    await refresh();
                                  })
                                }
                              >
                                <Button size="small" danger>
                                  删除
                                </Button>
                              </Popconfirm>
                            )
                          )}
                        </Space>
                      ),
                    },
                  ]}
                />
              </Card>
              {!selected ? (
                <Card className="block">
                  <Empty description="选择一个任务，查看分析结果" />
                </Card>
              ) : (
                <Card
                  className="block"
                  title={
                    <Space>
                      结果 · {selected.id.slice(0, 8)}
                      {current && status(current.status)}
                    </Space>
                  }
                  extra={
                    current?.status === "succeeded" && (
                      <Button onClick={() => act(() => download(current.id))}>
                        下载证据与补丁
                      </Button>
                    )
                  }
                >
                  {current?.error && (
                    <Alert title={current.error} type="error" showIcon />
                  )}
                  {!result ? (
                    <div className="pending">
                      {current?.status === "running" ||
                      current?.status === "queued" ? (
                        <Spin description={current.stage} />
                      ) : (
                        <Empty description="尚无分析结果" />
                      )}
                    </div>
                  ) : (
                    <>
                      {result.before.assessment && (
                        <Alert
                          type={
                            result.before.assessment.status === "analyzed"
                              ? "info"
                              : "warning"
                          }
                          showIcon
                          title={result.before.assessment.message}
                          description={`入口 ${result.before.summary.entries}；识别到数据操作的入口 ${result.before.assessment.entries_with_operation_result}；未完整分析的入口 ${result.before.assessment.entries_with_gaps}。`}
                        />
                      )}
                      <div className="metrics">
                        <Statistic
                          title="疑似缺陷"
                          value={result.before.summary.suspected || 0}
                        />
                        <Statistic
                          title="待确认"
                          value={result.before.summary.needs_review || 0}
                        />
                        <Statistic
                          title="已满足授权要求"
                          value={result.before.summary.covered || 0}
                        />
                        <Statistic
                          title="跨服务连接"
                          value={result.before.summary.rpc_edges || 0}
                        />
                        <Statistic
                          title="修复后疑似缺陷"
                          value={
                            result.after
                              ? result.after.summary.suspected || 0
                              : "—"
                          }
                        />
                      </div>
                      <div className="result-note">
                        <Tag>
                          {result.sample_type === "constructed_lab"
                            ? "自建靶场"
                            : result.sample_type === "upstream_sample"
                              ? "上游原始样例"
                              : "导入项目"}
                        </Tag>
                        静态分析和模型意见分别展示。
                        {result.verification
                          ? "运行验证结果包含 HTTP 响应和数据库检查。"
                          : "本任务未运行服务，修复建议仍需结合业务验证。"}
                      </div>
                      <Tabs
                        defaultActiveKey="findings"
                        items={[
                          {
                            key: "skills",
                            label: "执行流程",
                            children: (
                              <Table
                                rowKey="skill_id"
                                pagination={false}
                                dataSource={result.skill_events || []}
                                columns={[
                                  { title: "技能", dataIndex: "title" },
                                  { title: "ID", dataIndex: "skill_id" },
                                  {
                                    title: "状态",
                                    dataIndex: "status",
                                    render: status,
                                  },
                                  {
                                    title: "耗时（秒）",
                                    dataIndex: "elapsed_seconds",
                                  },
                                ]}
                              />
                            ),
                          },
                          {
                            key: "findings",
                            label: "发现与证据",
                            children: (
                              <>
                                <Select
                                  value={filter}
                                  onChange={setFilter}
                                  style={{ width: 160, marginBottom: 16 }}
                                  options={[
                                    { value: "all", label: "全部结果" },
                                    ...[
                                      "suspected",
                                      "covered",
                                      "needs_review",
                                    ].map((value) => ({
                                      value,
                                      label: labels[value],
                                    })),
                                  ]}
                                />
                                <Table
                                  rowKey="id"
                                  dataSource={result.before.results.filter(
                                    (f) =>
                                      filter === "all" || f.status === filter,
                                  )}
                                  pagination={{ pageSize: 8 }}
                                  scroll={{ x: 650 }}
                                  columns={[
                                    {
                                      title: "服务入口",
                                      render: (_, f) => (
                                        <a onClick={() => setFinding(f)}>
                                          {f.endpoint.join(" ")}
                                        </a>
                                      ),
                                    },
                                    {
                                      title: "静态判定",
                                      dataIndex: "status",
                                      render: status,
                                    },
                                    {
                                      title: "数据操作",
                                      render: (_, f) =>
                                        f.operation.kind +
                                        " · " +
                                        (f.operation.table || "表名未解析"),
                                    },
                                    {
                                      title: "说明",
                                      render: (_, f) =>
                                        f.missing
                                          .map(
                                            (x: any) =>
                                              reasons[x.kind] || x.kind,
                                          )
                                          .join("；") ||
                                        (f.status === "needs_review"
                                          ? "分析不完整"
                                          : "已满足授权要求"),
                                    },
                                    {
                                      title: "证据",
                                      render: (_, f) => (
                                        <Button
                                          size="small"
                                          onClick={() => setFinding(f)}
                                        >
                                          展开证据
                                        </Button>
                                      ),
                                    },
                                  ]}
                                />
                              </>
                            ),
                          },
                          {
                            key: "smart",
                            label: "智能复核",
                            children: (
                              <>
                                <Alert
                                  type="info"
                                  showIcon
                                  title={
                                    result.smart.status === "disabled"
                                      ? "本任务未开启智能复核"
                                      : "工具查询记录与模型意见"
                                  }
                                  description="模型通过只读工具查询方法、SQL、跨服务路径和策略，复核意见单独保存，供你与静态结果对照。"
                                />
                                <div className="block">
                                  {result.smart.results.map((m: any) => (
                                    <Card
                                      size="small"
                                      key={m.finding_id}
                                      title={result.before.results
                                        .find((f) => f.id === m.finding_id)
                                        ?.endpoint.join(" ")}
                                      style={{ marginBottom: 12 }}
                                    >
                                      {m.status === "completed" ? (
                                        <>
                                          {status(m.review.verdict)}
                                          {m.disagrees_with_static && (
                                            <Tag color="gold">
                                              与静态判断不同
                                            </Tag>
                                          )}
                                          <p>{m.review.explanation}</p>
                                          <p>
                                            建议验证：{m.review.suggested_test}
                                          </p>
                                          <details>
                                            <summary>
                                              查看工具调用与证据 ID
                                            </summary>
                                            {json(m.tool_calls)}
                                          </details>
                                        </>
                                      ) : (
                                        <Alert type="warning" title={m.error} />
                                      )}
                                    </Card>
                                  ))}
                                  {result.smart.skipped_finding_ids?.length >
                                    0 && (
                                    <p>
                                      已达到本次复核上限，另有{" "}
                                      {result.smart.skipped_finding_ids.length}{" "}
                                      条未复核。
                                    </p>
                                  )}
                                </div>
                              </>
                            ),
                          },
                          {
                            key: "verify",
                            label: "运行验证",
                            children: result.verification ? (
                              <>
                                <Alert
                                  type={
                                    result.verification.passed
                                      ? "success"
                                      : "error"
                                  }
                                  title={
                                    result.verification.passed
                                      ? "靶场回归测试通过"
                                      : "部分回归测试未通过"
                                  }
                                  showIcon
                                />
                                <div className="metrics">
                                  <Statistic
                                    title="修复前越权请求生效数"
                                    value={
                                      result.verification.before.summary
                                        .unauthorized_effects_observed
                                    }
                                  />
                                  <Statistic
                                    title="修复后越权请求生效数"
                                    value={
                                      result.verification.after.summary
                                        .unauthorized_effects_observed
                                    }
                                  />
                                  <Statistic
                                    title="正常请求通过数"
                                    value={
                                      result.verification.after.summary
                                        .legitimate_requests_passed
                                    }
                                    suffix="/ 18"
                                  />
                                  <Statistic
                                    title="边界检查"
                                    value={
                                      result.verification.after.summary
                                        .boundary_checks_passed
                                    }
                                    suffix="/ 4"
                                  />
                                </div>
                                <Table
                                  rowKey={(c: any) => c.endpoint.join(" ")}
                                  dataSource={result.verification.after.cases}
                                  pagination={{ pageSize: 8 }}
                                  columns={[
                                    {
                                      title: "入口",
                                      render: (_, c: any) =>
                                        c.endpoint.join(" "),
                                    },
                                    {
                                      title: "越权请求",
                                      render: (_, c: any) =>
                                        c.attack.effect ? "生效" : "未生效",
                                    },
                                    {
                                      title: "正常请求",
                                      render: (_, c: any) =>
                                        c.legitimate.effect ? "通过" : "失败",
                                    },
                                    {
                                      title: "断言",
                                      render: (_, c: any) => (
                                        <Tag color={c.passed ? "green" : "red"}>
                                          {c.passed ? "通过" : "失败"}
                                        </Tag>
                                      ),
                                    },
                                  ]}
                                />
                              </>
                            ) : (
                              <Empty description="尚未执行运行验证。请先启用验证服务，再为内置靶场开启“运行验证”。" />
                            ),
                          },
                          {
                            key: "gaps",
                            label:
                              "覆盖范围 (" +
                              result.before.coverage_gaps.length +
                              ")",
                            children: (
                              <>
                                <p>
                                  以下列出尚未解析的语法和调用，相关路径需要人工核对。
                                </p>
                                {result.before.coverage_gaps.length ? (
                                  json(result.before.coverage_gaps)
                                ) : (
                                  <Empty description="本次分析未记录不支持的语法或调用" />
                                )}
                              </>
                            ),
                          },
                        ]}
                      />
                    </>
                  )}
                </Card>
              )}
            </>
          )}
          {section === "method" && <MethodGuide />}
          {section === "settings" && (
            <>
              <Typography.Title level={2}>模型与部署</Typography.Title>
              <Card title="当前实例">
                <Descriptions
                  column={1}
                  items={[
                    { key: "version", label: "版本", children: caps?.version },
                    {
                      key: "model",
                      label: "模型",
                      children: caps?.model || "尚未配置",
                    },
                    {
                      key: "tools",
                      label: "只读工具",
                      children: caps?.tools.join(" / "),
                    },
                    {
                      key: "verify",
                      label: "运行验证",
                      children: caps?.verify_enabled ? "已启用" : "未启用",
                    },
                  ]}
                />
              </Card>
              <Card title="配置模型复核" className="block">
                <p>
                  在部署目录 .env 中设置 MICROBIND_LLM_ENABLED=1、MICROBIND_LLM_BASE_URL（包含
                  /v1）、MICROBIND_LLM_MODEL 和 MICROBIND_LLM_API_KEY，然后重新创建
                  API 与 worker 容器。模型需支持 Chat Completions 工具调用。
                </p>
                <p>
                  提交分析时可切换“思考模式”，默认开启。当前支持 DeepSeek 的思考开关；
                  未启用智能复核时，该开关不触发模型调用。
                </p>
                {json({
                  MICROBIND_LLM_ENABLED: 1,
                  MICROBIND_LLM_BASE_URL: "https://model.example.com/v1",
                  MICROBIND_LLM_MODEL: "model-name",
                  MICROBIND_SMART_MAX_FINDINGS: 8,
                })}
                <p>
                  运行命令、离线导入和资源调整见仓库 docs/DEPLOYMENT.md。MCP
                  客户端可使用 microbind-mcp
                  查询项目的方法、SQL、路径和策略证据。
                </p>
              </Card>
            </>
          )}
          <footer>
            MicroBind v0.3.4 · 分析结果依据项目配置，未支持的路径请查看覆盖范围
          </footer>
        </Layout.Content>
      </Layout>
      <Drawer
        title={finding?.endpoint?.join(" ")}
        open={!!finding}
        onClose={() => setFinding(null)}
        size="large"
        styles={{ body: { padding: 20 } }}
      >
        {finding && context && (
          <>
            <Space>
              {status(finding.status)}
              <Tag>{finding.operation.table}</Tag>
            </Space>
            <Tabs
              items={[
                {
                  key: "evidence",
                  label: "源码与 SQL",
                  children: context.snippets.map((s: any) => (
                    <div key={s.evidence_id}>
                      <h4>
                        {s.file}:{s.line}
                      </h4>
                      <pre className="code">{s.code}</pre>
                    </div>
                  )),
                },
                {
                  key: "path",
                  label: "对象与路径",
                  children: (
                    <>
                      <h4>实际对象</h4>
                      {json(context.object)}
                      <h4>授权要求与已知条件</h4>
                      {json({
                        required: context.required,
                        facts: context.facts,
                      })}
                      <h4>跨服务实参绑定</h4>
                      {json(context.parameter_mappings)}
                    </>
                  ),
                },
                {
                  key: "patch",
                  label: "修复建议",
                  children: patch ? (
                    <>
                      <p>{patch.reason || "根据源码分析生成的修复补丁"}</p>
                      <p>位置：{patch.file}</p>
                      <Tag
                        color={
                          patch.verification === "passed_in_lab"
                            ? "green"
                            : "default"
                        }
                      >
                        {patch.verification === "passed_in_lab"
                          ? "靶场运行验证通过"
                          : "尚未进行运行验证"}
                      </Tag>
                      <h4>原代码</h4>
                      <pre className="code">
                        {patch.old || "在指定位置插入检查"}
                      </pre>
                      <h4>修改代码</h4>
                      <pre className="code">{patch.new}</pre>
                      <details>
                        <summary>补丁元数据</summary>
                        {json(patch)}
                      </details>
                      <p>下载包包含修改后的源码副本和 diff，原始项目保持原样。</p>
                    </>
                  ) : (
                    <Empty description="当前发现没有可自动生成的补丁" />
                  ),
                },
                {
                  key: "model",
                  label: "模型意见",
                  children: model ? (
                    json(model)
                  ) : (
                    <Empty description="此发现没有模型复核结果" />
                  ),
                },
              ]}
            />
          </>
        )}
      </Drawer>
    </Layout>
  );
}

function MethodGuide() {
  return (
    <>
      <Typography.Title level={2}>分析方法与参考工作</Typography.Title>
      <Typography.Paragraph>
        我们参考以下工作实现了跨服务连接、授权检查和修复。仓库
        docs/RESEARCH.md 列出了具体采用范围和参考版本。
      </Typography.Paragraph>
      <Table
        pagination={false}
        rowKey="name"
        dataSource={[
          {
            name: "NEO / MScan",
            idea: "跨服务路径与通信适配",
            here: "以 Feign 服务名、路由和参数位置连接服务，保留对象绑定。",
          },
          {
            name: "PCFinder",
            idea: "权限检查的控制语义",
            here: "分析检查失败是否真正中断；忽略返回值的检查不算覆盖。",
          },
          {
            name: "BolaRay",
            idea: "数据库对象与查询约束",
            here: "把 SQL 的 owner / tenant 条件绑定回调用实参。",
          },
          {
            name: "IRIS / LLMxCPG",
            idea: "路径上下文与模型辅助",
            here: "提供源码片段，并允许模型按需查询相关方法和 SQL。",
          },
          {
            name: "FixMeUp",
            idea: "复用已有检查进行修复",
            here: "复用已有授权检查，调整对象参数和 SQL 条件。",
          },
        ]}
        columns={[
          { title: "文献 / 工具", dataIndex: "name" },
          { title: "参考技术", dataIndex: "idea" },
          { title: "本项目实现", dataIndex: "here" },
        ]}
      />
      <Card title="后续计划" className="block">
        <ol>
          <li>
            优先补充接口实现、复杂 Feign 参数和动态
            SQL 的解析，减少调用路径丢失造成的漏报。
          </li>
          <li>
            完善可信身份和授权检查的解析，核对检查对象、失败分支以及后续数据操作。
          </li>
          <li>支持更多业务规则和间接归属关系，例如通过订单确定订单项的归属用户。</li>
          <li>
            使用同一批已标注项目，比较静态分析与不同模型复核方式的误报、漏报和运行成本。
          </li>
        </ol>
        <p>
          详细任务和验证方式见 docs/ROADMAP.md。
        </p>
      </Card>
    </>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: "#2d668a",
          borderRadius: 6,
          fontFamily: 'Inter, system-ui, -apple-system, "Segoe UI", sans-serif',
        },
        components: {
          Layout: { siderBg: "#18334d", headerBg: "#ffffff" },
          Menu: { darkItemBg: "#18334d", darkItemSelectedBg: "#2d668a" },
        },
      }}
    >
      <AntApp>
        <MicroBind />
      </AntApp>
    </ConfigProvider>
  </React.StrictMode>,
);
