"""
代码理解深化模块

功能:
1. DependencyGraph: 项目依赖图分析
   - 自动解析 Python import/require 关系
   - 支持 JS/TS import/export 解析
   - 循环依赖检测
   - 依赖深度分析

2. ImpactAnalyzer: 代码变更影响分析
   - 给定修改文件列表，计算受影响文件
   - 反向依赖查找 (谁依赖了被修改的文件)
   - 影响等级评估 (直接/间接/无关)
   - 测试覆盖影响分析

用法:
    analyzer = CodeAnalyzer(project_root=".")
    graph = analyzer.build_dependency_graph()
    impacted = analyzer.analyze_impact(["src/auth.py", "src/db.py"])
    report = analyzer.generate_impact_report(["src/auth.py"])
"""

import os
import re
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


def _safe_relpath(path: str, start: str) -> str:
    """安全的 os.path.relpath，处理 Windows 跨盘符问题"""
    try:
        return os.path.relpath(path, start)
    except ValueError:
        # Windows 跨盘符时 relpath 会抛出 ValueError
        return path


# ── 依赖图 ─────────────────────────────────────────────────


@dataclass
class DepNode:
    """依赖图节点"""
    file_path: str             # 绝对路径
    module_name: str           # 模块名 (如 core.agent_loop)
    language: str = "python"   # python/javascript/typescript
    imports: List[str] = field(default_factory=list)    # 导入的模块
    imported_by: List[str] = field(default_factory=list) # 被谁导入
    depth: int = 0             # 依赖深度 (0=叶子节点)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "module_name": self.module_name,
            "language": self.language,
            "imports": self.imports,
            "imported_by": self.imported_by,
            "depth": self.depth,
        }


class DependencyGraph:
    """
    项目依赖图

    支持:
    - Python: import / from X import
    - JavaScript/TypeScript: import / require / export
    - 循环依赖检测
    - 依赖深度计算
    """

    # Python import 正则
    PY_IMPORT = re.compile(
        r'^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))',
        re.MULTILINE
    )

    # JS/TS import 正则
    JS_IMPORT = re.compile(
        r"""(?:import\s+.*?from\s+['"](.+?)['"]|"""
        r"""require\s*\(\s*['"](.+?)['"]\s*\))""",
        re.MULTILINE
    )

    # 忽略的模块/路径
    IGNORE_MODULES = {
        "os", "sys", "json", "re", "time", "typing", "logging",
        "pathlib", "collections", "dataclasses", "datetime",
        "threading", "asyncio", "hashlib", "uuid", "abc",
        "functools", "itertools", "copy", "math", "io",
        "subprocess", "shutil", "glob", "fnmatch",
    }

    def __init__(self, project_root: str = "."):
        self.project_root = os.path.abspath(project_root)
        self.nodes: Dict[str, DepNode] = {}  # file_path -> DepNode
        self._adjacency: Dict[str, Set[str]] = defaultdict(set)  # file -> depends_on files
        self._reverse_adj: Dict[str, Set[str]] = defaultdict(set)  # file -> depended_by files

    def build(self, scan_dirs: List[str] = None) -> Dict[str, DepNode]:
        """
        构建项目依赖图

        Args:
            scan_dirs: 要扫描的目录列表 (默认扫描 project_root)

        Returns:
            {file_path: DepNode}
        """
        if scan_dirs is None:
            scan_dirs = [self.project_root]

        # 1. 扫描所有源文件
        files = self._scan_files(scan_dirs)
        logger.info(f"Scanning {len(files)} source files")

        # 2. 解析每个文件的导入
        for file_path in files:
            node = self._parse_file(file_path)
            if node:
                self.nodes[file_path] = node

        # 3. 解析模块名到文件路径的映射
        module_to_file = self._build_module_map()

        # 4. 构建邻接关系
        for file_path, node in self.nodes.items():
            for imp in node.imports:
                target = module_to_file.get(imp)
                if target and target != file_path:
                    self._adjacency[file_path].add(target)
                    self._reverse_adj[target].add(file_path)
                    if target not in node.imported_by:
                        # 反向关系在目标节点中记录
                        pass

            # 填充 imported_by
            for dep_file in self._adjacency.get(file_path, set()):
                if dep_file in self.nodes:
                    if file_path not in self.nodes[dep_file].imported_by:
                        self.nodes[dep_file].imported_by.append(file_path)

        # 5. 计算深度
        self._compute_depths()

        logger.info(f"Dependency graph: {len(self.nodes)} nodes, "
                     f"{sum(len(v) for v in self._adjacency.values())} edges")
        return self.nodes

    def _scan_files(self, dirs: List[str]) -> List[str]:
        """扫描源文件"""
        extensions = {'.py', '.js', '.ts', '.jsx', '.tsx'}
        skip_dirs = {'node_modules', '__pycache__', '.git', '.venv', 'venv', 'dist', 'build'}

        files = []
        for scan_dir in dirs:
            scan_path = Path(scan_dir)
            if not scan_path.exists():
                continue
            for ext in extensions:
                for f in scan_path.rglob(f"*{ext}"):
                    # 跳过特定目录
                    if any(skip in f.parts for skip in skip_dirs):
                        continue
                    files.append(str(f))
        return files

    def _parse_file(self, file_path: str) -> Optional[DepNode]:
        """解析单个文件的导入"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception:
            return None

        ext = Path(file_path).suffix
        if ext == '.py':
            return self._parse_python(file_path, content)
        elif ext in ('.js', '.ts', '.jsx', '.tsx'):
            return self._parse_js(file_path, content)
        return None

    def _parse_python(self, file_path: str, content: str) -> DepNode:
        """解析 Python 文件导入"""
        imports = []
        for match in self.PY_IMPORT.finditer(content):
            module = match.group(1) or match.group(2)
            if module:
                # 取顶级模块名
                top = module.split('.')[0]
                if top not in self.IGNORE_MODULES:
                    imports.append(module)

        rel_path = _safe_relpath(file_path, self.project_root)
        module_name = rel_path.replace(os.sep, '.').replace('.py', '')

        return DepNode(
            file_path=file_path,
            module_name=module_name,
            language="python",
            imports=list(set(imports)),
        )

    def _parse_js(self, file_path: str, content: str) -> DepNode:
        """解析 JS/TS 文件导入"""
        imports = []
        for match in self.JS_IMPORT.finditer(content):
            module = match.group(1) or match.group(2)
            if module and not module.startswith('.') and not module.startswith('/'):
                # 外部模块 (npm 包)
                pkg = module.split('/')[0]
                if pkg.startswith('@'):
                    pkg = '/'.join(module.split('/')[:2])
                imports.append(pkg)
            elif module:
                # 相对/绝对路径
                imports.append(module)

        rel_path = _safe_relpath(file_path, self.project_root)
        module_name = rel_path.replace(os.sep, '/')

        return DepNode(
            file_path=file_path,
            module_name=module_name,
            language="javascript" if file_path.endswith('.js') else "typescript",
            imports=list(set(imports)),
        )

    def _build_module_map(self) -> Dict[str, str]:
        """构建模块名 → 文件路径映射"""
        mapping = {}
        for file_path, node in self.nodes.items():
            mapping[node.module_name] = file_path
            # 也添加部分匹配
            parts = node.module_name.split('.')
            for i in range(1, len(parts)):
                partial = '.'.join(parts[:i])
                if partial not in mapping:
                    mapping[partial] = file_path
        return mapping

    def _compute_depths(self):
        """计算每个节点的依赖深度 (BFS)"""
        # 叶子节点 (无导入) 深度为 0
        for file_path, node in self.nodes.items():
            if not self._adjacency.get(file_path):
                node.depth = 0

        # 反向 BFS
        visited = set()
        queue = deque()

        # 从叶子节点开始
        for fp, node in self.nodes.items():
            if node.depth == 0:
                queue.append(fp)
                visited.add(fp)

        while queue:
            current = queue.popleft()
            current_depth = self.nodes[current].depth if current in self.nodes else 0

            # 谁依赖了 current
            for dependent in self._reverse_adj.get(current, set()):
                if dependent not in visited and dependent in self.nodes:
                    self.nodes[dependent].depth = max(
                        self.nodes[dependent].depth,
                        current_depth + 1
                    )
                    visited.add(dependent)
                    queue.append(dependent)

    def detect_cycles(self) -> List[List[str]]:
        """检测循环依赖"""
        visited = set()
        rec_stack = set()
        cycles = []

        def _dfs(node, path):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for dep in self._adjacency.get(node, set()):
                if dep not in self.nodes:
                    continue
                if dep not in visited:
                    _dfs(dep, path)
                elif dep in rec_stack:
                    idx = path.index(dep)
                    cycles.append(path[idx:] + [dep])

            path.pop()
            rec_stack.discard(node)

        for node in self.nodes:
            if node not in visited:
                _dfs(node, [])

        return cycles

    def get_dependents(self, file_path: str, max_depth: int = 5) -> List[str]:
        """获取文件的所有依赖 (正向)"""
        result = set()
        visited = set()
        queue = deque([(file_path, 0)])

        while queue:
            current, depth = queue.popleft()
            if depth > max_depth or current in visited:
                continue
            visited.add(current)
            if current != file_path:
                result.add(current)
            for dep in self._adjacency.get(current, set()):
                if dep not in visited:
                    queue.append((dep, depth + 1))

        return list(result)

    def get_reverse_dependents(self, file_path: str, max_depth: int = 5) -> List[str]:
        """获取依赖该文件的所有文件 (反向)"""
        result = set()
        visited = set()
        queue = deque([(file_path, 0)])

        while queue:
            current, depth = queue.popleft()
            if depth > max_depth or current in visited:
                continue
            visited.add(current)
            if current != file_path:
                result.add(current)
            for dep in self._reverse_adj.get(current, set()):
                if dep not in visited:
                    queue.append((dep, depth + 1))

        return list(result)

    def get_stats(self) -> Dict[str, Any]:
        """统计"""
        languages = defaultdict(int)
        for node in self.nodes.values():
            languages[node.language] += 1

        total_edges = sum(len(v) for v in self._adjacency.values())
        max_depth = max((n.depth for n in self.nodes.values()), default=0)

        return {
            "total_files": len(self.nodes),
            "total_dependencies": total_edges,
            "languages": dict(languages),
            "max_depth": max_depth,
            "cycles": len(self.detect_cycles()),
        }


# ── 变更影响分析 ────────────────────────────────────────────


@dataclass
class ImpactResult:
    """影响分析结果"""
    changed_files: List[str]
    direct_impact: List[str]         # 直接影响的文件
    indirect_impact: List[str]       # 间接影响
    total_impact: int                # 总影响文件数
    impact_level: str                # low/medium/high/critical
    test_files_affected: List[str]   # 受影响的测试文件
    risk_assessment: str = ""        # 风险评估

    def to_dict(self) -> Dict[str, Any]:
        return {
            "changed_files": self.changed_files,
            "direct_impact": self.direct_impact,
            "indirect_impact": self.indirect_impact,
            "total_impact": self.total_impact,
            "impact_level": self.impact_level,
            "test_files_affected": self.test_files_affected,
            "risk_assessment": self.risk_assessment,
        }


class ImpactAnalyzer:
    """
    代码变更影响分析器

    给定修改的文件列表，分析:
    - 直接受影响的文件 (直接依赖修改文件的)
    - 间接受影响的文件 (间接依赖链)
    - 受影响的测试文件
    - 整体风险等级
    """

    def __init__(self, graph: DependencyGraph):
        self.graph = graph

    def analyze(self, changed_files: List[str], max_depth: int = 3) -> ImpactResult:
        """
        分析变更影响

        Args:
            changed_files: 修改的文件路径列表
            max_depth: 最大影响深度

        Returns:
            ImpactResult
        """
        direct = set()
        indirect = set()

        for cf in changed_files:
            # 规范化路径
            cf_abs = os.path.abspath(cf)
            cf_rel = _safe_relpath(cf_abs, self.graph.project_root)

            # 尝试匹配图中的节点
            matched = self._find_matching_node(cf_abs, cf_rel)
            if not matched:
                continue

            # 反向依赖 (谁依赖了这个文件)
            direct_deps = self.graph.get_reverse_dependents(matched, max_depth=1)
            indirect_deps = self.graph.get_reverse_dependents(matched, max_depth=max_depth)

            direct.update(direct_deps)
            indirect.update(set(indirect_deps) - set(direct_deps))

        # 排除已修改的文件
        changed_set = set(os.path.abspath(f) for f in changed_files)
        direct -= changed_set
        indirect -= changed_set
        indirect -= direct

        # 测试文件
        test_files = [
            f for f in (direct | indirect)
            if 'test' in f.lower() or f.endswith('_test.py') or f.startswith('test_')
        ]

        total = len(direct) + len(indirect)
        level = self._assess_level(total, len(changed_files))
        risk = self._assess_risk(changed_files, direct, indirect)

        return ImpactResult(
            changed_files=changed_files,
            direct_impact=sorted(direct),
            indirect_impact=sorted(indirect),
            total_impact=total,
            impact_level=level,
            test_files_affected=sorted(test_files),
            risk_assessment=risk,
        )

    def _find_matching_node(self, abs_path: str, rel_path: str) -> Optional[str]:
        """查找匹配的文件节点"""
        if abs_path in self.graph.nodes:
            return abs_path
        # 尝试相对路径
        for node_path in self.graph.nodes:
            if node_path.endswith(rel_path) or rel_path.endswith(os.path.basename(node_path)):
                return node_path
        return None

    def _assess_level(self, total_impact: int, changed_count: int) -> str:
        """评估影响等级"""
        if total_impact == 0:
            return "low"
        elif total_impact <= 3:
            return "low"
        elif total_impact <= 10:
            return "medium"
        elif total_impact <= 25:
            return "high"
        else:
            return "critical"

    def _assess_risk(self, changed: List[str], direct: Set, indirect: Set) -> str:
        """风险评估描述"""
        risks = []

        # 核心文件检测
        core_keywords = ['agent_loop', 'session_state', 'cli', 'registry', 'manager']
        for cf in changed:
            basename = os.path.basename(cf).lower()
            if any(kw in basename for kw in core_keywords):
                risks.append(f"⚠️ 核心文件修改: {basename}")

        # 影响范围
        if len(direct) > 10:
            risks.append(f"⚠️ 大量直接影响: {len(direct)} 个文件")

        # 测试覆盖
        test_count = sum(1 for f in (direct | indirect) if 'test' in f.lower())
        if test_count > 0:
            risks.append(f"ℹ️ {test_count} 个测试文件可能需要更新")

        if not risks:
            return "低风险: 变更影响范围有限"
        return "; ".join(risks)

    def generate_report(self, changed_files: List[str]) -> str:
        """生成人类可读的影响分析报告"""
        result = self.analyze(changed_files)

        lines = [
            "=" * 60,
            "代码变更影响分析报告",
            "=" * 60,
            "",
            f"修改文件: {len(result.changed_files)} 个",
        ]
        for cf in result.changed_files:
            lines.append(f"  - {cf}")

        lines.extend([
            "",
            f"影响等级: {result.impact_level.upper()}",
            f"总影响: {result.total_impact} 个文件",
            "",
            f"直接影响 ({len(result.direct_impact)} 个):",
        ])
        for f in result.direct_impact[:15]:
            lines.append(f"  - {_safe_relpath(f, self.graph.project_root)}")
        if len(result.direct_impact) > 15:
            lines.append(f"  ... 还有 {len(result.direct_impact) - 15} 个")

        if result.indirect_impact:
            lines.extend([
                "",
                f"间接影响 ({len(result.indirect_impact)} 个):",
            ])
            for f in result.indirect_impact[:10]:
                lines.append(f"  - {_safe_relpath(f, self.graph.project_root)}")
            if len(result.indirect_impact) > 10:
                lines.append(f"  ... 还有 {len(result.indirect_impact) - 10} 个")

        if result.test_files_affected:
            lines.extend([
                "",
                f"受影响测试 ({len(result.test_files_affected)} 个):",
            ])
            for f in result.test_files_affected:
                lines.append(f"  - {_safe_relpath(f, self.graph.project_root)}")

        lines.extend([
            "",
            f"风险评估: {result.risk_assessment}",
        ])

        return "\n".join(lines)


# ── 统一入口 ───────────────────────────────────────────────


class CodeAnalyzer:
    """代码分析器统一入口"""

    def __init__(self, project_root: str = "."):
        self.project_root = project_root
        self.graph = DependencyGraph(project_root)
        self.analyzer: Optional[ImpactAnalyzer] = None

    def build_dependency_graph(self, scan_dirs: List[str] = None) -> Dict[str, DepNode]:
        """构建依赖图"""
        nodes = self.graph.build(scan_dirs)
        self.analyzer = ImpactAnalyzer(self.graph)
        return nodes

    def analyze_impact(self, changed_files: List[str]) -> Optional[Dict[str, Any]]:
        """分析变更影响"""
        if not self.analyzer:
            self.build_dependency_graph()
        result = self.analyzer.analyze(changed_files)
        return result.to_dict()

    def generate_impact_report(self, changed_files: List[str]) -> str:
        """生成影响报告"""
        if not self.analyzer:
            self.build_dependency_graph()
        return self.analyzer.generate_report(changed_files)

    def get_stats(self) -> Dict[str, Any]:
        return self.graph.get_stats()
