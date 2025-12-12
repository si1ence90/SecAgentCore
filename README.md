# SecAgent-Core

<div align="center">

**一个基于 ReAct 框架的网络安全智能体系统**

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

*让 AI 智能体帮你自动化的完成各种繁琐的网络安全任务*

</div>

---

## 📖 项目简介

**SecAgent-Core** 是一个基于 ReAct (Reasoning + Acting) 循环的网络安全智能体系统。它能够理解自然语言描述的安全任务，自动规划执行步骤，调用相应的安全工具，并生成结构化的分析报告，提升安全工作的效率。

### 核心特性

- 🤖 **智能任务规划**: 基于 ReAct 循环，自动分解和执行复杂安全任务
- 🛠️ **丰富工具生态**: 集成数据包分析、威胁情报、端口扫描等多种安全工具
- 📚 **场景化知识库**: 内置场景化知识库，指导 Agent 执行特定任务
- 📊 **自动报告生成**: 自动整理执行结果，生成 Markdown 和 HTML 报告
- 🔄 **智能错误修复**: 自动修复工具参数错误，提高执行成功率
- 📝 **详细日志记录**: 完整的执行日志，便于审计和调试

---

## 🧠 Agent 工作原理

SecAgent-Core 采用 **ReAct (Reasoning + Acting)** 循环架构，通过思考-行动-观察的循环来完成任务。

<img width="1719" height="852" alt="image" src="https://github.com/user-attachments/assets/11b10020-cb22-4058-a247-09eb32301e0c" />
<img width="1722" height="843" alt="image" src="https://github.com/user-attachments/assets/80b43dcb-2368-4256-8dcc-89347c1a02fc" />

### ReAct 循环流程

```
用户任务输入
    ↓
┌─────────────────┐
│  1. Think       │  ← Agent 思考任务，制定执行计划
│  (思考)         │
└─────────────────┘
    ↓
┌─────────────────┐
│  2. Act         │  ← 选择并执行合适的工具
│  (行动)         │
└─────────────────┘
    ↓
┌─────────────────┐
│  3. Observe     │  ← 观察工具执行结果
│  (观察)         │
└─────────────────┘
    ↓
┌─────────────────┐
│  4. Reflect     │  ← 根据结果决定下一步
│  (反思)         │
└─────────────────┘
    ↓
  继续循环或完成任务
```

### 执行步骤

1. **任务理解**: Agent 接收用户任务描述，理解任务目标
2. **知识库匹配**: 自动搜索场景化知识库，获取任务执行指南
3. **计划制定**: 基于知识库和工具能力，制定详细的执行计划
4. **工具选择**: 根据当前步骤，选择最合适的工具
5. **参数提取**: 从任务描述中提取工具所需参数
6. **工具执行**: 调用工具并获取执行结果
7. **结果分析**: 分析工具执行结果，决定下一步行动
8. **报告生成**: 任务完成后，自动生成结构化报告
---

## 🛠️ 安全工具列表

SecAgent-Core 集成了以下安全工具，持续扩展中：

| 工具 | 功能 | 核心能力 |
|------|------|----------|
| **`pcap_analysis`** | PCAP 数据包分析 | 解析流量文件、SQL/Pandas 查询、统计分析、多格式导出 |
| **`threatbook_ip_query`** | 威胁情报查询 | 恶意检测、风险评级、威胁标签识别、地理位置信息 |
| **`port_scan`** | 端口扫描 | 多线程并发、服务识别、可配置端口范围 |
| **`network_ping`** | 连通性检测 | ICMP ping、响应时间统计、自动回退机制 |
| **`file_analyzer`** | 文件分析 | 内容提取、摘要生成、关键信息识别 |
| **`report_generator`** | 报告生成 | LLM 自动整理、Markdown/HTML 双格式 |
| **`notification`** | 消息通知 | 邮箱通知（已实现）、微信/IM/短信（预留） |

> 💡 **提示**: 所有工具均支持参数自动修复和错误自动重试，确保执行成功率。

---

## 🎯 支持场景

### 📦 场景 1: PCAP 数据包分析

**适用**: 网络流量捕获文件分析

**示例**:
```
分析1.cap文件，提取所有TCP数据包的源IP、源端口和协议信息，并生成分析报告
```

**流程**: `pcap_analysis` → 数据提取 → 统计分析 → `report_generator`

**知识库**: `knowledge_base/pcap_analysis.txt`

<img width="1761" height="1014" alt="image" src="https://github.com/user-attachments/assets/4b3a241b-503b-4a04-8ba8-24321a095d47" />


---

### 🛡️ 场景 2: IP 威胁情报查询

**适用**: IP 地址安全风险评估

**示例**:
```
查询 1.2.3.4 和 5.6.7.8 的威胁情报，识别高风险IP并生成报告
```

**流程**: `threatbook_ip_query` → 风险分析 → `report_generator`

**知识库**: 通用知识库

<img width="1755" height="1080" alt="image" src="https://github.com/user-attachments/assets/30bd1fb0-34ba-4e5f-95b0-e14dedd97312" />

---

### 🌐 场景 3: 主机和端口扫描

**适用**: 主机存活检测与端口服务识别

**示例**:
```
扫描 192.168.1.1 这个主机，判断是否存活，开放了哪些端口和服务，并生成扫描报告
```

**流程**: `network_ping` → `port_scan` → 服务识别 → `report_generator`

**知识库**: `knowledge_base/port_scanning.txt`

<img width="2121" height="1059" alt="image" src="https://github.com/user-attachments/assets/00b37eff-a0e5-413f-b903-aa1e09d1f346" />


---

### 🔍 场景 4: 综合安全分析

**适用**: 多维度安全评估

**示例**:
```
扫描 10.48.47.254 主机，查询其威胁情报，分析开放端口的安全风险，并生成综合报告
```

**流程**: `network_ping` → `port_scan` → `threatbook_ip_query` → 综合分析 → `report_generator`

**知识库**: 多知识库组合

---

### 📄 场景 5: 文件安全分析

**适用**: 文件内容安全审查

**示例**:
```
分析 config.txt 文件，提取其中的敏感配置信息
```

**流程**: `file_analyzer` → 信息提取 → 报告生成

**知识库**: `knowledge_base/file_analysis.txt`

---

> 📝 **持续扩展**: 更多场景正在开发中，欢迎贡献新场景和工具！

---

## 🚀 部署方式

### 方式一: 本地部署（推荐）

#### 环境要求

- Python 3.10+ (推荐 64 位)
- 64 位 Python（Web UI 版本需要，命令行版本支持 32 位）

#### 安装步骤

1. **克隆项目**
```bash
git clone https://github.com/yourusername/SecAgent-Core.git
cd SecAgent-Core
```

2. **安装依赖**

**Web UI 版本**（需要 64 位 Python）:
```bash
pip install -r requirements.txt
```

**命令行版本**（支持 32 位 Python）:
```bash
pip install -r requirements_minimal.txt
```

**PCAP 分析功能额外依赖**:
```bash
pip install scapy pandasql openpyxl
```

3. **配置环境变量**

创建 `.env` 文件：
```env
# LLM API Key（至少配置一个）
DEEPSEEK_API_KEY=your_deepseek_api_key
# 或
QWEN_API_KEY=your_qwen_api_key

# 威胁情报查询（可选）
THREATBOOK_API_KEY=your_threatbook_api_key

# 邮箱通知（可选）
EMAIL_SMTP_HOST=smtp.qq.com
EMAIL_SMTP_PORT=587
EMAIL_USERNAME=your_email@qq.com
EMAIL_PASSWORD=your_auth_code
```

4. **配置 LLM 提供商**

编辑 `config.yaml`：
```yaml
llm:
  provider: deepseek  # 或 qwen-max
```

5. **运行应用**

**命令行界面**:
```bash
python app_cli.py
```

**Web 界面**（需要 64 位 Python）:
```bash
streamlit run app.py
```


---

## 📁 项目结构

```
SecAgent-Core/
├── core/                      # 核心模块
│   ├── agent.py              # Agent 引擎（ReAct 循环）
│   ├── llm.py                # LLM 交互封装
│   ├── state.py              # 会话状态管理
│   ├── tools.py              # 工具基类和注册机制
│   ├── realtime_logger.py    # 实时日志记录器
│   ├── execution_logger.py   # 执行日志记录器
│   └── knowledge_base.py     # 知识库管理
├── tools/                     # 工具实现
│   ├── pcap_analysis.py      # PCAP 数据包分析工具
│   ├── threatbook.py         # 威胁情报查询工具
│   ├── network.py            # 网络工具（端口扫描、连通性检测）
│   ├── file.py               # 文件分析工具
│   ├── report.py             # 报告生成工具
│   └── notification.py       # 通知工具
├── knowledge_base/            # 知识库文件
│   ├── pcap_analysis.txt     # PCAP 分析场景指南
│   ├── port_scanning.txt     # 端口扫描场景指南
│   ├── network_analysis.txt  # 网络分析场景指南
│   └── file_analysis.txt     # 文件分析场景指南
├── logs/                      # 日志目录
├── reports/                   # 报告输出目录
├── exports/                   # 导出文件目录
├── app.py                     # Streamlit Web 界面
├── app_cli.py                 # 命令行界面
├── config.yaml                # 配置文件
├── requirements.txt           # 依赖包（Web UI 版本）
└── requirements_minimal.txt  # 依赖包（CLI 版本）
```

---

## 📖 使用示例

### 示例 1: PCAP 流量分析

```bash
# 启动 CLI
python app_cli.py

# 创建任务
任务: 分析1.cap文件，提取所有TCP数据包的源IP、源端口和协议，并生成报告
```

Agent 会自动：
1. 解析 PCAP 文件
2. 使用 SQL 查询提取 TCP 数据包信息
3. 生成统计信息
4. 生成分析报告

### 示例 2: IP 威胁情报批量查询

```bash
任务: 查询以下IP的威胁情报：1.2.3.4, 5.6.7.8, 9.10.11.12，识别高风险IP并生成报告
```

Agent 会自动：
1. 依次查询每个 IP 的威胁情报
2. 汇总分析结果
3. 识别高风险 IP
4. 生成威胁情报分析报告

### 示例 3: 主机扫描

```bash
任务: 扫描 192.168.1.1 这个主机，判断是否存活，开放了哪些端口和服务，并生成扫描报告
```

Agent 会自动：
1. 使用 ping 检查主机存活
2. 扫描开放端口
3. 识别运行的服务
4. 生成扫描报告

---

## ⚙️ 配置说明

### 配置文件 (`config.yaml`)

```yaml
# LLM 提供商配置
llm:
  provider: deepseek  # 或 qwen-max
  
  deepseek:
    api_key: ${DEEPSEEK_API_KEY}
    base_url: https://api.deepseek.com/v1
    model: deepseek-reasoner
    temperature: 0.7
    max_tokens: 4096

# Agent 配置
agent:
  max_iterations: 20  # 最大迭代次数
  enable_human_in_the_loop: false  # 是否启用人机协同

# 工具配置
tools:
  pcap_analysis:
    default_export_dir: exports
    max_packets: 0
    default_limit: 1000
  
  threatbook:
    api_key: ${THREATBOOK_API_KEY}
  
  notification:
    email:
      smtp_host: ${EMAIL_SMTP_HOST}
      smtp_port: ${EMAIL_SMTP_PORT}
      username: ${EMAIL_USERNAME}
      password: ${EMAIL_PASSWORD}
```

---

## 🔧 高级功能


### 工具自动推断

当模型使用了不存在的工具时，系统会：
- 自动推断正确的工具
- 自动提取参数
- 重新执行

### LLM 调用重试

自动处理 LLM API 调用的临时错误（502、超时、限流等），使用指数退避策略重试。

### 详细日志

- **实时日志** (`logs/realtime_*.log`): 执行过程中的实时状态
- **执行日志** (`logs/execution_*.log`): 详细的 JSON 格式日志
- **会话日志** (`logs/session_*.log`): 会话结束时的总结

---


## 🌟 Star History

如果这个项目对你有帮助，请给一个 ⭐ Star！

---

<div align="center">

**Made with ❤️ by si1ence**

</div>
