#!/usr/bin/env python3
"""
CareerAgent Shared Code Detector
---------------------------------
Run from repo root:  python check_shared_code.py <dir1> <dir2>
Example:             python check_shared_code.py agents/interview_agent agents/opportunity_agent

Scans both agent directories and reports:
  1. Shared third-party imports (candidates for unified requirements.txt)
  2. Shared env variable references (candidates for a common config loader)
  3. Duplicate function/class names (candidates for a shared module)
  4. Structurally similar code blocks (near-duplicate logic)
"""

import ast
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from difflib import SequenceMatcher

# ── Helpers ──────────────────────────────────────────────────────────────────

STDLIB_TOP_LEVEL = {
    "os", "sys", "re", "json", "math", "time", "datetime", "pathlib",
    "typing", "collections", "itertools", "functools", "abc", "enum",
    "dataclasses", "logging", "argparse", "asyncio", "copy", "hashlib",
    "io", "traceback", "unittest", "uuid", "warnings", "textwrap",
    "subprocess", "shutil", "glob", "tempfile", "socket", "http",
    "urllib", "csv", "pickle", "struct", "contextlib", "inspect",
    "operator", "string", "pprint", "secrets", "hmac", "base64",
}


_EXCLUDE_DIRS = {".venv", "venv", "__pycache__", ".git", "node_modules", "dist", "build", ".eggs", "*.egg-info"}

def collect_py_files(directory: str) -> list[Path]:
    result = []
    for path in Path(directory).rglob("*.py"):
        if not any(part in _EXCLUDE_DIRS or part.endswith(".egg-info") for part in path.parts):
            result.append(path)
    return sorted(result)


def get_local_packages(directory: str) -> set[str]:
    """Return names of local Python packages — subdirs with __init__.py OR any .py files."""
    local = set()
    for path in Path(directory).iterdir():
        if path.name.startswith(".") or path.name in _EXCLUDE_DIRS:
            continue
        if path.is_dir():
            has_init = (path / "__init__.py").exists()
            has_py = any(path.glob("*.py"))
            if has_init or has_py:
                local.add(path.name)
    return local


def extract_imports(filepath: Path) -> set[str]:
    """Return set of top-level package names imported in a file."""
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return set()

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    return imports


def extract_env_vars(filepath: Path) -> set[str]:
    """Return env variable names referenced via os.environ or os.getenv."""
    try:
        text = filepath.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return set()
    patterns = [
        r'os\.environ\.get\(\s*["\'](\w+)["\']',
        r'os\.environ\[\s*["\'](\w+)["\']',
        r'os\.getenv\(\s*["\'](\w+)["\']',
        r'environ\.get\(\s*["\'](\w+)["\']',
        r'environ\[\s*["\'](\w+)["\']',
    ]
    env_vars = set()
    for pat in patterns:
        env_vars.update(re.findall(pat, text))
    return env_vars


def extract_definitions(filepath: Path) -> dict[str, list[str]]:
    """Return {name: [source_lines]} for every function and class definition."""
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError):
        return {}

    lines = source.splitlines()
    defs = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start = node.lineno - 1
            end = node.end_lineno if hasattr(node, "end_lineno") and node.end_lineno else start + 1
            body = lines[start:end]
            defs[node.name] = body
    return defs


def similarity(a: list[str], b: list[str]) -> float:
    return SequenceMatcher(None, "\n".join(a), "\n".join(b)).ratio()


# ── Analysis ─────────────────────────────────────────────────────────────────

def analyze(dir1: str, dir2: str):
    label1 = Path(dir1).name
    label2 = Path(dir2).name
    files1 = collect_py_files(dir1)
    files2 = collect_py_files(dir2)
    local1 = get_local_packages(dir1)
    local2 = get_local_packages(dir2)

    if not files1:
        print(f"⚠  No .py files found in {dir1}")
    if not files2:
        print(f"⚠  No .py files found in {dir2}")
    if not files1 or not files2:
        sys.exit(1)

    print(f"\n{'='*70}")
    print(f"  CareerAgent Shared Code Report")
    print(f"  Comparing: {label1} ({len(files1)} files) vs {label2} ({len(files2)} files)")
    print(f"{'='*70}\n")

    # ── 1. Shared third-party imports ────────────────────────────────────
    imports1: dict[str, list[str]] = defaultdict(list)
    imports2: dict[str, list[str]] = defaultdict(list)

    all_local = local1 | local2
    skip = STDLIB_TOP_LEVEL | all_local

    for f in files1:
        for imp in extract_imports(f):
            if imp not in skip and not imp.startswith("_"):
                imports1[imp].append(str(f.relative_to(dir1)))
    for f in files2:
        for imp in extract_imports(f):
            if imp not in skip and not imp.startswith("_"):
                imports2[imp].append(str(f.relative_to(dir2)))

    shared_imports = set(imports1.keys()) & set(imports2.keys())
    only1 = set(imports1.keys()) - set(imports2.keys())
    only2 = set(imports2.keys()) - set(imports1.keys())

    # Report local package name clashes (important for mono-repo restructuring)
    clashing_locals = local1 & local2

    print("1) SHARED THIRD-PARTY IMPORTS")
    print("   (These should appear in your unified requirements.txt)\n")
    if shared_imports:
        for pkg in sorted(shared_imports):
            print(f"   ✓ {pkg}")
            print(f"     {label1}: {', '.join(imports1[pkg])}")
            print(f"     {label2}: {', '.join(imports2[pkg])}")
    else:
        print("   None found — the two agents have fully independent deps.")

    print(f"\n   Only in {label1}: {', '.join(sorted(only1)) or '(none)'}")
    print(f"   Only in {label2}: {', '.join(sorted(only2)) or '(none)'}")

    if clashing_locals:
        print(f"\n   ⚠  LOCAL PACKAGE NAME CLASHES (rename before merging into mono-repo):")
        for name in sorted(clashing_locals):
            print(f"     '{name}/' exists in both agents — will conflict under a shared PYTHONPATH")

    # ── 2. Shared env variable references ────────────────────────────────
    env1: dict[str, list[str]] = defaultdict(list)
    env2: dict[str, list[str]] = defaultdict(list)

    for f in files1:
        for var in extract_env_vars(f):
            env1[var].append(str(f.relative_to(dir1)))
    for f in files2:
        for var in extract_env_vars(f):
            env2[var].append(str(f.relative_to(dir2)))

    shared_env = set(env1.keys()) & set(env2.keys())

    print(f"\n\n2) SHARED ENV VARIABLES")
    print("   (These confirm a single .env file is the right call)\n")
    if shared_env:
        for var in sorted(shared_env):
            print(f"   ✓ {var}")
            print(f"     {label1}: {', '.join(env1[var])}")
            print(f"     {label2}: {', '.join(env2[var])}")
        print(f"\n   → Consider a shared config loader: common/config.py")
    else:
        print("   None found — each agent uses its own set of env vars.")

    all_env = set(env1.keys()) | set(env2.keys())
    if all_env:
        print(f"\n   All env vars across both agents (for your .env template):")
        for var in sorted(all_env):
            source = []
            if var in env1:
                source.append(label1)
            if var in env2:
                source.append(label2)
            print(f"     {var}  ← {', '.join(source)}")

    # ── 3. Duplicate function/class names ────────────────────────────────
    defs1: dict[str, dict] = {}  # name -> {file, lines}
    defs2: dict[str, dict] = {}

    for f in files1:
        for name, body in extract_definitions(f).items():
            defs1[name] = {"file": str(f.relative_to(dir1)), "body": body}
    for f in files2:
        for name, body in extract_definitions(f).items():
            defs2[name] = {"file": str(f.relative_to(dir2)), "body": body}

    shared_names = set(defs1.keys()) & set(defs2.keys())
    # Filter out common dunder/trivial names
    shared_names -= {"__init__", "__repr__", "__str__", "main", "setup", "run"}

    print(f"\n\n3) DUPLICATE FUNCTION / CLASS NAMES")
    print("   (Same name in both agents — possible extraction candidates)\n")
    if shared_names:
        for name in sorted(shared_names):
            sim = similarity(defs1[name]["body"], defs2[name]["body"])
            flag = "🔴 HIGH" if sim > 0.7 else "🟡 MEDIUM" if sim > 0.4 else "🟢 LOW"
            print(f"   {flag} similarity ({sim:.0%}): {name}()")
            print(f"     {label1}: {defs1[name]['file']}")
            print(f"     {label2}: {defs2[name]['file']}")
            if sim > 0.7:
                print(f"     → Strong candidate for shared/common module")
    else:
        print("   None found — no overlapping function or class names.")

    # ── 4. Cross-file near-duplicates (expensive, top 5 only) ────────────
    print(f"\n\n4) NEAR-DUPLICATE CODE BLOCKS (top matches, different names)")
    print("   (>60% structurally similar — candidates for a shared utility)\n")

    candidates = []
    all_defs1 = [(n, d) for n, d in defs1.items() if len(d["body"]) >= 5]
    all_defs2 = [(n, d) for n, d in defs2.items() if len(d["body"]) >= 5]

    for name1, d1 in all_defs1:
        for name2, d2 in all_defs2:
            if name1 == name2:
                continue  # already reported in section 3
            sim = similarity(d1["body"], d2["body"])
            if sim > 0.6:
                candidates.append((sim, name1, d1["file"], name2, d2["file"]))

    candidates.sort(reverse=True)
    shown = candidates[:5]
    if shown:
        for sim, n1, f1, n2, f2 in shown:
            flag = "🔴 HIGH" if sim > 0.8 else "🟡 MED"
            print(f"   {flag} {sim:.0%} similar: {n1}() [{label1}/{f1}]")
            print(f"                      ↔ {n2}() [{label2}/{f2}]")
        if len(candidates) > 5:
            print(f"\n   ... and {len(candidates)-5} more (showing top 5 only)")
    else:
        print("   None found — no structurally similar code across agents.")

    # ── Summary ──────────────────────────────────────────────────────────
    issues = len(shared_imports) + len(shared_env) + len(shared_names) + len(candidates)
    print(f"\n{'='*70}")
    if issues == 0:
        print("  ✅ Clean split — no shared code to extract.")
        print("  Your agents are already independent. Proceed with mono-repo as-is.")
    else:
        print(f"  Found {issues} overlap(s) to review.")
        print("")
        print("  Suggested shared/ module candidates:")
        if shared_env:
            print("    shared/config.py  — unified env-var loader (GROQ_API_KEY, etc.)")
        if shared_imports:
            print("    requirements.txt  — merge the two into one (see section 1)")
        if shared_names or candidates:
            print("    shared/utils.py   — any 🔴 HIGH similarity functions above")
        print("")
        print("  Items marked 🔴 should be extracted to a shared/ module.")
        print("  Items marked 🟡 are worth a quick look.")
        print("  Items marked 🟢 are likely coincidental — skip unless trivial to unify.")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python check_shared_code.py <agent_dir_1> <agent_dir_2>")
        print("Example: python check_shared_code.py agents/interview_agent agents/opportunity_agent")
        sys.exit(1)

    d1, d2 = sys.argv[1], sys.argv[2]
    if not os.path.isdir(d1):
        print(f"Error: {d1} is not a directory")
        sys.exit(1)
    if not os.path.isdir(d2):
        print(f"Error: {d2} is not a directory")
        sys.exit(1)

    analyze(d1, d2)
