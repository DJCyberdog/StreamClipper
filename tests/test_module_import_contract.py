"""Static guard against mixed-source import errors (e.g. missing apply_segment_changes).

This check intentionally does not need PySide6/CUDA; native Windows GUI
smoke and real-model checks remain separate M10.5 release gates.
"""
from __future__ import annotations

import ast
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "streamclipper"


def _symbols(tree: ast.Module) -> set[str]:
    found: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            found.add(node.name)
        elif isinstance(node, (ast.ImportFrom, ast.Import)):
            for name in node.names:
                found.add(name.asname or name.name.split(".")[0])
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                found.update(n.id for n in ast.walk(target) if isinstance(n, ast.Name))
    return found


def test_internal_relative_imports_have_committed_symbols():
    for path in sorted(PACKAGE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.level != 1 or not node.module:
                continue
            module_path = PACKAGE / (node.module + ".py")
            assert module_path.is_file(), f"{path.name}: fehlendes Modul {node.module}"
            definitions = _symbols(ast.parse(module_path.read_text(encoding="utf-8")))
            for imported in node.names:
                if imported.name != "*":
                    assert imported.name in definitions, (
                        f"{path.name}: .{node.module}.{imported.name} fehlt in {module_path.name}"
                    )
