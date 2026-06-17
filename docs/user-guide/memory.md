# 记忆系统

记忆系统让 AI 能够跨会话记住重要的项目知识和用户偏好。记忆在每次对话开始时自动注入，并随时间衰减以保持相关性。

---

## 核心概念

| 概念 | 说明 |
|------|------|
| **记忆条目** | 单条知识点（如"项目使用 PostgreSQL 16"）|
| **新鲜度** | 记忆的新近程度，随时间衰减（7天内为"新鲜"）|
| **语义召回** | LLM 驱动的自动检索，在对话时注入相关记忆 |
| **持久化** | 记忆保存在 `~/.opencode/memories/`，跨会话共享 |

---

## 自动注入

每次对话开始时，OpenCode 会：

1. 扫描记忆文件，构建记忆清单
2. 根据你的提问，LLM 自动检索相关记忆
3. 将相关记忆注入系统提示词（标记新鲜度）

```
> 帮我写数据库迁移脚本

[系统自动注入]:
  📝 记忆: 项目使用 PostgreSQL 16 + SQLAlchemy 2.0 (2天前)
  📝 记忆: 迁移脚本放在 migrations/ 目录 (5天前)
```

---

## 管理命令

### 查看记忆

```
> /memory list

记忆条目 (共 23 条):
  #1  [新鲜] 项目使用 PostgreSQL 16          2天前
  #2  [新鲜] API 认证使用 JWT Bearer Token    3天前
  #3  [一般] 代码风格遵循 PEP 8               12天前
  ...
```

### 搜索记忆

```
> /memory search "数据库"

匹配结果:
  #1  项目使用 PostgreSQL 16 + SQLAlchemy 2.0
  #5  数据库连接池大小: 20
  #12 测试数据库: SQLite in-memory
```

### 手动添加记忆

```
> /memory add "本项目的前端框架是 Next.js 14 + TypeScript"

✅ 记忆已保存
```

### 删除记忆

```
> /memory delete 5

✅ 记忆 #5 已删除
```

### 导出记忆

```
> /memory export memories_backup.json

✅ 已导出 23 条记忆到 memories_backup.json
```

---

## 记忆工具

AI 也可以通过工具操作记忆：

| 工具 | 说明 |
|------|------|
| `save_memory` | 保存记忆条目 |
| `load_memory` | 加载指定记忆 |
| `search_memories` | 语义搜索 |
| `list_memories` | 列出记忆索引 |
| `get_memory_summary` | 获取摘要 |
| `get_relevant_memories` | LLM 驱动的相关记忆召回 |
| `delete_memory` | 删除记忆 |

---

## 存储位置

```
~/.opencode/memories/
├── memory_manifest.json    # 记忆清单（索引+时间戳）
└── entries/                # 记忆条目文件
    ├── mem_001.json
    ├── mem_002.json
    └── ...
```

---

## 相关命令

| 命令 | 说明 |
|------|------|
| `/memory` | 记忆管理入口 |
| `/memory list` | 列出所有记忆 |
| `/memory search <query>` | 语义搜索 |
| `/memory add <content>` | 手动添加 |
| `/memory delete <id>` | 删除记忆 |
| `/memory export <file>` | 导出为文件 |
