# 基于 opencode 的软件全生命周期智能管理平台需求规格说明书（V2.0）

**文档版本**：V2.0  
**更新日期**：2026-06-16  
**编制依据**：opencode 现有能力分析 + Hermes Gateway 集成架构思想  

---

## 1. 项目背景与目标

### 1.1 背景
opencode 当前已实现 AI 编程助手核心能力（会话管理、工具调用、代码理解、子代理协同、权限控制、MCP 集成），**AI 引擎层完成度约 95%，平台基础设施完成度约 5%**。其交互方式以 CLI 和简单 Web UI（Bridge 模式）为主，缺乏面向软件工程全生命周期的系统性管理界面、流程编排及外部生态集成能力。

### 1.2 目标
将 opencode 改造为**后端服务平台**，配套开发**前端管理控制台**，并引入**集成网关（Integration Gateway）**，覆盖软件开发的六个核心阶段：

| 序号 | 阶段 | 核心产出 |
|------|------|----------|
| 1 | 需求分析 | 需求文档、用户故事、验收标准 |
| 2 | 详细设计（含数据库设计） | 设计文档、ER图、DDL、接口定义 |
| 3 | 代码开发 | 源代码、代码审查报告、单元测试 |
| 4 | 测试 | 测试用例、测试报告、缺陷清单、覆盖率 |
| 5 | 部署 | 部署流水线、环境配置、发布版本 |
| 6 | 验收 | 验收报告、发布说明、最终审批 |

**平台愿景**：构建一个 **“AI 驱动、数据贯通、生态互联”** 的下一代软件工程工作台。

---

## 2. 范围与用户角色

### 2.1 业务范围
- **核心流程**：覆盖从需求到验收的全生命周期，支持阶段门禁（Stage-Gate）控制。
- **AI 赋能**：每个阶段均嵌入 AI 辅助能力（生成、分析、建议、自动化）。
- **生态集成**：通过网关对接 Jira、飞书、钉钉、企业微信、Jenkins、GitLab 等企业工具。

### 2.2 用户角色与权限矩阵

| 角色 | 需求 | 设计 | 开发 | 测试 | 部署 | 验收 | 配置管理 |
|------|------|------|------|------|------|------|----------|
| 产品经理 (PM) | ✅ 读写 | 👁️ 只读+评论 | 👁️ 只读 | 👁️ 只读 | 👁️ 只读 | ✅ 审批 | ❌ |
| 架构师 | 👁️ 只读 | ✅ 读写 | 👁️ 只读 | 👁️ 只读 | 👁️ 只读 | 👁️ 只读 | ❌ |
| **技术负责人 (TL)** | 👁️ 只读 | ✅ 审批 | ✅ 审批 | 👁️ 只读 | ✅ 审批 | 👁️ 只读 | ❌ |
| 开发工程师 | 👁️ 只读 | 👁️ 只读 | ✅ 读写 | ✅ 读写 | 👁️ 只读 | ❌ | ❌ |
| 测试工程师 | 👁️ 只读 | 👁️ 只读 | 👁️ 只读 | ✅ 读写 | 👁️ 只读 | ✅ 验证 | ❌ |
| 运维/DevOps | ❌ | ❌ | 👁️ 只读 | 👁️ 只读 | ✅ 读写 | ❌ | ❌ |
| 项目经理 | ✅ 读写 | 👁️ 只读 | 👁️ 只读 | 👁️ 只读 | 👁️ 只读 | ✅ 最终审批 | ❌ |
| 系统管理员 | 👁️ 只读 | 👁️ 只读 | 👁️ 只读 | 👁️ 只读 | 👁️ 只读 | ❌ | ✅ 全部 |

---

## 3. 功能需求（按阶段）

### 3.1 需求分析阶段

| ID | 功能点 | 详细描述 | AI 加持 | 外部集成（网关） |
|----|--------|----------|---------|------------------|
| REQ-01 | 需求录入与解析 | 支持 Markdown 编辑、PRD 文档上传（PDF/Word），AI 自动抽取结构化字段（Epic/Feature/User Story），支持批量导入/导出（Excel/JSON/CSV，含模板下载） | ✅ NLP 结构化 | 从 Jira 导入需求 |
| REQ-02 | 智能拆解 | 将大需求递归拆分为可独立交付的子任务，并预估复杂度（T恤尺寸 S/M/L/XL） | ✅ 子代理分解 | - |
| REQ-03 | 验收标准生成 | 基于 User Story 自动生成 Gherkin 格式（Given-When-Then）验收条件 | ✅ LLM 生成 | 同步至 Jira 验收字段 |
| REQ-04 | 需求校验与冲突检测 | 检查需求字段完整性（必填项、优先级一致性），基于 LLM 识别明显的语义矛盾 | ✅ LLM 辅助 | - |
| REQ-05 | 变更影响分析 | 需求变更时，自动评估对设计/DB/代码/测试/部署的影响范围 | ✅ ImpactAnalyzer | 触发 Jenkins 重新评估 |
| REQ-06 | 需求追溯矩阵 | 建立需求→设计→代码→测试→部署的双向链接，支持可视化追溯图 | - | 从 Jira/TAPD 反向同步状态 |

### 3.2 详细设计阶段（含数据库设计）

| ID | 功能点 | 详细描述 | AI 加持 | 外部集成（网关） |
|----|--------|----------|---------|------------------|
| DES-01 | 设计文档生成 | 基于需求+架构模式（分层/微服务/DDD）自动生成设计文档草稿 | ✅ LLM 模板填充 | - |
| DES-02 | ER 图与 DDL 生成 | 根据实体关系描述生成 ER 图（Mermaid/PlantUML）及对应方言 DDL（MySQL/PG/Oracle） | ✅ 数据库建模器 | 导出至 Flyway/Liquibase |
| DES-03 | 索引建议（P2） | 分析已生成的 DDL 查询模式，提供基础索引建议 | ✅ LLM 辅助 | - |
| DES-04 | DDL 变更影响分析 | 解析 ALTER 语句，识别受影响的视图、存储过程及应用程序代码位置 | ✅ SQL 解析+ImpactAnalyzer | - |
| DES-05 | 接口契约生成 | 根据需求生成 OpenAPI 3.0 / GraphQL Schema / gRPC Proto 文件 | ✅ LLM 生成 | 推送至 API 网关（如 Kong） |
| DES-06 | 架构图生成 | 生成 C4 模型、系统上下文图、容器图、组件图 | ✅ Mermaid 渲染 | - |
| DES-07 | 设计评审 | AI 辅助检查设计文档完整性（字段缺失、接口未定义），人工主导评审流程 | ✅ LLM 检查清单 | 发送评审通知至钉钉/飞书 |

### 3.3 代码开发阶段（opencode 原生能力开放）

| ID | 功能点 | 详细描述 | AI 加持 | 外部集成（网关） |
|----|--------|----------|---------|------------------|
| DEV-01 | 会话管理 | 创建/切换/删除/分支/回退会话，支持多任务并行 | ✅ SessionStore | - |
| DEV-02 | 对话式编码 | WebSocket 流式对话，AI 执行 50+ 工具（读/写/搜索/执行/LSP/Web） | ✅ AgentLoop | - |
| DEV-03 | 代码审查 | 对变更集进行安全漏洞（16类）、代码异味、逻辑错误扫描；支持 PR/MR 审查工作流（Approve/Request Changes/Comment，审查状态：待审查/需修改/已通过，支持多审查者并行） | ✅ SecurityScanner+CodeAnalyzer | 关联 GitLab MR/PR 评论 |
| DEV-04 | 依赖分析 | 生成 Python/JS/TS 项目依赖图，检测循环依赖与冗余依赖 | ✅ DependencyGraph | - |
| DEV-05 | 单元测试生成 | 为目标函数生成符合项目框架（pytest/jest/unittest）的单测代码 | ✅ TestGenerator | - |
| DEV-06 | 智能 Commit | 根据变更内容生成规范的 Conventional Commit 信息 | ✅ LLM | 推送至 Git 仓库 |
| DEV-07 | Git Worktree 管理 | 为每个任务隔离工作区，避免分支切换污染 | ✅ worktree_tool | - |
| DEV-08 | 定时任务（Cron） | 设置每日 Lint、静态检查、依赖更新提醒等自动化任务 | ✅ cron_tool | 触发 Jenkins Pipeline |

### 3.4 测试阶段

| ID | 功能点 | 详细描述 | AI 加持 | 外部集成（网关） |
|----|--------|----------|---------|------------------|
| TST-01 | 测试用例生成 | 根据需求/代码分支自动生成测试用例（含边界值、异常、性能场景） | ✅ LLM+TestAnalyst | 同步至 TestLink/Xray |
| TST-02 | 测试执行与监控 | 触发单元/集成测试，实时流式输出执行日志 | ✅ TestRunner | 对接 Jenkins 测试插件 |
| TST-03 | 失败智能分析 | 分析失败堆栈，分类（断言/超时/环境/代码缺陷）并推荐修复方案 | ✅ 日志分析+LLM | 自动创建 Jira 缺陷单 |
| TST-04 | 覆盖率趋势 | 收集行/分支/函数覆盖率，生成版本间趋势图 | ✅ CoverageTracker | - |
| TST-05 | 缺陷管理与追踪 | AI 辅助填写缺陷标题、严重级别、复现步骤，关联需求与代码变更；支持批量导入/导出缺陷（Excel/CSV） | ✅ LLM | 双向同步 Jira/TAPD |
| TST-06 | 测试优先级排序 | 基于代码变更影响范围，推荐优先执行的测试用例 | ✅ 变更影响分析 | - |

### 3.5 部署阶段

| ID | 功能点 | 详细描述 | AI 加持 | 外部集成（网关） |
|----|--------|----------|---------|------------------|
| DEP-01 | 环境配置管理 | 多环境（Dev/Test/Staging/Prod）变量、密钥、配置模板管理（加密存储） | - | 对接 HashiCorp Vault |
| DEP-02 | 部署脚本生成 | 根据项目类型（Node/Python/Java/Go）生成 Dockerfile、K8s YAML、Helm Chart | ✅ LLM 模板 | - |
| DEP-03 | 流水线编排 | 定义线性部署步骤（构建→迁移→发布→探测），支持 YAML 配置 | - | 对接 Jenkins/Tekton |
| DEP-04 | 一键部署与回滚 | 选择环境/版本执行部署，支持应用+数据库双回滚 | - | 调用 K8s API / Ansible |
| DEP-05 | 健康检查 | 部署后自动执行健康探测（HTTP/TCP 探针），失败时自动回滚 | - | 对接 Prometheus/Grafana |
| DEP-06 | 失败根因分析 | 部署失败时，聚合日志、事件、配置差异，给出根因推断 | ✅ 日志分析+LLM | - |
| DEP-07 | 部署审批流 | 生产环境部署需 PM/运维双签，通过 IM 卡片快速审批 | - | ✅ 钉钉/飞书/企微审批回传 |

### 3.6 验收阶段

| ID | 功能点 | 详细描述 | AI 加持 | 外部集成（网关） |
|----|--------|----------|---------|------------------|
| ACC-01 | 验收标准自动检查 | 自动核验每个验收条件对应的测试状态、部署环境版本 | ✅ 状态机+规则引擎 | - |
| ACC-02 | 验收报告生成 | 聚合需求实现清单、测试报告、覆盖率、缺陷趋势、部署记录，生成 PDF/HTML | ✅ LLM 润色 | 邮件自动发送 |
| ACC-03 | 追溯矩阵补全 | 基于 Git 提交消息中的需求 ID，自动关联代码变更与需求 | ✅ 规则匹配 | - |
| ACC-04 | 最终审批与签署 | 客户/PM 在线签署验收意见，锁定版本标签 | - | - |
| ACC-05 | 发布说明起草 | 根据验收通过的功能列表，生成面向客户的 Release Notes（新功能/修复/已知问题） | ✅ LLM | 发布至 Confluence/公众号 |

---

## 4. AI 智能增强总览（横向能力）

| 能力维度 | 具体实现 | 覆盖阶段 |
|----------|----------|----------|
| **自然语言 ↔ 结构化** | 需求→Epic/Story，设计→实体模型，日志→缺陷描述 | 需求、设计、测试 |
| **内容生成** | 文档、代码、脚本、用例、报告 | 全阶段 |
| **影响分析** | 需求变更→代码影响，DDL变更→应用影响，部署失败→根因 | 设计、开发、部署 |
| **质量检测** | 需求校验、设计完整性检查、安全漏洞、代码异味、配置错误 | 需求、设计、开发、部署 |
| **辅助决策** | 测试优先级排序、回滚建议、部署健康检查 | 测试、部署 |

---

## 5. 集成网关（Integration Gateway）架构需求

为实现“生态互联”，平台引入轻量级集成网关，参考 Hermes Gateway 设计模式。**实施策略：后端与网关合并为同一 FastAPI 服务，网关作为 `platform/gateway/` 子模块（详见附录 B）。**

### 5.1 网关核心组件

| 组件 | 职责 | 对应 Hermes 参考 |
|------|------|------------------|
| **适配器工厂** | 管理外部系统适配器（Jira/钉钉/飞书/企微/Jenkins/GitLab）的注册与实例化 | `PlatformRegistry` |
| **统一事件格式** | 将外部系统 Webhook 转换为平台标准事件（Event Schema） | `MessageEvent` |
| **事件路由器** | 根据事件类型（需求更新/构建完成/审批回调）路由至对应 Handler | `DeliveryRouter` |
| **上下文注入** | 在调用 AIAgent 前注入外部来源上下文（如“来自 Jira 问题 ABC-123”） | `SessionSource` |
| **重试与死信** | 外部系统不可达时，事件进入重试队列，最终死信告警 | `delivery.py` 重试机制 |

### 5.2 网关关键流程示例

- **入站流程**（外部 → 平台）：
  `Jira Webhook (问题已关闭)` → `JiraAdapter.parse()` → `统一事件(EventType.REQUIREMENT_UPDATED)` → `事件路由器` → 触发 `需求变更影响分析` → 通知 `PM 会话`
- **出站流程**（平台 → 外部）：
  `部署成功事件` → `事件路由器` → `钉钉Adapter.send_card()` → 运维群收到卡片消息

### 5.3 首批适配器清单（按优先级）

| 适配器 | 方向 | 核心场景 |
|--------|------|----------|
| **钉钉/飞书/企微** | 双向 | 审批交互、通知推送、群机器人命令（如“部署预发布”） |
| **Jira/TAPD** | 双向 | 需求同步、缺陷自动创建、状态回写 |
| **Jenkins/GitLab CI** | 入站 | 构建完成触发测试、部署流水线状态回调 |
| **GitLab/GitHub** | 出站 | 自动创建 MR/PR、评论审查报告、设置 Commit Status |
| **邮件（SMTP/IMAP）** | 双向 | 验收报告发送、邮件命令触发 |

---

## 6. 开放给前端的 API 接口清单

前缀：`/api/v1`，认证：JWT。WebSocket 端点：`/ws/sessions/{sessionId}`。

### 6.1 项目管理（12 个端点）
| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/projects` | 分页获取项目列表 |
| POST | `/projects` | 创建项目 |
| GET | `/projects/{id}` | 获取项目详情 |
| PUT | `/projects/{id}` | 更新项目元信息 |
| DELETE | `/projects/{id}` | 归档/删除项目 |
| GET | `/projects/{id}/stages` | 获取六阶段状态及门禁检查结果 |
| POST | `/projects/{id}/stages/{stage}/transition` | 请求阶段流转（含检查） |
| GET | `/projects/{id}/traceability` | 获取全链路追溯矩阵（支持导出 CSV） |
| GET | `/projects/{id}/stats/dashboard` | 获取项目综合仪表盘数据 |

### 6.2 需求分析（10 个端点）
| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/projects/{id}/requirements` | 获取需求树（Epic/Feature/Story） |
| POST | `/projects/{id}/requirements` | 创建需求（含批量导入） |
| PUT | `/requirements/{reqId}` | 更新需求 |
| POST | `/requirements/{reqId}/breakdown` | AI 拆解子需求 |
| POST | `/requirements/{reqId}/acceptance` | 生成/更新验收标准 |
| POST | `/requirements/conflict-check` | 执行全量需求冲突检测 |
| POST | `/requirements/impact-analysis` | 提交变更影响分析任务（异步） |
| GET | `/requirements/impact-analysis/{taskId}` | 获取影响分析结果 |

### 6.3 详细设计（含数据库）（14 个端点）
| 方法 | 路径 | 功能 |
|------|------|------|
| GET/PUT | `/projects/{id}/design` | 获取/更新设计文档 |
| POST | `/projects/{id}/design/modules` | 新增模块设计 |
| GET | `/design/modules/{id}/diagram` | 获取模块图表（Mermaid/PlantUML） |
| GET/POST | `/design/interfaces` | 接口定义管理 |
| POST | `/design/review` | 发起设计评审 |
| GET | `/design/dependency-graph` | 获取依赖图（节点/边） |
| GET/POST | `/design/database/schema` | 获取/更新数据库模型（JSON Schema） |
| GET | `/design/database/diagram` | 生成 ER 图 |
| GET | `/design/database/ddl` | 生成 DDL 脚本（支持版本选择） |
| POST | `/design/database/ddl/alter` | 生成 ALTER 变更脚本 |
| GET | `/design/database/index-suggestions` | 获取索引建议列表 |
| POST | `/design/database/impact-analysis` | 数据库变更影响分析 |

### 6.4 代码开发（16 个端点，另含 WebSocket）
| 方法 | 路径 | 功能 |
|------|------|------|
| GET/POST | `/projects/{id}/sessions` | 会话列表/创建 |
| GET/DELETE | `/sessions/{id}` | 获取/删除会话 |
| POST | `/sessions/{id}/branch` | 创建分支 |
| POST | `/sessions/{id}/rewind` | 回退快照 |
| POST | `/sessions/{id}/compare` | 分支对比 |
| POST | `/files/read` | 读取文件（行号） |
| POST | `/files/write` | 写入文件（需审批） |
| POST | `/files/search` | Grep/Glob 搜索 |
| POST | `/code/review` | 提交代码审查 |
| POST | `/code/analyze/deps` | 分析依赖 |
| POST | `/code/test/generate` | 生成单测代码 |
| GET/POST/DELETE | `/worktrees` | 工作区管理 |
| GET/POST/PUT/DELETE | `/cron/tasks` | 定时任务管理 |

### 6.5 测试（8 个端点）
| 方法 | 路径 | 功能 |
|------|------|------|
| GET/POST | `/projects/{id}/test/plans` | 测试计划管理 |
| POST | `/test/plans/{id}/execute` | 执行测试（异步） |
| GET | `/test/executions/{execId}` | 获取执行结果（流式） |
| GET | `/projects/{id}/test/coverage` | 获取覆盖率报告 |
| GET/POST/PUT | `/defects` | 缺陷管理 CRUD |
| POST | `/defects/{id}/analyze` | AI 缺陷根因分析 |

### 6.6 部署（11 个端点）
| 方法 | 路径 | 功能 |
|------|------|------|
| GET/POST/DELETE | `/projects/{id}/environments` | 环境配置管理 |
| GET/POST | `/projects/{id}/pipelines` | 流水线定义管理 |
| POST | `/pipelines/{id}/trigger` | 触发部署（含版本选择） |
| GET | `/deployments/{deploymentId}` | 获取部署详情 |
| GET/WS | `/deployments/{id}/logs` | 获取实时日志 |
| POST | `/deployments/{id}/rollback` | 回滚 |
| GET | `/projects/{id}/deployments/history` | 部署历史 |
| GET | `/deployments/{id}/report` | 部署报告 |
| GET/POST | `/environments/{id}/approvals` | 部署审批管理 |

### 6.7 验收（5 个端点）
| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/projects/{id}/acceptance/check` | 触发验收标准检查 |
| GET | `/projects/{id}/acceptance/report` | 生成验收报告（PDF/HTML） |
| POST | `/projects/{id}/acceptance/approve` | 最终审批 |
| POST | `/projects/{id}/release` | 生成发布包/Release Note |

### 6.8 通知中心（新增，6 个端点）
| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/notifications` | 获取用户通知列表（分页，支持已读/未读筛选） |
| PUT | `/notifications/{id}/read` | 标记单条通知为已读 |
| PUT | `/notifications/read-all` | 标记全部为已读 |
| GET/PUT | `/notifications/preferences` | 获取/更新通知偏好（哪些事件触发通知、渠道选择） |
| WS | `/ws/notifications` | WebSocket 实时推送新通知 |

### 6.9 系统配置与网关管理（15 个端点）
| 方法 | 路径 | 功能 |
|------|------|------|
| GET/PUT | `/config/models` | 模型配置 |
| GET/PUT | `/config/permissions` | 权限规则 |
| GET/PUT | `/config/tools` | 工具参数 |
| GET/POST/PUT/DELETE | `/config/skills` | 技能管理 |
| GET/POST/DELETE | `/config/plugins` | 插件管理 |
| GET/POST/PUT/DELETE | `/config/mcp/servers` | MCP 服务器配置 |
| GET/PUT | `/config/hooks` | Hook 配置 |
| GET/PUT | `/config/deployment` | 部署引擎配置 |
| GET/POST/PUT/DELETE | `/config/integrations/adapters` | **网关适配器注册与管理** |
| GET/POST/PUT/DELETE | `/config/integrations/routes` | **事件路由表配置** |
| GET | `/audit/logs` | 审计日志查询 |

---

## 7. 开放给前端的配置项清单（按域划分）

| 域 | 配置项 | 前端控件 | 说明 |
|----|--------|----------|------|
| **模型** | 阶段默认模型、Fallback链、温度/MaxTokens | 下拉+滑块 | 支持按阶段独立配置 |
| **预算** | 项目预算上限(USD)、Token预警阈值(80%/95%) | 数字输入+滑块 | - |
| **权限** | 工具白名单、审批队列规则、四级权限级别 | 树形选择+规则编辑器 | - |
| **工具** | 启用/禁用工具、缓存TTL、重试策略 | 开关+数字输入 | - |
| **技能** | 内置技能开关、自定义技能YAML编辑器、扫描路径 | 开关+代码编辑器+路径列表 | - |
| **插件** | 插件列表、启用/卸载、远程源URL | 列表+URL输入 | - |
| **MCP** | MCP服务器列表（类型/命令/环境变量） | 表单+密码框 | - |
| **部署** | 引擎类型(K8s/SSH/Ansible)、各环境连接配置、保留版本数、超时秒数 | 下拉+文件上传+数字 | 敏感信息加密 |
| **数据库** | 默认方言、命名规范、自动索引建议开关、导出格式 | 下拉+单选+开关+多选 | - |
| **网关** | **适配器启用/禁用、Webhook URL映射、重试次数、死信告警接收人** | 开关+URL输入+数字+人员选择 | **新增核心域** |
| **通知** | 全局Webhook、IM群组绑定、邮件服务器 | URL输入+表单 | - |

---

## 8. 非功能需求（NFR）

### 8.1 性能
| 指标 | 目标值 |
|------|--------|
| API（非LLM）P95 响应时间 | < 200ms |
| WebSocket 并发连接数 | ≥ 1000 |
| 代码搜索（100k文件） | < 5s |
| 部署日志流延迟 | < 500ms |
| 依赖图生成（含缓存） | < 3s |

### 8.2 安全
- **认证**：JWT（Access+Refresh），支持 OAuth2/SAML（企业 SSO）。
- **RBAC**：至少 8 个角色（PM/Arch/TL/Dev/Tester/Ops/PMgr/Admin）。
- **数据隔离**：项目级租户隔离，禁止跨项目数据访问。
- **密钥管理**：配置文件密钥使用 AES-256 加密存储，日志自动脱敏（手机号/邮箱/Token）。
- **操作审计**：所有配置变更、权限审批、部署操作、网关路由变更均记录审计日志。

### 8.3 可用性
- 后端无状态设计，支持 K8s 水平伸缩。
- WebSocket 断线自动重连（指数退避），支持会话状态恢复与消息重放。
- 网关适配器故障隔离：单个外部系统（如 Jira 宕机）不影响平台核心功能。
- 关键操作支持“Dry-Run”模式（如部署前模拟）。

### 8.4 可扩展性
- 新阶段可插件化扩展（如增加“运维监控”阶段）。
- 新工具/技能通过 YAML 定义动态注册。
- **网关适配器热插拔**：新外部系统适配器可动态加载，无需重启后端。
- MCP 服务热加载。

### 8.5 可观测性
- 集成 OpenTelemetry，支持分布式追踪（Trace ID 贯穿全链路）。
- 提供 `/metrics` Prometheus 端点（请求数、延迟、错误率、LLM Token消耗）。
- 结构化日志（JSON 格式），支持 ELK/Loki 采集。

---

## 9. 技术架构建议

### 9.1 整体架构分层
```
┌─────────────────────────────────────────────────────────────────┐
│                        前端（React/Vue 3）                      │
├─────────────────────────────────────────────────────────────────┤
│                    API Gateway (Kong/Traefik)                   │
├─────────────────────────────────────────────────────────────────┤
│              核心业务层（FastAPI + Asyncio）                    │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ │
│  │项目/阶段 │ │需求/设计 │ │代码开发  │ │测试/缺陷│ │部署/验收│ │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘ │
├─────────────────────────────────────────────────────────────────┤
│              集成网关层（Integration Gateway）                  │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐             │
│  │Jira适配器│ │钉钉适配器│ │Jenkins  │ │GitLab   │  ...       │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘             │
├─────────────────────────────────────────────────────────────────┤
│              AI 引擎层（opencode Core）                         │
│  AgentLoop / SessionStore / Tools / Subagent / Memory / MCP   │
├─────────────────────────────────────────────────────────────────┤
│              基础设施层                                         │
│  PostgreSQL / Redis / MinIO(S3) / SQLite / Celery(可选)       │
└─────────────────────────────────────────────────────────────────┘
```

### 9.2 关键组件选型
| 层级 | 组件 | 选型 |
|------|------|------|
| Web 框架 | FastAPI | 复用 Bridge 模块 |
| 异步任务 | Celery + Redis | 测试执行/部署/影响分析 |
| 数据库（业务） | PostgreSQL | 需求/设计/部署记录等 |
| 会话存储 | SQLite（原有）+ Redis 缓存 | - |
| 对象存储 | MinIO / S3 | 文档/图表/报告 |
| 网关适配器 SDK | 自研 `BaseAdapter` | 参考 Hermes |
| 部署执行 | kubectl / Ansible / SSH | 通过子进程调用 |
| 前端编辑器 | Monaco Editor | - |
| 图表渲染 | ECharts + Mermaid | - |

---

## 10. 实施优先级与里程碑

### P0 核心底座（MVP，第 1-2 月）
- [ ] 平台基础设施（FastAPI 骨架 + PostgreSQL + JWT 认证 + 8 角色 RBAC）
- [ ] 项目管理与六阶段状态机（含快速通道 + 迭代回退）
- [ ] 需求 CRUD + 基础拆解 + 验收标准生成
- [ ] 代码开发核心（复用 opencode: WebSocket 会话 + 文件读写 + 搜索 + 审查）
- [ ] 数据库模型管理（ER 图 + DDL 生成）
- [ ] 测试用例生成 + 单元/集成测试执行
- [ ] 单环境一键部署 + 日志查看 + 健康检查
- [ ] 验收标准检查 + 报告生成
- [ ] 通知中心（站内通知 + WebSocket 推送）

### P1 智能增强与协同（第 3-5 月）
- [ ] 全阶段 AI 生成能力（设计文档/测试优先级/验收报告）
- [ ] 需求校验与冲突检测 + 变更影响分析
- [ ] 代码审查增强 + 依赖图可视化
- [ ] 覆盖率趋势与缺陷管理
- [ ] 部署回滚 + 审批流（PM/TL/运维三级）
- [ ] Git Worktree + Cron 定时任务
- [ ] 需求追溯矩阵 + 版本管理
- [ ] 出站通知适配器（钉钉/飞书/企微推送）

### P2 生态互联与高级特性（第 6-12 月）
- [ ] 集成网关核心（适配器工厂 + 事件路由 + 重试队列）
- [ ] 入站适配器（Jira/TAPD Webhook → 需求同步）
- [ ] CI/CD 集成（Jenkins/GitLab CI 回调）
- [ ] 代码托管集成（GitLab/GitHub MR/PR 自动创建）
- [ ] DDL 变更影响分析 + 索引建议
- [ ] SSO 集成（OAuth2/SAML）
- [ ] 可观测性（OpenTelemetry + Prometheus）

### P3 高级特性（第 13+ 月，按需）
- [ ] 多模型并行对比（/model compare）
- [ ] 灰度发布智能放量（对接 Prometheus 监控指标）
- [ ] 实时监控仪表盘（Dora 指标）
- [ ] 性能测试集成（k6/Locust）

---

## 11. 成功标准（KPI）

| 维度 | 指标 | 目标值 |
|------|------|--------|
| **效率** | 需求→部署全流程耗时 | 较传统模式缩短 **30%** |
| **质量** | AI 生成代码审查通过率 | ≥ 50% |
| **覆盖** | 自动生成测试覆盖率 | ≥ 60%（新项目） |
| **采用** | 团队成员日活 | ≥ 70% 研发人员 |
| **集成** | 外部系统对接数量 | ≥ 3 个（P1: 钉钉/飞书，P2: Jira） |
| **AI** | LLM Token 成本/需求 | 控制在 $2 以内 |

---

## 12. 风险与应对

| 风险 | 影响 | 应对措施 |
|------|------|----------|
| opencode 同步代码改造为异步困难 | 高并发性能不达标 | 关键路径（AgentLoop）保留同步，使用 `asyncio.to_thread` 隔离；WebSocket 仅做 IO 透传 |
| 网关外部系统 API 变更频繁 | 适配器维护成本高 | 采用适配器版本隔离，P2 再抽象为通用网关框架，P0/P1 用硬编码适配器 |
| LLM 输出幻觉导致设计/代码错误 | 质量风险 | 所有 AI 生成内容标注“AI 生成，需人工确认”，加入人工校验门禁 |
| 多租户数据隔离复杂性 | 安全风险 | 项目 ID 作为强制过滤条件，底层查询自动追加 `project_id = ?` |
| 部署引擎（K8s/SSH）环境差异大 | 部署失败率高 | 提供部署模板（Docker Compose/K8s YAML），支持社区贡献模板 |
| 时间线风险 | 延期交付 | P0 聚焦 MVP，严格控制范围；P1/P2 允许延期，不阻塞 P0 上线 |

---

## 13. 附录：术语表

| 术语 | 说明 |
|------|------|
| **Stage-Gate** | 阶段门禁，只有通过当前阶段所有检查才能进入下一阶段 |
| **ER 图** | 实体关系图（Entity-Relationship Diagram） |
| **DDL** | 数据定义语言（Data Definition Language） |
| **MCP** | Model Context Protocol，opencode 集成的外部模型服务协议 |
| **Worktree** | Git 工作树，可在同一仓库下隔离多个工作目录 |
| **适配器（Adapter）** | 封装外部系统 API 差异的组件，实现统一的 `send`/`receive` 接口 |
| **事件路由** | 根据事件类型、来源、内容条件，决定调用哪个处理器或适配器 |

---

> **文档审批**：  
> 本文档由产品团队与架构委员会联合评审通过，作为后续详细设计、开发排期和测试验收的基线依据。如有需求变更，需提交变更请求并更新本文档版本。

---

## 附录 A：需求评审分析报告

**评审日期**：2026-06-16  
**评审范围**：合理性、逻辑性、清晰度、流程合理性、技术可行性  

---

### A.1 合理性分析

#### A.1.1 设计亮点

| 维度 | 评价 |
|------|------|
| **全生命周期覆盖** | 需求→设计→开发→测试→部署→验收六阶段模型是软件工程标准实践，覆盖完整 |
| **Stage-Gate 门禁** | 阶段间设置质量门禁是成熟的项目管理方法论，能有效防止"带病流转" |
| **AI 横向赋能** | 每个阶段均嵌入 AI 辅助（生成/分析/检测/修复），而非仅在开发阶段，方向正确 |
| **分优先级实施** | P0/P1/P2 三级划分合理：P0 聚焦底座，P1 增强智能，P2 生态互联 |
| **角色权限矩阵** | 7 角色 × 6 阶段的权限设计覆盖了实际组织分工 |
| **NFR 量化指标** | P95 <200ms、WebSocket ≥1000 连接等指标具体可测 |
| **API 设计全面** | 精炼后约 67 个端点覆盖所有业务域，RESTful 设计规范 |

#### A.1.2 风险与问题

| # | 问题 | 严重度 | 说明 | 建议修正 |
|---|------|--------|------|----------|
| R1 | **范围膨胀** | 高 | 从 CLI 工具到全生命周期平台是质的飞跃。"完成度约 99.5%"严重误导——opencode 作为 AI 编码助手完成度高，但作为平台底座缺少 ORM、数据库、认证、多租户、异步队列等基础设施 | 将"完成度"修正为"AI 引擎层完成度 95%，平台基础设施完成度 5%" |
| R2 | **集成网关过于复杂** | 高 | Integration Gateway（适配器工厂+事件路由+死信队列）本身是独立产品级系统，与核心平台并行开发会严重分散资源 | P0/P1 用硬编码适配器快速集成，P2 再抽象为通用网关 |
| R3 | **时间线不现实** | 高 | 6 个月完成 P0→P2 相当于同时构建 Jira+Figma+Jenkins+TestLink+网关。即使 10 人团队也至少需 12-18 个月 | 调整为 12 个月分 4 阶段实施 |
| R4 | **缺少用户旅程** | 中 | 只有功能清单和 API 端点，缺少端到端操作流程（如 PM 创建需求→架构师设计→开发编码的完整路径） | 补充 3-5 个核心用户旅程图 |
| R5 | **灰度发布过于超前** | 低 | DEP-05 的金丝雀智能放量属于高级 DevOps 能力 | P2 简化为手动灰度，智能放量推迟到后续版本 |
| R6 | **KPI 目标过于乐观** | 中 | AI 代码审查通过率 ≥75%（业界最优约 40-50%）；Token 成本 ≤$0.5/需求（大需求可能需 $5-10） | 审查通过率降至 50%，Token 成本放宽到 $2 |

---

### A.2 逻辑性分析

#### A.2.1 阶段流转逻辑

**正向流程**：需求 → 设计 → 开发 → 测试 → 部署 → 验收

**问题与修正**：

| 问题 | 说明 | 建议修正 |
|------|------|----------|
| **缺少反向迭代路径** | 测试发现缺陷后应能回退到开发，部署失败后应能回退到测试/开发。实际开发中 60% 场景需回溯 | 增加"迭代回退"机制：允许测试→开发、部署→测试的反向流转 |
| **设计与开发间缺少原型验证** | 直接从 ER 图/DDL 跳到编码，缺少可运行原型验证步骤 | 增加"原型验证"子阶段（可选） |
| **测试阶段定位模糊** | TST-01（用例生成）和 TST-02（执行）是两类不同工作。执行测试需真实 CI 环境（Docker/DB/网络），文档未说明 | 明确测试执行环境的搭建方案 |

#### A.2.2 角色权限逻辑问题

| 问题 | 说明 | 建议修正 |
|------|------|----------|
| **开发者权限过窄** | 开发工程师不能读写测试用例，实际中开发者需编写和运行单测 | 开发者增加"测试-读写"权限 |
| **PM 权限过大** | PM 只读设计，但经常需要调整设计中的业务逻辑描述 | PM 增加"设计-评论"权限 |
| **缺少技术负责人角色** | Tech Lead 负责代码合并、设计审批、部署审批，现有角色无法覆盖 | 新增"Tech Lead"角色 |

#### A.2.3 数据流缺失

| 缺失数据流 | 说明 | 建议补充 |
|------------|------|----------|
| 需求变更 → 下游自动更新 | 仅有影响分析，缺少自动更新机制 | 定义变更传播规则（自动/手动/审批） |
| 代码提交 → CI 触发 | 缺少 CI 触发规则定义 | 补充提交触发器配置 |
| 部署版本 ↔ 验收条目 | 缺少映射关系 | 增加版本-验收关联模型 |

---

### A.3 清晰度分析

#### A.3.1 需细化的模糊表述

| 功能 ID | 模糊点 | 需要明确 |
|---------|--------|----------|
| REQ-01 | "NLP 结构化" | 使用什么模型？抽取精度要求？支持哪些文档格式？ |
| DES-03 | "索引智能推荐" | 扫描范围（全量/增量）？支持的 ORM 框架列表？推荐置信度阈值？ |
| TST-01 | "自动生成测试用例" | 用例格式？与现有测试框架如何集成？覆盖率目标？ |
| DEP-05 | "灰度发布智能放量" | 基于哪些监控指标？放量策略（百分比/时间/用户群）？ |
| ACC-01 | "验收标准自动检查" | 检查维度？通过/失败判定规则？ |

#### A.3.2 缺失的需求模块

| 缺失项 | 重要度 | 说明 | 建议补充 |
|--------|--------|------|----------|
| **通知中心** | 高 | 原 91 个端点中无“通知”端点，用户无法知道任务更新 | ✅ 已补充 `/notifications` 端点（列表/已读/WebSocket 推送） |
| **代码审查工作流** | 高 | DEV-03 提到审查但没有 PR/MR 审核流程 | 补充 Approve/Request Changes/Comment 流程 |
| **版本管理策略** | 高 | 需求/设计/接口定义均需版本历史和 Diff | 补充版本模型（版本号/创建时间/变更摘要） |
| **数据导入/导出** | 中 | 仅提到 CSV 导出追溯矩阵 | 补充批量导入需求/缺陷的完整规格 |
| **操作日志查询** | 中 | `/audit/logs` 仅提到但未定义字段和查询条件 | 补充审计日志数据模型 |

---

### A.4 流程合理性分析

#### A.4.1 Stage-Gate 模型评估

**优点**：阶段门禁确保质量，防止"未设计完就编码"的反模式。

**问题与建议**：

| 问题 | 建议修正 |
|------|----------|
| 过于瀑布式，不适用于快速迭代 | 增加 **"快速通道"**：小需求（<2 人天）可跳过设计阶段直接进入开发 |
| 设计与开发不能并行 | 增加 **"并行模式"**：设计和开发可部分并行（先开发核心模块，同时细化边缘设计） |
| 验收阶段缺少"部分通过"机制 | 支持验收条目的部分通过，未通过项回退到对应阶段 |

#### A.4.2 集成网关流程评估

```
入站: Jira Webhook → Adapter.parse() → 统一事件 → 路由 → 触发 AI → 通知 PM
出站: 部署事件 → 路由 → 钉钉 Adapter → 群消息
```

**待明确问题**：
- 入站"触发 AI"是同步还是异步？异步时 Jira Webhook 超时如何处理？
- 事件路由器如何保证幂等性？同一事件重发是否会重复触发？
- 适配器之间的依赖关系未定义（如 Jenkins 部署需要 GitLab 的 Commit SHA）

---

### A.5 技术可行性评估

#### A.5.1 现有架构 → 目标架构差距

| 能力 | 当前 opencode | 目标需求 | 差距评估 | 复用策略 |
|------|-------------|----------|----------|----------|
| Web 框架 | FastAPI Bridge（仅会话管理） | 全功能 REST API（91 端点） | 需重建路由层、中间件、认证 | Bridge 路由可作为子模块挂载 |
| 数据库 | SQLite（文件级存储） | PostgreSQL + Redis | 需引入 ORM、迁移工具 | 新增 SQLAlchemy 层 |
| 认证 | Bearer Token（单用户） | JWT + RBAC（7+角色） | 需完整 Auth 模块 | 扩展 bridge/auth.py |
| 异步任务 | 同步 AgentLoop | Celery 异步队列 | 需任务调度、状态跟踪 | AgentLoop 用 asyncio.to_thread 隔离 |
| 文件存储 | 本地文件系统 | MinIO/S3 | 需存储抽象层 | 新增 storage 模块 |
| 多租户 | 无 | 项目级隔离 | 需数据隔离中间件 | 新增 tenant middleware |
| 集成网关 | 无 | 适配器+路由+死信 | 全新模块 | 新建 gateway/ 包 |
| 前端 | HTML 测试页 | React/Vue SPA | 全新开发 | 新建 frontend/ 项目 |

**结论**：从当前 CLI 工具到 V2 平台需 **90% 以上的代码重写/新增**。Bridge 模块可作为 WebSocket 层复用，AgentLoop 可作为 AI 引擎层复用。

#### A.5.2 关键技术决策

| 决策点 | 建议选型 | 理由 |
|--------|----------|------|
| AgentLoop 同步→异步 | 保持同步 + `asyncio.to_thread` | CPU 密集的 LLM 调用链，async 化收益低且风险高 |
| ORM | SQLAlchemy 2.0 (async) | 生态成熟、支持 async session、类型安全 |
| 前端框架 | React + Next.js + Ant Design Pro | 生态最丰富、适合管理后台 |
| 网关架构 | P2 再实现通用网关 | P0/P1 先做硬编码适配器快速验证 |
| 任务队列 | Celery + Redis | 成熟稳定，支持定时任务和优先级队列 |
| 数据库 | PostgreSQL 16 | 支持 JSONB（灵活存储需求/设计文档）、全文搜索 |

---

### A.6 修订后的详细开发计划（4 阶段 × 12 个月）

#### Phase 0：平台基础设施（第 1-2 月，6 个 Sprint）

| Sprint | 周期 | 任务 | 产出模块 | 关键技术 |
|--------|------|------|----------|----------|
| S1 | W1-2 | 项目骨架搭建 | `platform/` monorepo、CI/CD、代码规范 | pyproject.toml / pre-commit / GitHub Actions |
| S2 | W2-3 | 数据库层 | SQLAlchemy 模型（Project/Requirement/Design/Session/TestCase/Defect/Deployment）、Alembic 迁移 | SQLAlchemy 2.0 / Alembic / PostgreSQL 16 |
| S3 | W3-4 | 认证与 RBAC | JWT 认证、8 角色权限中间件（新增 Tech Lead）、API Key 管理 | python-jose / passlib / fastapi-users |
| S4 | W4-5 | API 基础框架 | 统一响应格式、分页、错误处理、日志中间件、OpenAPI 文档 | FastAPI / structlog / prometheus-fastapi-instrumentator |
| S5 | W5-6 | 文件存储 | MinIO/S3 抽象层、文件上传/下载/预览 API | minio-py / boto3 |
| S6 | W6-8 | 前端骨架 | React SPA 骨架、路由、布局、登录/注册、基础组件库 | Next.js 14 / Ant Design Pro / Zustand / TanStack Query |

#### Phase 1：核心业务 MVP（第 3-5 月，8 个 Sprint）

| Sprint | 周期 | 任务 | 端点 | AI 能力 |
|--------|------|------|------|--------|
| S7 | W8-9 | 项目管理 | `/projects` CRUD + 六阶段状态机 + Stage-Gate + 快速通道 | - |
| S8 | W9-10 | 需求管理 | `/requirements` CRUD + 需求树（Epic/Feature/Story）+ 批量导入/导出 | REQ-01: NLP 结构化抽取 |
| S9 | W10-11 | 设计管理 | `/design` 文档 + 模块图 + 接口定义 + DB Schema + 版本管理 | DES-01: LLM 设计文档生成 |
| S10 | W11-13 | 代码开发 | 复用 Bridge WebSocket + AgentLoop，增加文件管理 API、代码审查工作流 | DEV-01~DEV-08: 全部复用 opencode |
| S11 | W13-14 | 测试管理 | `/test/plans` + `/defects` CRUD + 执行触发 + 结果流式输出 | TST-01: 测试用例生成 |
| S12 | W14-15 | 部署管理 | `/environments` + `/pipelines` + 单环境部署 + 日志流 + 回滚 | DEP-02: 部署脚本生成 |
| S13 | W15-16 | 验收管理 | `/acceptance/check` + 报告生成 + 部分通过机制 | ACC-02: 验收报告 LLM 润色 |
| S14 | W16-18 | 前端集成 | 项目 Dashboard、需求树视图、代码编辑器（Monaco）、测试报告页、部署日志 | WebSocket 实时推送 |

#### Phase 2：AI 增强与协同（第 6-8 月，6 个 Sprint）

| Sprint | 周期 | 任务 | 端点 | AI 能力 |
|--------|------|------|------|--------|
| S15 | W18-19 | 智能需求分析 | `/requirements/conflict-check` + `/impact-analysis` | REQ-04: 冲突检测 / REQ-05: 变更影响分析 |
| S16 | W19-21 | 智能设计 | ER 图生成 + DDL 多方言 + 索引建议 + DDL 变更影响 | DES-02 / DES-03 / DES-04 |
| S17 | W21-22 | 智能测试 | 失败分析 + 覆盖率趋势 + 缺陷根因分析 | TST-03 / TST-04 / TST-06 |
| S18 | W22-23 | 代码质量 | 依赖图可视化 + 安全扫描增强 + 性能预测 | DEV-04 / TST-06 |
| S19 | W23-24 | 追溯矩阵 | 需求→设计→代码→测试→部署全链路追溯 + 可视化 | ACC-03: 自动补全关联 |
| S20 | W24-26 | 前端增强 | 设计图查看器、追溯图可视化、AI 对话面板、通知中心 | ECharts / Mermaid / 通知 WebSocket |

#### Phase 3：集成网关与生态（第 9-12 月，8 个 Sprint）

| Sprint | 周期 | 任务 | 适配器/模块 | 说明 |
|--------|------|------|-------------|------|
| S21 | W26-27 | 网关核心 | 适配器工厂 + 统一事件格式 + 事件路由器 + 重试队列 | `gateway/` 包 |
| S22 | W27-29 | 出站通知 | 钉钉 / 飞书 / 企微 | 部署通知、审批卡片、群机器人 |
| S23 | W29-31 | 入站集成 | Jira / TAPD | Webhook → 需求同步 → 状态回写 |
| S24 | W31-33 | CI/CD 集成 | Jenkins / GitLab CI | 构建触发 → 测试执行 → 部署流水线 |
| S25 | W33-35 | 代码托管集成 | GitLab / GitHub | MR/PR 自动创建、审查评论、Commit Status |
| S26 | W35-37 | 部署增强 | - | 多环境并行部署、Dry-Run、部署审批流 |
| S27 | W37-39 | 验收闭环 | - | 在线签署、Release Notes 自动生成、发布归档 |
| S28 | W39-40 | 可观测性 | - | OpenTelemetry + Prometheus `/metrics` + 结构化日志 + Grafana Dashboard |

---

### A.7 关键建议汇总

| # | 建议 | 优先级 |
|---|------|--------|
| 1 | **砍掉 P0 的"出站通知适配器"** — P0 应聚焦核心业务 CRUD + 前端骨架 | 高 |
| 2 | **增加"通知中心"模块** — 91 个端点缺少 `/notifications`，协作平台基础 | 高 |
| 3 | **增加"快速通道"** — 小需求（<2 人天）可跳过设计阶段 | 中 |
| 4 | **增加"迭代回退"** — 允许测试→开发、部署→测试的反向流转 | 高 |
| 5 | **调整 KPI 目标** — AI 审查通过率 75%→50%，Token 成本 $0.5→$2 | 中 |
| 6 | **新增"技术负责人"角色** — 负责代码合并审批、设计评审、部署审批 | 高 |
| 7 | **网关架构延后到 P2** — P0/P1 用硬编码适配器快速集成 | 高 |
| 8 | **增加"版本管理"** — 需求/设计/接口定义均需版本历史和 Diff | 中 |
| 9 | **补充用户旅程图** — 至少 3-5 个核心端到端操作流程 | 中 |
| 10 | **修正"完成度"表述** — 明确区分"AI 引擎层"和"平台基础设施"完成度 | 高 |

---

## 附录 B：架构决策记录

**决策日期**：2026-06-16  
**决策范围**：前端/后端/网关的分离与合并策略  

---

### B.1 决策背景

newplan_V2 提出构建三层系统（前端 + 后端 + 集成网关），核心问题是：
1. Web 前端、后端、网关是否应该分开设计？
2. 后端与网关是否可以合并为一个服务？

两个决策需综合考量。

---

### B.2 最终架构决策

| 层级 | 决策 | 理由 |
|------|------|------|
| **前端** | **完全独立**（独立仓库/独立构建） | 技术栈异构（JS/TS vs Python），部署方式不同（CDN vs K8s），开发节奏独立 |
| **后端** | **与网关合并**（同一 FastAPI 服务） | 同技术栈、共享数据库/认证、减少通信开销、降低初期运维复杂度 |
| **网关** | **作为后端子模块**（`platform/gateway/`） | 当前适配器数量 <10，Webhook 接收量 <5000 QPS，不需要独立进程 |
| **opencode** | **保持独立**（AI 引擎库） | 核心 AI 能力不受平台改造影响，CLI 模式保持可用 |

**一句话总结**：**前端独立、后端+网关合并、opencode 作为引擎库被引用**

---

### B.3 目标架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                    前端（Next.js + Ant Design Pro）              │
│  独立构建 / CDN 部署 / WebSocket 客户端                          │
└─────────────────────────────────────────────────────────────────┘
                           ↕ HTTP/REST + WebSocket
┌─────────────────────────────────────────────────────────────────┐
│                  后端服务（FastAPI 单体）                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐         │
│  │ 业务 API 层 │  │ 网关模块    │  │ AI 引擎引用层   │         │
│  │ (91 个端点) │  │ adapters/   │  │ import opencode │         │
│  │             │  │ router.py   │  │                 │         │
│  │ projects/   │  │ webhooks.py │  │ AgentLoop       │         │
│  │ requirements│  │ events.py   │  │ SessionStore    │         │
│  │ sessions/   │  │ retry.py    │  │ Tools/Memory    │         │
│  └─────────────┘  └─────────────┘  └─────────────────┘         │
├─────────────────────────────────────────────────────────────────┤
│  PostgreSQL / Redis / Celery Worker / MinIO                    │
└─────────────────────────────────────────────────────────────────┘
```

---

### B.4 项目目录结构

```
opencode/                        # 现有：AI 引擎（保持不动）
├── core/                        # AgentLoop / SessionState / Memory
├── tools/                       # 50+ 工具
├── bridge/                      # WebSocket 会话管理
├── services/                    # 持久化服务
└── ...                          # CLI / 配置 / 测试

platform/                        # 新增：业务后端 + 网关（同一服务）
├── main.py                      # FastAPI 入口（注册所有路由）
├── api/                         # 业务 API 端点
│   ├── projects.py
│   ├── requirements.py
│   ├── design.py
│   ├── sessions.py
│   ├── testing.py
│   ├── deployment.py
│   ├── acceptance.py
│   └── notifications.py         # 通知中心（补充缺失模块）
├── gateway/                     # 网关模块（内嵌）
│   ├── __init__.py
│   ├── adapters/                # 适配器
│   │   ├── base.py              # BaseAdapter 抽象类
│   │   ├── dingtalk.py          # 钉钉
│   │   ├── feishu.py            # 飞书
│   │   ├── wecom.py             # 企业微信
│   │   ├── jira.py              # Jira/TAPD
│   │   └── jenkins.py           # Jenkins/GitLab CI
│   ├── events.py                # 统一事件模型（Pydantic）
│   ├── router.py                # 事件路由器（条件分发）
│   ├── webhooks.py              # Webhook 接收端点
│   └── retry.py                 # 重试队列（Celery 任务）
├── core/                        # 业务核心（非 AI）
│   ├── stage_gate.py            # 阶段门禁状态机
│   ├── traceability.py          # 追溯矩阵
│   └── versioning.py            # 版本管理
├── models/                      # SQLAlchemy ORM 模型
│   ├── project.py
│   ├── requirement.py
│   ├── design.py
│   ├── test_case.py
│   ├── defect.py
│   ├── deployment.py
│   └── notification.py
├── auth/                        # JWT + RBAC
│   ├── jwt.py
│   ├── rbac.py                  # 8 角色（含 Tech Lead）
│   └── middleware.py
├── tasks/                       # Celery 异步任务
│   ├── ai_tasks.py              # LLM 调用异步包装
│   ├── test_tasks.py            # 测试执行
│   └── deploy_tasks.py          # 部署执行
└── config.py                    # 服务配置

frontend/                        # 新增：Web 前端（完全独立）
├── package.json
├── next.config.js
├── src/
│   ├── app/                     # Next.js 页面路由
│   ├── components/              # 通用组件
│   ├── services/                # API 调用层（axios）
│   ├── stores/                  # Zustand 状态管理
│   └── hooks/                   # 自定义 hooks
└── public/
```

---

### B.5 后端与网关合并的具体实现

#### B.5.1 Webhook 端点挂载

```python
# platform/main.py
from fastapi import FastAPI
from api import projects, requirements, sessions  # 业务 API
from gateway.webhooks import router as webhook_router  # 网关 Webhook

app = FastAPI(title="OpenCode Platform")

# 业务 API 路由
app.include_router(projects.router, prefix="/api/v1")
app.include_router(requirements.router, prefix="/api/v1")
app.include_router(sessions.router, prefix="/api/v1")

# 网关 Webhook 路由（外部系统回调）
app.include_router(webhook_router, prefix="/webhooks")
```

#### B.5.2 适配器调用（Celery 异步）

```python
# platform/gateway/router.py
from celery import shared_task
from gateway.adapters.dingtalk import DingTalkAdapter
from gateway.adapters.jira import JiraAdapter

@shared_task(bind=True, max_retries=3)
def dispatch_event(self, event_type: str, payload: dict):
    """事件路由：根据事件类型分发到对应适配器"""
    routes = {
        "deployment.success": [DingTalkAdapter, "notify_deploy"],
        "requirement.updated": [JiraAdapter, "sync_requirement"],
        "review.approved": [DingTalkAdapter, "notify_review"],
    }
    adapter_cls, method = routes.get(event_type, [None, None])
    if adapter_cls:
        getattr(adapter_cls(), method)(payload)
```

#### B.5.3 事件模型（统一格式）

```python
# platform/gateway/events.py
from pydantic import BaseModel
from enum import Enum
from datetime import datetime

class EventType(str, Enum):
    REQUIREMENT_UPDATED = "requirement.updated"
    DESIGN_REVIEWED = "design.reviewed"
    CODE_COMMITTED = "code.committed"
    TEST_PASSED = "test.passed"
    DEPLOYMENT_SUCCESS = "deployment.success"
    DEPLOYMENT_FAILED = "deployment.failed"
    ACCEPTANCE_APPROVED = "acceptance.approved"

class PlatformEvent(BaseModel):
    event_id: str
    event_type: EventType
    project_id: str
    source: str          # 触发来源（web/jira/jenkins）
    payload: dict
    timestamp: datetime = datetime.utcnow()
```

---

### B.6 与 opencode 的集成方式

**关键原则**：opencode 作为 Python 库被平台后端 import，而非 HTTP 调用

```python
# platform/api/sessions.py
from fastapi import APIRouter, WebSocket
from opencode.core.agent_loop import AgentLoop        # 引用 AI 引擎
from opencode.bridge.session import BridgeSession      # 引用会话管理
from opencode.bridge.manager import BridgeSessionManager

router = APIRouter()

@router.post("/projects/{project_id}/sessions")
async def create_session(project_id: str, req: CreateSessionReq):
    """创建开发会话（复用 opencode BridgeSession）"""
    config = SessionConfig(
        work_dir=get_project_workdir(project_id),
        model=req.model,
        ...
    )
    session = session_manager.create_session(config)
    return {"session_id": session.session_id}

@router.websocket("/sessions/{session_id}/ws")
async def session_websocket(ws: WebSocket, session_id: str):
    """WebSocket 会话（复用 opencode Bridge 事件推送）"""
    ...
```

---

### B.7 分阶段演进路线

| 阶段 | 架构形态 | 说明 |
|------|----------|------|
| **P0（第 1-2 月）** | Monorepo 内分层 | opencode + platform + frontend 在同一仓库，后端/网关合并为单一 FastAPI 服务 |
| **P1（第 3-5 月）** | 同 P0 | 网关模块逐步完善（适配器从 2 个增至 5 个），仍为同一服务 |
| **P2（第 6-8 月）** | 同 P0 | AI 增强功能嵌入后端，追溯矩阵等复杂功能加入 |
| **P3+（如需）** | 可选拆分 | 当网关适配器 >15 个 或 Webhook QPS >5000 时，将 gateway/ 拆为独立服务 |

---

### B.8 关键决策对比表

| 方案 | 前端 | 后端 | 网关 | 适用场景 |
|------|------|------|------|----------|
| A. 全部合并 | 嵌入后端 | 合并 | 合并 | 极小项目（已排除） |
| B. 前端独立，后端+网关合并 | **独立** | **合并** | **合并** | **当前选择（P0-P2）** |
| C. 三层完全分离 | 独立 | 独立 | 独立 | 大团队/高并发（P3+ 备选） |
| D. 微服务 | 独立 | 拆多个 | 独立 | 超大规模（暂不需要） |

---

### B.9 风险与缓解

| 风险 | 概率 | 缓解措施 |
|------|------|----------|
| 后端+网关合并后代码耦合 | 中 | gateway/ 模块严格只依赖 events.py 和 base.py，不直接 import api/ |
| 适配器崩溃影响核心 API | 低 | 适配器调用全部走 Celery 异步任务，异常不影响 API 响应 |
| 未来拆分困难 | 低 | gateway/ 已设计为独立模块，拆分时只需改 import 为 HTTP 调用 |
| 前端与后端接口契约不一致 | 中 | 后端提供 OpenAPI 文档，前端用 openapi-typescript-codegen 自动生成调用层 |