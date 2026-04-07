# LingFlow+

灵字辈生态系统的多项目并行 CLI Agent。

## 设计宪章

**轻框架，多工具。重流程，重协调，重约束，重验证。和谐欢畅，自然端庄。**

## 架构

```
LingFlow+ (集成层, ~800 行)
├── project_manager.py   项目注册、Git 状态、会话绑定
├── scheduler.py         跨项目并行调度（复用 LingFlow WorkflowOrchestrator）
├── constraints.py       TokenQuota + RateLimiter + FileLock + ContextBudget
├── tool_router.py       任务类型 → Agent 路由（MCP 协议）
├── quality_gate.py      提交前质量门
├── coordinator.py       主协调器（组合所有子系统）
└── cli.py               CLI 入口（+run, +status, +projects, +dashboard, +review）
```

## 依赖

- `lingflow` — 工作流引擎
- `pyyaml` — YAML 工作流加载

## 安装

```bash
pip install -e .
```

## 使用

```bash
# 注册项目
lingflow-plus register LingFlow /home/ai/LingFlow
lingflow-plus register LingClaude /home/ai/LingClaude

# 查看所有项目
lingflow-plus projects

# 看板
lingflow-plus dashboard

# 执行跨项目工作流
lingflow-plus run workflow.yaml

# 质量门检查
lingflow-plus review src/main.py tests/test_main.py

# 全局状态
lingflow-plus status
```

## 测试

```bash
pytest tests/ -v
```
