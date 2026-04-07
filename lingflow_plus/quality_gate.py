"""质量门

自动代码审查，提交前强制质量检查。
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from lingflow.core.types import Result

logger = logging.getLogger(__name__)

DEFAULT_MIN_SCORE = 70
DEFAULT_MAX_CRITICAL = 0


@dataclass
class QualityReport:
    """质量报告"""
    score: int
    passed: bool
    dimensions: Dict[str, int]
    critical_issues: List[str]
    warnings: List[str]
    summary: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "passed": self.passed,
            "dimensions": self.dimensions,
            "critical_issues": self.critical_issues,
            "warnings": self.warnings,
            "summary": self.summary,
        }


class QualityGate:
    """提交质量门

    在 commit 前自动调用灵通 code-review skill。
    如果质量分低于阈值或存在 critical issue，阻止提交。
    """

    def __init__(
        self,
        min_score: int = DEFAULT_MIN_SCORE,
        max_critical: int = DEFAULT_MAX_CRITICAL,
        dimensions: Optional[List[str]] = None,
    ):
        self.min_score = min_score
        self.max_critical = max_critical
        self.dimensions = dimensions or [
            "code_quality",
            "architecture",
            "performance",
            "security",
            "maintainability",
            "best_practices",
            "consistency",
            "bug_risk",
        ]

    def check(self, review_result: Result) -> QualityReport:
        """检查审查结果是否通过质量门"""
        if review_result.is_error:
            return QualityReport(
                score=0,
                passed=False,
                dimensions={},
                critical_issues=[f"Review failed: {review_result.error}"],
                warnings=[],
                summary=f"Quality gate error: {review_result.error}",
            )

        data = review_result.data or {}
        score = data.get("score", 0)
        dimensions = data.get("dimensions", {})
        critical = data.get("critical_issues", [])
        warnings = data.get("warnings", [])

        passed = score >= self.min_score and len(critical) <= self.max_critical

        return QualityReport(
            score=score,
            passed=passed,
            dimensions=dimensions,
            critical_issues=critical,
            warnings=warnings,
            summary=f"Score: {score}/{100}, Critical: {len(critical)}, {'PASSED' if passed else 'BLOCKED'}",
        )

    def check_file_changes(self, changed_files: List[str]) -> QualityReport:
        """快速检查文件变更列表（不依赖 code-review skill）"""
        issues: List[str] = []
        warnings: List[str] = []
        score = 100

        for f in changed_files:
            if ".env" in f or "secret" in f.lower() or "credential" in f.lower():
                issues.append(f"Potential secret file: {f}")
                score -= 20
            if f.endswith(".pyc") or f.endswith(".pyo") or "__pycache__" in f:
                warnings.append(f"Compiled/binary file: {f}")
                score -= 5
            if "test_" not in f and f.endswith(".py"):
                has_test = any(
                    tf for tf in changed_files
                    if "test_" in tf and tf.replace("test_", "").rstrip("/").endswith(f.rstrip("/").split("/")[-1])
                )
                if not has_test and len(changed_files) > 3:
                    warnings.append(f"No test for: {f}")

        score = max(0, score)
        passed = score >= self.min_score and len(issues) <= self.max_critical

        return QualityReport(
            score=score,
            passed=passed,
            dimensions={"file_check": score},
            critical_issues=issues,
            warnings=warnings,
            summary=f"File check: {score}/100, Critical: {len(issues)}, {'PASSED' if passed else 'BLOCKED'}",
        )
