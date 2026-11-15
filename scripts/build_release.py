"""Build an installable, reproducible Blender legacy add-on ZIP. Python stdlib only."""
import ast
import hashlib
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = (ROOT / "camera_subject_follow.py").read_bytes()
    tree = ast.parse(source.decode("utf-8"))
    metadata = next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "bl_info" for target in node.targets)
    )
    version = ".".join(map(str, metadata["version"]))
    output = ROOT / "dist"
    output.mkdir(exist_ok=True)
    archive = output / f"camera_subject_follow-v{version}.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for name, data in (("camera_subject_follow.py", source), ("LICENSE", (ROOT / "LICENSE").read_bytes())):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.testzip() is None
        assert bundle.read("camera_subject_follow.py") == source
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / "SHA256SUMS.txt").write_text(f"{checksum}  {archive.name}\n", encoding="utf-8")
    print(archive)
    print(f"SHA256 {checksum}")


if __name__ == "__main__":
    main()
