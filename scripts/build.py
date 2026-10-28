"""Build Linux x86_64 artifacts for Amazon Linux 2023 and Python 3.12 Lambda."""

import gzip
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"


def main():
    BUILD.mkdir(exist_ok=True)
    dependencies = BUILD / "dependencies"
    if dependencies.exists():
        shutil.rmtree(dependencies)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--requirement",
            str(ROOT / "requirements.txt"),
            "--target",
            str(dependencies),
            "--only-binary=:all:",
            "--platform",
            "manylinux2014_x86_64",
            "--platform",
            "manylinux_2_28_x86_64",
            "--platform",
            "manylinux_2_34_x86_64",
            "--implementation",
            "cp",
            "--python-version",
            "3.12",
            "--abi",
            "cp312",
            "--no-compile",
        ],
        check=True,
    )
    certificate = BUILD / "global-bundle.pem"
    with urllib.request.urlopen(
        "https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem",
        timeout=30,
    ) as response:
        certificate.write_bytes(response.read())
    files = []
    for directory in [ROOT / "backend", dependencies]:
        for path in sorted(directory.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                relative = path.relative_to(directory)
                files.append((path, f"{directory.name}/{relative}"))
    files.append((certificate, certificate.name))
    with (BUILD / "release.tar.gz").open("wb") as output:
        with gzip.GzipFile(fileobj=output, mode="wb", filename="", mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as archive:
                for path, name in files:
                    info = archive.gettarinfo(str(path), arcname=name)
                    info.mtime = 0
                    info.uid = info.gid = 0
                    info.uname = info.gname = ""
                    with path.open("rb") as source:
                        archive.addfile(info, source)
    with zipfile.ZipFile(BUILD / "lambda.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, name in files:
            if name.startswith(("backend/shop/", "backend/migrations/")):
                name = name.removeprefix("backend/")
            elif name.startswith("dependencies/"):
                name = name.removeprefix("dependencies/")
            elif name != certificate.name:
                continue
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
    print("Created build/release.tar.gz and build/lambda.zip (Linux x86_64).")


if __name__ == "__main__":
    main()
