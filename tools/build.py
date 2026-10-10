"""Build with GCC or Clang without CMake or third-party Python packages."""
import argparse
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test", action="store_true", help="Run the regression suite after building")
    parser.add_argument("--sanitize", action="store_true", help="Enable ASan and UBSan (supported compilers only)")
    args = parser.parse_args()
    compiler = shlex.split(os.environ.get("CXX", "g++"), posix=os.name != "nt")
    if not compiler or not shutil.which(compiler[0]):
        parser.error("C++ compiler not found. Install GCC/Clang or use the CMake build with Visual Studio.")
    destination = ROOT / "build"
    destination.mkdir(exist_ok=True)
    binary = destination / ("market-ledger.exe" if os.name == "nt" else "market-ledger")
    flags = ["-std=c++17", "-Wall", "-Wextra", "-Wpedantic", "-Werror", "-O2"]
    if args.sanitize:
        flags += ["-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
    subprocess.run(compiler + flags + ["-I", str(ROOT / "include"), str(ROOT / "src/engine.cpp"),
                   str(ROOT / "src/main.cpp"), "-o", str(binary)], check=True, cwd=ROOT)
    print(f"Built {binary}", flush=True)
    if args.test:
        subprocess.run([sys.executable, str(ROOT / "tests/test_cli.py"), "--binary", str(binary)],
                       check=True, cwd=ROOT)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        sys.exit(error.returncode)
