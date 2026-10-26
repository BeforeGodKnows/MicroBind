import { useEffect, useState } from "react";
import { Alert, Button, Card, Table, Tag, Typography } from "antd";
import { api } from "../api";

const samples = [
  {
    id: "sample-neo-http",
    name: "NEO · HTTP 通信样例",
    scope: "NEO 上游 Java 文件，按类划分逻辑服务",
    observed: "识别到 5 条 Feign 连接；样例未提供 SQL 授权问题标注。",
  },
  {
    id: "sample-neo-role",
    name: "NEO · 跨语言角色修改",
    scope: "NEO 上游 Java / Python 样例",
    observed: "尚不支持完整的 RestTemplate / Python 调用路径，需人工核对。",
  },
  {
    id: "sample-litemall",
    name: "litemall · 地址与品牌接口",
    scope: "固定版本的地址、品牌接口及相关源码子集",
    observed: "6 个入口、8 条操作；1 条满足授权要求，7 条待确认。",
  },
];

export function SamplesGuide({ onSelect }: { onSelect: (id: string) => void }) {
  return (
    <>
      <Typography.Title level={2}>示例项目</Typography.Title>
      <Alert
        showIcon
        type="info"
        title="选择样例，在工作台点击“开始分析”"
        description="下表列出已知结果。提交后会使用当前分析器创建新任务，完成后可查看和下载报告。样例已包含在仓库中，无需联网或启用模型。"
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
      <Card title="结果说明" style={{ marginTop: 20 }}>
        <p>
          示例项目仅运行静态分析。NEO 跨语言路径及部分 MyBatis
          查询尚未完整支持，报告会列出需要人工核对的代码。
        </p>
        <p>
          litemall 来自 PCFinder
          的项目列表，源码版本由我们自行固定。这组样例用于测试框架适配，尚不足以评估完整项目的漏洞检出率。
        </p>
        <p>
          文件来源和 SHA-256 记录在 samples/*/provenance.json，详细结果与运行命令见
          docs/PAPER_SAMPLE_TESTS.md。
        </p>
      </Card>
    </>
  );
}

const permissions: Record<string, string> = {
  read_source: "读取源码",
  write_report: "生成报告",
  model_network: "调用模型服务",
  write_project_copy: "修改源码副本",
  execute_trusted_lab: "运行内置靶场",
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
        title="任务按配置执行以下步骤"
        description="每个步骤对应一项技能。是否执行模型复核、补丁生成和靶场验证，取决于服务配置与任务选项。任务结果中可以查看各步骤的状态和耗时。"
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
            title: "操作能力",
            render: (_, r) =>
              r.permissions.map((p: string) => (
                <Tag key={p}>{permissions[p] || p}</Tag>
              )),
          },
        ]}
      />
      <Card title="任务如何执行" style={{ marginTop: 20 }}>
        <p>
          任务先分析源码，按需执行模型复核，再生成补丁并复查。内置靶场可继续运行修复前后的服务，最后统一导出报告和证据。
        </p>
        <p>
          当前使用内置技能和固定执行顺序，上传项目不能添加可执行插件。新增步骤的开发方式见
          docs/AGENT_SKILLS_PLAN.md。
        </p>
      </Card>
    </>
  );
}
