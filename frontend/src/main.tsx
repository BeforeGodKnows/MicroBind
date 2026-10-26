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
  covered: "已有覆盖",
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
  untrusted_subject: "身份来自可控请求",
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
  const [projects, setProjects] = useState<Project[]>([]),
    [jobs, setJobs] = useState<Job[]>([]),
    [caps, setCaps] = useState<Capabilities | null>(null);
  const [project, setProject] = useState("demo"),
    [smart, setSmart] = useState(false),
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
  if (!logged)
    return (
      <div className="login">
        <Card style={{ width: 420 }}>
          <div className="brand">
            M<span>MicroBind</span>
            <Tag>0.3</Tag>
          </div>
          <Typography.Title level={3}>微服务授权分析</Typography.Title>
          <Typography.Paragraph type="secondary">
            输入实例访问令牌。令牌位于部署目录的 secrets/api_token.txt
            中。
          </Typography.Paragraph>
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
          M<span>MicroBind</span>
        </div>
        <div className="sidebar-note">微服务授权分析工作台</div>
        <Menu
          theme="dark"
          selectedKeys={[section]}
          onClick={(e) => setSection(e.key)}
          items={[
            { key: "workspace", label: "分析工作台" },
            { key: "samples", label: "上游样例与实测" },
            { key: "skills", label: "技能与执行流程" },
            { key: "method", label: "技术依据与改进方向" },
            { key: "settings", label: "部署与智能分析" },
          ]}
        />
        <div className="sidebar-footer">
          MicroBind · v0.3.2
          <br />
          源码证据 / 小补丁 / 回归验证
        </div>
      </Layout.Sider>
      <Layout>
        <Layout.Header className="header">
          <Space>
            <b>
              {section === "workspace"
                ? "项目与分析任务"
                : section === "method"
                  ? "技术依据与改进方向"
                  : section === "samples"
                    ? "上游样例与实测"
                    : section === "skills"
                      ? "技能与执行流程"
                      : "部署与智能分析"}
            </b>
            <Tag>Java · Spring · MyBatis</Tag>
          </Space>
          <Button
            size="small"
            onClick={() => {
              sessionStorage.removeItem("microbind-token");
              setLogged(false);
            }}
          >
            退出
          </Button>
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
                    把授权检查追到实际操作的对象
                  </Typography.Title>
                  <Typography.Paragraph type="secondary">
                    从服务入口到
                    SQL，查看检查是否覆盖目标对象，再生成可复核的小补丁。
                  </Typography.Paragraph>
                </div>
                <Tag color="blue">独立任务运行</Tag>
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
                        ? "按需查询方法与 SQL"
                        : caps?.smart_enabled
                          ? "配置模型地址与名称"
                          : "服务器已关闭模型功能"}
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
                    <small>在新副本中修改与复查</small>
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
                    <small>内置靶场 HTTP / 数据库断言</small>
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
                  导入包需包含唯一的 project.yml
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
                          {j.kind === "verify" ? "完整运行验证" : "源码分析"}
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
                          description={`入口 ${result.before.summary.entries}；形成操作记录的入口 ${result.before.assessment.entries_with_operation_result}；存在覆盖缺口的入口 ${result.before.assessment.entries_with_gaps}。`}
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
                          title="已有覆盖"
                          value={result.before.summary.covered || 0}
                        />
                        <Statistic
                          title="跨服务连接"
                          value={result.before.summary.rpc_edges || 0}
                        />
                        <Statistic
                          title="补丁后疑似缺陷"
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
                        静态判定与模型复核分别保留。
                        {result.verification
                          ? "下方含实际 HTTP 与数据库验证。"
                          : "本任务未执行服务，补丁效果以静态复查为依据。"}
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
                                    { value: "all", label: "全部发现" },
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
                                      title: "缺口",
                                      render: (_, f) =>
                                        f.missing
                                          .map(
                                            (x: any) =>
                                              reasons[x.kind] || x.kind,
                                          )
                                          .join("；") ||
                                        (f.status === "needs_review"
                                          ? "分析不完整"
                                          : "条件已覆盖"),
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
                                  description="模型可查询方法、SQL、跨服务路径和策略；意见分歧不会自动抹掉静态发现。"
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
                                      达到本次模型预算，另有{" "}
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
                                      ? "真实服务回归通过"
                                      : "存在未通过的回归项"
                                  }
                                  showIcon
                                />
                                <div className="metrics">
                                  <Statistic
                                    title="修复前越权效果"
                                    value={
                                      result.verification.before.summary
                                        .unauthorized_effects_observed
                                    }
                                  />
                                  <Statistic
                                    title="修复后越权效果"
                                    value={
                                      result.verification.after.summary
                                        .unauthorized_effects_observed
                                    }
                                  />
                                  <Statistic
                                    title="修复后正常请求通过"
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
                                      title: "越权效果",
                                      render: (_, c: any) =>
                                        c.attack.effect ? "发生" : "未发生",
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
                              <Empty description="未运行。启用 verify 容器后，可为内置靶场提交完整验证任务。" />
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
                                  未解析语法和未连接调用单独保留，便于区分‘没有发现’与‘尚未覆盖’。
                                </p>
                                {result.before.coverage_gaps.length ? (
                                  json(result.before.coverage_gaps)
                                ) : (
                                  <Empty description="本次解析未记录覆盖缺口" />
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
              <Typography.Title level={2}>部署与智能分析</Typography.Title>
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
              <Card title="开启方式" className="block">
                <p>
                  在部署目录 .env 中设置 MICROBIND_LLM_ENABLED=1、MICROBIND_LLM_BASE_URL（包含
                  /v1）、MICROBIND_LLM_MODEL 和 MICROBIND_LLM_API_KEY，然后重新创建
                  API 与 worker 容器。模型需支持 Chat Completions 工具调用。
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
                  读取同一套源码证据工具；此版本没有调用 IDA。
                </p>
              </Card>
            </>
          )}
          <footer>
            MicroBind v0.3.2 · 分析结论以配置的授权策略和可解析代码为边界
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
                      <h4>要求与事实</h4>
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
                      <p>{patch.reason || "基于源码证据生成的小补丁"}</p>
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
                      <p>原始项目保留；修改副本和 diff 位于下载包中。</p>
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
      <Typography.Title level={2}>这套分析从哪里来</Typography.Title>
      <Typography.Paragraph>
        以下工作提供方法参考，MicroBind 的分析代码独立实现。仓库
        docs/RESEARCH.md 记录了阅读文件和固定版本。
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
            here: "生成对象参数、已有 guard 和 SQL 条件的小改动。",
          },
        ]}
        columns={[
          { title: "文献 / 工具", dataIndex: "name" },
          { title: "参考技术", dataIndex: "idea" },
          { title: "本项目实现", dataIndex: "here" },
        ]}
      />
      <Card title="下一步优先提高哪里" className="block">
        <ol>
          <li>
            先补调用与数据访问覆盖：接口实现、复杂 Feign 参数、动态
            SQL。路径丢失会直接导致漏报。
          </li>
          <li>
            再提高检查语义：哪些身份可信、检查哪个对象、失败后能否继续、是否覆盖所有分支。
          </li>
          <li>把业务策略与间接归属关系补齐，例如订单项通过订单归属用户。</li>
          <li>
            用同一批真实项目标注，比较纯静态、一次性模型复核与工具辅助复核的误报、漏报和成本。
          </li>
        </ol>
        <p>
          可研究的增量是“检查对象—传递对象—数据库对象”的对应关系及修复位置选择。是否优于已有工作，需要在共同样本上验证。
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
