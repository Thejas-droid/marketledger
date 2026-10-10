"""Create a reproducible GitHub source ZIP using an explicit publication allowlist."""
import hashlib
from pathlib import Path
import re
import sys
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
FILES = ("README.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "CHANGELOG.md", "CONTRIBUTING.md",
         "SECURITY.md", "CMakeLists.txt", ".gitignore", ".gitattributes", ".github/workflows/ci.yml")
DIRECTORIES = ("include", "src", "tests", "tools", "docs", "examples")
TOKEN = re.compile(rb"(?:AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)")


def collect_files(root):
    paths = [root / name for name in FILES]
    for directory in DIRECTORIES:
        paths.extend(p for p in (root / directory).rglob("*") if p.is_file()
                     and "__pycache__" not in p.parts and p.suffix not in (".pyc", ".pyo"))
    for path in paths:
        if not path.is_file():
            raise ValueError(f"Missing release file: {path.relative_to(root)}")
        if path.is_symlink() or root.resolve() not in path.resolve().parents:
            raise ValueError(f"Release file escapes project: {path}")
        if path.suffix.lower() in (".exe", ".zip", ".gz", ".pdf", ".o", ".obj"):
            raise ValueError(f"Unexpected release artifact: {path}")
        if TOKEN.search(path.read_bytes()):
            raise ValueError(f"Potential credential in release file: {path.relative_to(root)}")
    return sorted(paths, key=lambda p: p.relative_to(root).as_posix())


def main():
    paths = collect_files(ROOT)
    output = ROOT / "release"
    output.mkdir(exist_ok=True)
    archive = output / "market-ledger-1.0.0-source.zip"
    manifest = []
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as package:
        for path in paths:
            relative = path.relative_to(ROOT).as_posix()
            data = path.read_bytes()
            info = ZipInfo("MarketLedger/" + relative, date_time=(2026, 10, 10, 0, 0, 0))
            info.create_system = 3
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            package.writestr(info, data)
            manifest.append(f"{hashlib.sha256(data).hexdigest()}  {relative}")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / "SHA256SUMS.txt").write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    (output / "MANIFEST.sha256").write_text("\n".join(manifest) + "\n", encoding="utf-8")
    print(f"Exported {len(paths)} source files: {archive}")
    print("Only project source files are included; generated files and Git history are excluded.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
