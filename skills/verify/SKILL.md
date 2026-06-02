---
name: verify
description: 验证代码变更是否按预期工作，通过运行应用/测试来确认
trigger: 当完成代码修改需要验证正确性时激活，或用户主动调用 /verify
---

# Verify: 验证代码变更

确认代码变更是否按预期工作。通过实际运行应用或测试来验证，而非仅靠代码审查。

## 核心原则

**不要假设变更是正确的——证明它是正确的。**

## 验证流程

### Step 1: 理解变更

1. 运行 `git diff`（或 `git diff HEAD`）查看变更内容
2. 理解变更的目的：新功能、bug 修复、重构、性能优化？
3. 识别变更涉及的关键模块和入口点

### Step 2: 确定验证策略

根据项目类型选择验证方式：

**CLI / 命令行工具:**
```bash
# 构建项目
python -m build  # 或 pip install -e .

# 直接运行
python -m your_module --help
python -m your_module <test-args>

# 验证退出码
echo $?  # 0 = 成功
```

**Web 服务 / API:**
```bash
# 启动服务（后台运行）
python -m uvicorn app:app --port 8080 &

# 测试端点
curl -s http://localhost:8080/health
curl -X POST http://localhost:8080/api/endpoint -H "Content-Type: application/json" -d '{}'

# 停止服务
kill %1
```

**库 / 模块:**
```bash
# 运行测试套件
python -m pytest tests/ -v
python -m pytest tests/test_changed_module.py -v

# 交互式验证
python -c "from your_module import changed_func; print(changed_func())"
```

**前端应用:**
```bash
# 开发服务器
npm run dev  # 或 yarn dev / pnpm dev

# 构建验证
npm run build

# 测试
npm test
```

### Step 3: 执行验证

1. **运行测试套件** — 确保现有测试全部通过
2. **手动验证变更行为** — 用真实输入测试新功能/修复
3. **边界情况测试** — 测试空值、极端输入、错误路径
4. **回归检查** — 确认未破坏已有功能

### Step 4: 报告结果

输出验证报告：

```
## 验证结果

### 变更概要
- 修改了: [文件列表]
- 目的: [变更目的]

### 测试执行
- 测试套件: ✅ 通过 (N/N) / ❌ 失败 (X/N)
- 手动验证: ✅ 行为符合预期 / ❌ 发现问题

### 验证详情
- [具体验证步骤和结果]

### 结论
- ✅ 变更验证通过 / ⚠️ 发现问题需要修复
```

## 常见验证陷阱

- ❌ 只运行了 `--help` 就认为没问题
- ❌ 没有测试错误路径和边界情况
- ❌ 假设测试通过就等于功能正确
- ❌ 忽略了编译警告和 deprecation 提示

## 验证原则

1. **端到端优于单元测试** — 实际运行比 mock 更有说服力
2. **真实数据优于测试数据** — 尽量用真实场景验证
3. **负面测试与正面测试同样重要** — 确保错误被正确处理
4. **自动化优于手动** — 如果可以，写测试用例固化验证
