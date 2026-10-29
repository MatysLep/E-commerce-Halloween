"""The system AWS CLI must not load the application's Python dependencies."""

import os
import subprocess
from pathlib import Path


def test_migration_cli_uses_its_own_python_environment(tmp_path):
    template = (
        Path(__file__).resolve().parents[1] / "infrastructure/bootstrap.sh.tftpl"
    ).read_text()
    migration = template.split("<<'MIGRATE'\n", 1)[1].split("\nMIGRATE", 1)[0]
    migration = migration.replace("${migration_function}", "test-migration")
    cli = tmp_path / "aws"
    cli.write_text(
        "#!/bin/bash\n"
        'test "${PYTHONPATH+x}" != x || exit 2\n'
        'test "$1 $2" = "lambda invoke" || exit 3\n'
        'test "$AWS_REGION" = "eu-west-3" || exit 4\n'
        "echo None\n"
    )
    cli.chmod(0o755)
    result = subprocess.run(
        ["bash", "-c", migration],
        env={
            **os.environ,
            "PATH": f"{tmp_path}:{os.environ['PATH']}",
            "PYTHONPATH": "/application/python312-dependencies",
            "AWS_REGION": "eu-west-3",
        },
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0, result.stderr
