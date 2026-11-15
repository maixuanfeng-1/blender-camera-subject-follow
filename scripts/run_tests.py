"""Run each integration test in a separate factory-startup Blender process."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TESTS = ("verify_addon.py", "verify_motion.py", "verify_shots.py", "verify_picker.py")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", default="blender", help="Path to the Blender executable")
    args = parser.parse_args()
    for name in TESTS:
        print(f"\nRunning {name}", flush=True)
        result = subprocess.run([
            args.blender, "--background", "--factory-startup", "--python-exit-code", "1",
            "--python", str(ROOT / "tests" / name),
        ], cwd=ROOT)
        if result.returncode:
            return result.returncode
    print("\nAll four integration suites passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
