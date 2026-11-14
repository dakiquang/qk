import json
from pathlib import Path

import boto3
import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def isolated_aws_env(monkeypatch, tmp_path):
    """Keep tests away from real AWS config, credentials and region settings."""
    missing = tmp_path / "does-not-exist"
    monkeypatch.setenv("AWS_CONFIG_FILE", str(missing))
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(missing))
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    for name in (
        "AWS_SESSION_TOKEN",
        "AWS_SECURITY_TOKEN",
        "AWS_PROFILE",
        "AWS_DEFAULT_PROFILE",
        "AWS_DEFAULT_REGION",
        "AWS_REGION",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def load_fixture():
    def load(name):
        return json.loads((FIXTURES / name).read_text())

    return load


@pytest.fixture
def wafv2_client():
    return boto3.session.Session().client(
        "wafv2",
        region_name="us-east-1",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
    )
