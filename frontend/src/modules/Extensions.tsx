import { useEffect, useState } from "react";
import { Alert, Button, Card, Table, Tag, Typography } from "antd";
import { api } from "../api";

const samples = [
  {
    id: "sample-neo-http",
    name: "NEO · HTTP 通信样例",
    scope: "作者原始 Java 文件，按类分配逻辑服务",
    observed: "发布实测：5 条 Feign 连接；没有 SQL 授权真值。",
  },
  {
    id: "sample-neo-role",
    name: "NEO · 跨语言角色修改",
    scope: "作者原始 Java / Python 样例",
    observed: "发布实测：RestTemplate / Python 路径未覆盖，不能认定安全。",
  },
  {
    id: "sample-litemall",
    name: "PCFinder 列表 · litemall",
    scope: "固定提交的地址、品牌接口及相关源码子集",
    observed: "发布实测：6 个入口、8 条操作；1 条已有覆盖、7 条待确认。",
  },
];

export function SamplesGuide({ onSelect }: { onSelect: (id: string) => void }) {
  return (
    <>
      <Typography.Title level={2}>用原始样例检查实际能力</Typography.Title>
      <Alert
        showIcon
        type="info"
        title="选择样例后，点击工作台的“开始分析”重新执行"
        description="下表标明发布时结果；重新提交会运行当前分析器，产生新任务和可下载证据。样例不需要模型或联网，不执行上游 Java/Python 服务。"
      />
      <Table
        style={{ marginTop: 20 }}
        rowKey="id"
        pagination={false}
        dataSource={samples}
        columns={[
          { title: "样例", dataIndex: "name" },
          { title: "范围", dataIndex: "scope" },
          { title: "已知结果", dataIndex: "observed" },
          {
            title: "操作",
            render: (_, r) => (
              <Button onClick={() => onSelect(r.id)}>选择样例</Button>
            ),
          },
        ]}
      />
      <Card title="如何理解这些结果" style={{ marginTop: 20 }}>
        <p>
          NEO 的原工具离线演示另外运行过，能拼出 1 条 Java → Python
          路径；单服务流由作者脚本预置，没有运行 CodeQL 或模型判断。
        </p>
        <p>
          litemall 来自 PCFinder
          的项目列表，但列表没有给出固定提交；本项目自行锁定了源码版本。这些结果不能作为
          PCFinder 论文精度的复现。
        </p>
        <p>
          逐文件来源与 SHA256 在
          samples/*/provenance.json；复测命令和未覆盖项目见
          README.md、docs/PAPER_SAMPLE_TESTS.md。
        </p>
      </Card>
    </>
  );
}

const permissions: Record<string, string> = {
  read_source: "读取源码",
  write_report: "写报告",
  model_network: "访问配置模型",
  write_project_copy: "写项目副本",
  execute_trusted_lab: "运行自建靶场",
};
export function SkillCatalog() {
  const [items, setItems] = useState<any[]>([]),
    [error, setError] = useState("");
  useEffect(() => {
    api<any[]>("/skills")
      .then(setItems)
      .catch((e) => setError(e.message));
  }, []);
  return (
    <>
      <Typography.Title level={2}>技能与执行流程</Typography.Title>
      <Alert
        showIcon
        type="info"
        title="已实现注册式技能与固定工作流"
        description="任务执行器按输入输出依赖调用技能，记录每一步结果。当前不支持自主规划或上传插件代码；后续 agent 可以通过同一接口调用这些能力。"
      />
      {error && <Alert type="error" title={error} />}
      <Table
        style={{ marginTop: 20 }}
        rowKey="id"
        pagination={false}
        dataSource={items}
        columns={[
          { title: "功能", dataIndex: "title" },
          { title: "技能 ID", dataIndex: "id" },
          {
            title: "输入",
            render: (_, r) => r.requires.join(", ") || "项目源码",
          },
          { title: "输出", render: (_, r) => r.produces.join(", ") },
          {
            title: "能力范围",
            render: (_, r) =>
              r.permissions.map((p: string) => (
                <Tag key={p}>{permissions[p] || p}</Tag>
              )),
          },
        ]}
      />
      <Card title="下一步的 agent 设计" style={{ marginTop: 20 }}>
        <p>
          先稳定任务、证据与技能接口，再加入可选规划器。规划器选择技能和参数；执行器检查依赖、预算和允许的操作；每次运行留下源码版本、工具事件与可重放产物。
        </p>
        <p>
          新增执行步骤通过技能注册表接入，分析适配逻辑保留在分析器模块中。界面按服务端目录展示功能。接口与扩展方式见
          docs/AGENT_SKILLS_PLAN.md。
        </p>
      </Card>
    </>
  );
}
