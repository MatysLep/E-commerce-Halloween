"""A frontend deployment must not use credentials from a different AWS account."""

import runpy
from pathlib import Path
from types import SimpleNamespace

import boto3
import pytest

deployment_session = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "scripts/deploy_frontend.py")
)["deployment_session"]


def test_frontend_uses_the_profile_from_terraform_outputs(monkeypatch):
    captured = {}
    session = SimpleNamespace(
        client=lambda service: SimpleNamespace(
            get_caller_identity=lambda: {"Account": "123456789012"}
        )
    )

    def create_session(**options):
        captured.update(options)
        return session

    monkeypatch.setattr(boto3, "Session", create_session)
    assert (
        deployment_session(
            {
                "aws_profile": "training",
                "aws_account_id": "123456789012",
            }
        )
        is session
    )
    assert captured == {"profile_name": "training", "region_name": "eu-west-3"}


def test_frontend_refuses_another_account_before_upload(monkeypatch):
    session = SimpleNamespace(
        client=lambda service: SimpleNamespace(
            get_caller_identity=lambda: {"Account": "999999999999"}
        )
    )
    monkeypatch.setattr(boto3, "Session", lambda **_: session)
    with pytest.raises(RuntimeError, match="AWS account mismatch"):
        deployment_session({"aws_profile": "training", "aws_account_id": "123456789012"})
