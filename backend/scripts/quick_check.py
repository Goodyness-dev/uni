import os
import re
import subprocess
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))


def check_tests() -> bool:
    print("Running pytest suite...")
    result = subprocess.run([sys.executable, "-m", "pytest", "tests"], cwd=str(backend_dir))
    return result.returncode == 0


def check_banned_imports() -> bool:
    print("Checking banned imports...")
    app_dir = backend_dir / "app"
    banned_llm_pattern = re.compile(r"^\s*(import\s+(openai|anthropic|google\.generativeai)|from\s+(openai|anthropic|google\.generativeai)\s+import)")
    banned_init_pattern = re.compile(r"neatlogs\.init\s*\(")

    passed = True

    for py_file in app_dir.rglob("*.py"):
        rel_path = py_file.relative_to(backend_dir).as_posix()
        with open(py_file, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                # Check direct LLM imports
                if banned_llm_pattern.search(line):
                    if rel_path != "app/llm.py":
                        print(f"ERROR: Banned LLM import in {rel_path}:{line_no}: {line.strip()}")
                        passed = False

                # Check neatlogs.init
                if banned_init_pattern.search(line):
                    if rel_path != "app/tracing.py":
                        print(f"ERROR: Banned neatlogs.init in {rel_path}:{line_no}: {line.strip()}")
                        passed = False

    return passed


def check_git_secrets() -> bool:
    print("Checking git status for untracked secrets...")
    repo_root = backend_dir.parent
    result = subprocess.run(["git", "status", "--porcelain"], cwd=str(repo_root), capture_output=True, text=True)
    if result.returncode == 0:
        for line in result.stdout.splitlines():
            # If any .env is staged (starts with A, M, etc.)
            if line.startswith(("A ", "M ", "R ", "C ")) and ".env" in line and not line.endswith(".example"):
                print(f"ERROR: .env file is staged for git commit: {line}")
                return False
    return True


def main() -> None:
    if not check_git_secrets():
        sys.exit(1)
    if not check_banned_imports():
        sys.exit(1)
    if not check_tests():
        sys.exit(1)
    print("\nALL QUICK CHECKS PASSED: OK")


if __name__ == "__main__":
    main()
