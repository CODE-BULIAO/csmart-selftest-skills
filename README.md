# C-Smart 自测技能仓库

本仓库包含 C-Smart 系统的所有自测技能，用于验证 WhatsApp 机器人的各项功能。

## 技能列表

| 技能名称 | 说明 |
|---------|------|
| csmart-firepatrol-selftest | C-Smart 巡火自测技能，验证巡火消息的点位解析、区间计算、总结生成等功能 |
| csmart-epermit-selftest | C-Smart E-permit 自测技能，验证电子许可和纸本许可的申请、审批、通知流程 |
| csmart-lark-docs | C-Smart 飞书文档读取技能，从飞书多维表格读取项目配置信息 |

## 目录结构

```
csmart-selftest-skills/
├── csmart-firepatrol-selftest/   # 巡火自测技能
│   ├── SKILL.md                  # 技能定义和流程
│   ├── evals/                    # 测试用例
│   ├── scripts/                  # 辅助脚本
│   ├── references/               # 参考文档
│   ├── agents/                   # 代理配置
│   └── tests/                    # 测试代码
├── csmart-epermit-selftest/      # E-permit 自测技能
│   ├── SKILL.md                  # 技能定义和流程
│   ├── evals/                    # 测试用例
│   ├── scripts/                  # 辅助脚本
│   ├── references/               # 参考文档
│   └── agents/                   # 代理配置
└── csmart-lark-docs/             # 飞书文档读取技能
    ├── SKILL.md                  # 技能定义和流程
    ├── references/               # 参考文档
    │   ├── bitable-schema.md     # 多维表格结构文档
    │   └── doc-extraction-guide.md # 需求文档提取指南
    ├── scripts/                  # 辅助脚本
    │   └── build_profile.py      # 构建项目配置脚本
    └── agents/                   # 代理配置
```

## 技能关系

```
用户 → csmart-lark-docs（读取飞书表格）→ project-profile.json → csmart-firepatrol-selftest / csmart-epermit-selftest → 自测报告
```

csmart-lark-docs 是公共技能，为其他自测技能提供项目配置信息。

## 飞书多维表格

所有项目配置存储在飞书多维表格"各地盤群組配置情況"中：

- **Wiki Token**: `KvUmwCEIDin2p8kVhVIc8oyCnZg`
- **Bitable App Token**: `Vt0cbMdcRa6L9ZsJirJcs2tKnLg`
- **数据表**:
  - `tbl77ycCEeb0i1y7` - 数据表（主表，19 字段）
  - `tblM2aRPrkvnjnyr` - bug記錄（17 字段）
  - `tblqzlnEuGDoDf3U` - 自测报告模板（2 字段）

详细字段定义参见 `csmart-lark-docs/references/bitable-schema.md`。

## 使用方式

### 1. 读取项目配置

使用 csmart-lark-docs 技能从飞书表格读取项目配置：

```
用户：读取 BMM柴灣 外牆棚架 的项目配置
Agent：已提取项目配置，生成 project-profile.json
```

### 2. 执行自测

使用具体的自测技能执行测试：

```
用户：测试 BMM柴灣 外牆棚架 的许可申请流程
Agent：已读取项目配置，开始执行 csmart-epermit-selftest 自测流程
```

### 3. 查看报告

自测完成后查看报告：

```
用户：查看自测报告
Agent：报告已生成：outputs/<run-id>/test-report.md
```

## 环境要求

- Python 3.9+
- Node.js 20.11.0+（用于 lark-mcp）
- lark-mcp 工具（飞书 API 访问）

## 安装

### 安装 lark-mcp

```bash
# 安装 Node.js（如未安装）
curl -L -o node-arm64.tar.xz "https://nodejs.org/dist/v20.11.0/node-v20.11.0-darwin-arm64.tar.xz"
mkdir -p ~/.local && cd ~/.local && tar -xf /tmp/node-arm64.tar.xz
ln -sf ~/.local/node-v20.11.0-darwin-arm64 ~/.local/node
echo "export PATH=\$HOME/.local/node/bin:\$PATH" >> ~/.zshrc
export PATH=$HOME/.local/node/bin:$PATH

# 安装 lark-mcp
npm install -g @larksuiteoapi/lark-mcp
```

### 认证 lark-mcp

```bash
lark-mcp login -a <APP_ID> -s <APP_SECRET>
```

### 启动 lark-mcp 服务

```bash
lark-mcp mcp -a <APP_ID> -s <APP_SECRET> --mode streamable --port 3456 -l zh
```

## 版本历史

- **v2.0.0** (2026-07-16): 巡火自测技能通用化改造，支持任意巡火项目
- **v1.1.0** (2026-07-16): 添加飞书文档读取技能
- **v1.0.0** (2026-07-15): 初始版本，包含巡火和 E-permit 自测技能

## 维护者

-  Yiwen

## 许可证

内部使用
