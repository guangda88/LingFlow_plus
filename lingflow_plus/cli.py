"""LingFlow+ CLI 入口

命令：
    +run <workflow.yaml>    执行跨项目工作流
    +status                 查看全局状态
    +projects               列出注册的项目
    +register <name> <path> 注册项目
    +unregister <name>      取消注册
    +dashboard              看板（所有项目状态）
    +review <files...>      质量门检查
    +version                版本信息
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from lingflow_plus import __version__
from lingflow_plus.coordinator import LingFlowPlus


def cmd_status(args: argparse.Namespace) -> None:
    """查看全局状态"""
    lf = LingFlowPlus()
    status = lf.status()
    print(json.dumps(status, indent=2, ensure_ascii=False, default=str))


def cmd_projects(args: argparse.Namespace) -> None:
    """列出所有项目"""
    lf = LingFlowPlus()
    projects = lf.project_manager.list()
    if not projects:
        print("No projects registered.")
        return
    for p in projects:
        git = p.git_status()
        session = p.terminal_session or "-"
        print(f"  {p.name:20s} {git.get('branch', '?'):15s} dirty={git.get('dirty_files', 0):3d} session={session}")
        if p.description:
            print(f"  {'':20s} {p.description}")


def cmd_register(args: argparse.Namespace) -> None:
    """注册项目"""
    lf = LingFlowPlus()
    path = str(Path(args.path).resolve())
    ctx = lf.project_manager.register(args.name, path, description=args.description or "")
    print(f"Registered: {ctx.name} -> {ctx.path}")


def cmd_unregister(args: argparse.Namespace) -> None:
    """取消注册"""
    lf = LingFlowPlus()
    if lf.project_manager.unregister(args.name):
        print(f"Unregistered: {args.name}")
    else:
        print(f"Project not found: {args.name}")


def cmd_dashboard(args: argparse.Namespace) -> None:
    """看板"""
    lf = LingFlowPlus()
    dash = lf.project_manager.dashboard()
    for item in dash:
        name = item.get("name", "?")
        git = item.get("git", {})
        valid = item.get("valid", False)
        branch = git.get("branch", "?")
        dirty = git.get("dirty_files", 0)
        status_mark = "✓" if valid else "✗"
        print(f"  [{status_mark}] {name:20s} branch={branch:15s} dirty={dirty}")
    token_status = lf.token_quota.get_status()
    print(f"\n  Token: {token_status['window_used']:,} / {token_status['window_total']:,} used")


def cmd_run(args: argparse.Namespace) -> None:
    """执行工作流"""
    lf = LingFlowPlus()
    filepath = args.workflow
    if not Path(filepath).exists():
        print(f"File not found: {filepath}")
        sys.exit(1)
    print(f"Loading workflow: {filepath}")
    results = lf.run_workflow_file(filepath)
    success = sum(1 for r in results.values() if r.success)
    failed = sum(1 for r in results.values() if not r.success)
    print(f"Done: {success} success, {failed} failed, {len(results)} total")


def cmd_review(args: argparse.Namespace) -> None:
    """质量门检查"""
    lf = LingFlowPlus()
    report = lf.quality_check(args.files)
    print(f"Score: {report.score}/100")
    print(f"Gate: {'PASSED' if report.passed else 'BLOCKED'}")
    if report.critical_issues:
        print("\nCritical issues:")
        for issue in report.critical_issues:
            print(f"  ✗ {issue}")
    if report.warnings:
        print("\nWarnings:")
        for w in report.warnings:
            print(f"  ⚠ {w}")


def cmd_version(args: argparse.Namespace) -> None:
    """版本信息"""
    print(f"LingFlow+ v{__version__}")


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        prog="lingflow-plus",
        description="LingFlow+ — 灵字辈多项目并行 CLI Agent",
    )
    sub = parser.add_subparsers(dest="command")

    p_run = sub.add_parser("run", help="Execute cross-project workflow")
    p_run.add_argument("workflow", help="YAML workflow file")
    p_run.set_defaults(func=cmd_run)

    p_status = sub.add_parser("status", help="Global status")
    p_status.set_defaults(func=cmd_status)

    p_projects = sub.add_parser("projects", help="List projects")
    p_projects.set_defaults(func=cmd_projects)

    p_register = sub.add_parser("register", help="Register project")
    p_register.add_argument("name", help="Project alias")
    p_register.add_argument("path", help="Project directory")
    p_register.add_argument("--description", "-d", default="", help="Description")
    p_register.set_defaults(func=cmd_register)

    p_unregister = sub.add_parser("unregister", help="Unregister project")
    p_unregister.add_argument("name", help="Project alias")
    p_unregister.set_defaults(func=cmd_unregister)

    p_dashboard = sub.add_parser("dashboard", help="Dashboard view")
    p_dashboard.set_defaults(func=cmd_dashboard)

    p_review = sub.add_parser("review", help="Quality gate check")
    p_review.add_argument("files", nargs="+", help="Files to check")
    p_review.set_defaults(func=cmd_review)

    p_version = sub.add_parser("version", help="Version info")
    p_version.set_defaults(func=cmd_version)

    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(0)
    args.func(args)


if __name__ == "__main__":
    main()
