import json
from pathlib import Path

import pytest
from botocore.exceptions import NoCredentialsError
from botocore.stub import Stubber

from waf_upgrade_check import __version__, aws
from waf_upgrade_check.cli import main

GROUP = "AWSManagedRulesCommonRuleSet"


def test_version_flag_prints_version(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0
    assert __version__ in capsys.readouterr().out


@pytest.fixture
def stub(wafv2_client, monkeypatch):
    monkeypatch.setattr(aws, "make_client", lambda scope, region, profile: wafv2_client)
    with Stubber(wafv2_client) as stubber:
        yield stubber
        stubber.assert_no_pending_responses()


@pytest.fixture
def versions_stub(stub, load_fixture):
    stub.add_response(
        "list_available_managed_rule_group_versions", load_fixture("list_versions_page1.json")
    )
    stub.add_response(
        "list_available_managed_rule_group_versions", load_fixture("list_versions_page2.json")
    )
    return stub


@pytest.fixture
def diff_stub(stub, load_fixture):
    stub.add_response("describe_managed_rule_group", load_fixture("describe_v1_0.json"))
    stub.add_response("describe_managed_rule_group", load_fixture("describe_v1_1.json"))
    return stub


def test_versions_text_marks_default(versions_stub, capsys):
    assert main(["versions", GROUP]) == 0

    assert capsys.readouterr().out.splitlines() == [
        "Version_1.10",
        "Version_1.1 (default)",
        "Version_1.0",
        "Default version: Version_1.1",
    ]


def test_versions_json(versions_stub, capsys):
    assert main(["versions", GROUP, "--format", "json"]) == 0

    assert json.loads(capsys.readouterr().out) == {
        "rule_group": GROUP,
        "scope": "REGIONAL",
        "default_version": "Version_1.1",
        "versions": ["Version_1.10", "Version_1.1", "Version_1.0"],
    }


def test_diff_text(diff_stub, capsys):
    assert main(["diff", GROUP, "Version_1.0", "Version_1.1"]) == 0

    out = capsys.readouterr().out
    assert out.startswith(f"{GROUP} Version_1.0 -> Version_1.1 (REGIONAL)\n")
    assert "Capacity: 700 -> 750 (+50)\n" in out
    assert "Rules added (1):\n  CrossSiteScripting_COOKIE\n" in out
    assert "Rules removed (1):\n  LegacyRule_QUERYARGUMENTS\n" in out
    assert "Action changed (1):\n  SizeRestrictions_BODY: Count -> Block\n" in out
    assert (
        "Available labels added (1):\n"
        "  awswaf:managed:aws:core-rule-set:CrossSiteScripting_Cookie\n" in out
    )
    assert (
        "Available labels removed (1):\n"
        "  awswaf:managed:aws:core-rule-set:LegacyRule_QueryArguments\n" in out
    )
    assert (
        "Consumed labels added (1):\n  awswaf:managed:aws:bot-control:signal:automated_browser\n"
        in out
    )
    assert out.endswith("Consumed labels removed (0):\n  none\n")


def test_diff_json(diff_stub, capsys):
    assert main(["diff", GROUP, "Version_1.0", "Version_1.1", "--format", "json"]) == 0

    assert json.loads(capsys.readouterr().out) == {
        "rule_group": GROUP,
        "scope": "REGIONAL",
        "from": "Version_1.0",
        "to": "Version_1.1",
        "capacity": {"old": 700, "new": 750},
        "rules": {
            "added": ["CrossSiteScripting_COOKIE"],
            "removed": ["LegacyRule_QUERYARGUMENTS"],
            "action_changed": [{"name": "SizeRestrictions_BODY", "old": "Count", "new": "Block"}],
        },
        "available_labels": {
            "added": ["awswaf:managed:aws:core-rule-set:CrossSiteScripting_Cookie"],
            "removed": ["awswaf:managed:aws:core-rule-set:LegacyRule_QueryArguments"],
        },
        "consumed_labels": {
            "added": ["awswaf:managed:aws:bot-control:signal:automated_browser"],
            "removed": [],
        },
    }


def test_api_error_exits_2_without_traceback(stub, capsys):
    stub.add_client_error("describe_managed_rule_group", "WAFNonexistentItemException")

    assert main(["diff", GROUP, "Version_9.9", "Version_1.1"]) == 2

    err = capsys.readouterr().err
    assert err.startswith("waf-upgrade-check: error: ")
    assert "WAFNonexistentItemException" in err
    assert "Traceback" not in err


def test_missing_credentials_exits_2(monkeypatch, capsys):
    def no_credentials(scope, region, profile):
        raise NoCredentialsError()

    monkeypatch.setattr(aws, "make_client", no_credentials)

    assert main(["versions", GROUP]) == 2

    assert "waf-upgrade-check: error: Unable to locate credentials" in capsys.readouterr().err


def test_cloudfront_with_other_region_exits_2(monkeypatch, capsys):
    def unexpected(scope, region, profile):
        raise AssertionError("client must not be created")

    monkeypatch.setattr(aws, "make_client", unexpected)

    assert main(["versions", GROUP, "--scope", "CLOUDFRONT", "--region", "eu-west-1"]) == 2

    assert "--scope CLOUDFRONT requires region us-east-1" in capsys.readouterr().err


@pytest.mark.parametrize(
    "argv",
    [
        ["diff", GROUP, "Version_1.0"],
        ["versions", GROUP, "--scope", "GLOBAL"],
        ["check"],
        ["check", "--web-acl-file", "acl.json", "--web-acl", "example-web-acl"],
    ],
)
def test_usage_errors_exit_2(argv):
    with pytest.raises(SystemExit) as exit_info:
        main(argv)
    assert exit_info.value.code == 2


WEB_ACL_ID = "a1b2c3d4-5678-90ab-cdef-EXAMPLE11111"


def _add_list_responses(stub, load_fixture):
    base = {"VendorName": "AWS", "Name": GROUP, "Scope": "REGIONAL"}
    stub.add_response(
        "list_available_managed_rule_group_versions",
        load_fixture("list_versions_page1.json"),
        base,
    )
    stub.add_response(
        "list_available_managed_rule_group_versions",
        load_fixture("list_versions_page2.json"),
        {**base, "NextMarker": "page-2-marker"},
    )


def _add_describe(stub, load_fixture, fixture, version):
    stub.add_response(
        "describe_managed_rule_group",
        load_fixture(fixture),
        {"VendorName": "AWS", "Name": GROUP, "Scope": "REGIONAL", "VersionName": version},
    )


@pytest.fixture
def upgrade_stub(stub, load_fixture):
    _add_list_responses(stub, load_fixture)
    _add_describe(stub, load_fixture, "describe_v1_0.json", "Version_1.0")
    _add_describe(stub, load_fixture, "describe_v1_1.json", "Version_1.1")
    return stub


def _fixture_path(name):
    return str(Path(__file__).parent / "fixtures" / name)


def test_check_file_reports_findings_and_exits_1(upgrade_stub, capsys):
    argv = ["check", "--web-acl-file", _fixture_path("web_acl_upgrade.json")]

    assert main(argv) == 1

    assert capsys.readouterr().out.splitlines() == [
        f"ERROR  {GROUP}  label-no-longer-emitted  rule BlockLegacyLabel matches LABEL "
        "awswaf:managed:aws:core-rule-set:LegacyRule_QueryArguments, not emitted by Version_1.1",
        f"ERROR  {GROUP}  override-missing-rule  RuleActionOverrides entry "
        "LegacyRule_QUERYARGUMENTS in rule AWS-CRS is not a rule in Version_1.1",
        f"WARNING  {GROUP}  capacity-increase  capacity 700 -> 750 WCU (+50); web ACL capacity 900",
        f"INFO  {GROUP}  behind-default  pinned version Version_1.0 differs from default "
        "Version_1.1",
        f"INFO  {GROUP}  rules-changed  Version_1.0 -> Version_1.1: 1 added, 1 removed, "
        "1 action changed",
        "Summary: 2 error(s), 1 warning(s), 2 info",
    ]


def test_check_clean_file_describes_once_and_exits_0(stub, load_fixture, capsys):
    _add_list_responses(stub, load_fixture)
    _add_describe(stub, load_fixture, "describe_v1_1.json", "Version_1.1")

    assert main(["check", "--web-acl-file", _fixture_path("web_acl_clean.json")]) == 0

    assert capsys.readouterr().out == "Summary: 0 error(s), 0 warning(s), 0 info\n"


KBI = "AWSManagedRulesKnownBadInputsRuleSet"
WINDOWS = "AWSManagedRulesWindowsRuleSet"


def _add_real_list(stub, load_fixture, group, fixture):
    listing = load_fixture(f"aws/{fixture}")
    del listing["NextMarker"]
    stub.add_response(
        "list_available_managed_rule_group_versions",
        listing,
        {"VendorName": "AWS", "Name": group, "Scope": "REGIONAL"},
    )


def _managed_rule(name, priority, group, version=None, overrides=()):
    statement = {"VendorName": "AWS", "Name": group}
    if version is not None:
        statement["Version"] = version
    if overrides:
        statement["RuleActionOverrides"] = [
            {"Name": override, "ActionToUse": {"Count": {}}} for override in overrides
        ]
    return {
        "Name": name,
        "Priority": priority,
        "Statement": {"ManagedRuleGroupStatement": statement},
    }


def test_check_undescribable_default_warns_and_checks_other_groups(
    stub, load_fixture, tmp_path, capsys
):
    web_acl = {
        "WebACL": {
            "Rules": [
                _managed_rule("AWS-Windows", 0, WINDOWS),
                _managed_rule(
                    "AWS-KBI",
                    1,
                    KBI,
                    version="Version_1.0",
                    overrides=["BadAuthToken_COOKIE_AUTHORIZATION"],
                ),
            ]
        }
    }
    path = tmp_path / "web-acl.json"
    path.write_text(json.dumps(web_acl))
    _add_real_list(stub, load_fixture, WINDOWS, "windows_list_rc_default.json")
    _add_real_list(stub, load_fixture, KBI, "known_bad_inputs_list.json")
    for version, fixture in (
        ("Version_1.0", "known_bad_inputs_v1_0.json"),
        ("Version_1.26", "known_bad_inputs_v1_26.json"),
    ):
        stub.add_response(
            "describe_managed_rule_group",
            load_fixture(f"aws/{fixture}"),
            {"VendorName": "AWS", "Name": KBI, "Scope": "REGIONAL", "VersionName": version},
        )

    assert main(["check", "--web-acl-file", str(path)]) == 1

    assert capsys.readouterr().out.splitlines() == [
        f"ERROR  {KBI}  override-missing-rule  RuleActionOverrides entry "
        "BadAuthToken_COOKIE_AUTHORIZATION in rule AWS-KBI is not a rule in Version_1.26",
        f"WARNING  {WINDOWS}  default-not-describable  default version Version_2.4_PLUS_RC_COUNT "
        "cannot be described; comparisons that need it are skipped",
        f"INFO  {KBI}  behind-default  pinned version Version_1.0 differs from default "
        "Version_1.26",
        f"INFO  {KBI}  rules-changed  Version_1.0 -> Version_1.26: 9 added, 1 removed, "
        "0 action changed",
        "Summary: 1 error(s), 1 warning(s), 2 info",
    ]


def test_check_default_describe_nonexistent_warns(stub, load_fixture, capsys):
    _add_list_responses(stub, load_fixture)
    stub.add_client_error("describe_managed_rule_group", "WAFNonexistentItemException")

    assert main(["check", "--web-acl-file", _fixture_path("web_acl_clean.json")]) == 0

    assert capsys.readouterr().out.splitlines() == [
        f"WARNING  {GROUP}  default-not-describable  default version Version_1.1 "
        "cannot be described; comparisons that need it are skipped",
        "Summary: 0 error(s), 1 warning(s), 0 info",
    ]


def test_check_default_describe_other_error_exits_2(stub, load_fixture, capsys):
    _add_list_responses(stub, load_fixture)
    stub.add_client_error("describe_managed_rule_group", "WAFAccessDeniedException")

    assert main(["check", "--web-acl-file", _fixture_path("web_acl_clean.json")]) == 2

    assert "WAFAccessDeniedException" in capsys.readouterr().err


def test_check_api_json(stub, load_fixture, capsys):
    stub.add_response(
        "get_web_acl",
        load_fixture("web_acl_upgrade.json"),
        {"Name": "example-web-acl", "Scope": "REGIONAL", "Id": WEB_ACL_ID},
    )
    _add_list_responses(stub, load_fixture)
    _add_describe(stub, load_fixture, "describe_v1_0.json", "Version_1.0")
    _add_describe(stub, load_fixture, "describe_v1_1.json", "Version_1.1")

    argv = ["check", "--web-acl", "example-web-acl", "--id", WEB_ACL_ID, "--format", "json"]
    assert main(argv) == 1

    findings = json.loads(capsys.readouterr().out)
    assert [finding["code"] for finding in findings] == [
        "label-no-longer-emitted",
        "override-missing-rule",
        "capacity-increase",
        "behind-default",
        "rules-changed",
    ]
    assert findings[0] == {
        "code": "label-no-longer-emitted",
        "level": "error",
        "rule_group": GROUP,
        "message": "rule BlockLegacyLabel matches LABEL "
        "awswaf:managed:aws:core-rule-set:LegacyRule_QueryArguments, not emitted by Version_1.1",
        "details": {
            "rule": "BlockLegacyLabel",
            "managed_rule": "AWS-CRS",
            "scope": "LABEL",
            "key": "awswaf:managed:aws:core-rule-set:LegacyRule_QueryArguments",
            "in_use_version": "Version_1.0",
            "target_version": "Version_1.1",
        },
    }


def test_check_get_web_acl_error_exits_2(stub, capsys):
    stub.add_client_error("get_web_acl", "WAFNonexistentItemException")

    assert main(["check", "--web-acl", "example-web-acl", "--id", WEB_ACL_ID]) == 2

    err = capsys.readouterr().err
    assert err.startswith("waf-upgrade-check: error: ")
    assert "WAFNonexistentItemException" in err
    assert "Traceback" not in err


@pytest.fixture
def no_client(monkeypatch):
    def unexpected(scope, region, profile):
        raise AssertionError("client must not be created")

    monkeypatch.setattr(aws, "make_client", unexpected)


@pytest.mark.parametrize("content", [None, "not json", '{"Rules": []}'])
def test_check_unreadable_file_exits_2(no_client, tmp_path, capsys, content):
    path = tmp_path / "web-acl.json"
    if content is not None:
        path.write_text(content)

    assert main(["check", "--web-acl-file", str(path)]) == 2

    err = capsys.readouterr().err
    assert err.startswith("waf-upgrade-check: error: ")
    assert str(path) in err


def test_check_unavailable_explicit_target_exits_2(stub, load_fixture, capsys):
    _add_list_responses(stub, load_fixture)
    argv = ["check", "--web-acl-file", _fixture_path("web_acl_upgrade.json")]

    assert main([*argv, "--target", "Version_9.9"]) == 2

    err = capsys.readouterr().err
    assert err == (
        f"waf-upgrade-check: error: target version Version_9.9 is not available for {GROUP}; "
        "available: Version_1.10, Version_1.1, Version_1.0\n"
    )


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["check", "--web-acl", "example-web-acl"], "--web-acl requires --id"),
        (
            ["check", "--web-acl-file", "acl.json", "--id", WEB_ACL_ID],
            "--id cannot be used with --web-acl-file",
        ),
    ],
)
def test_check_option_errors_exit_2(no_client, capsys, argv, message):
    assert main(argv) == 2

    assert capsys.readouterr().err == f"waf-upgrade-check: error: {message}\n"
