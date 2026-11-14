from waf_upgrade_check.diff import ActionChange, diff_versions
from waf_upgrade_check.model import RuleGroupVersion


def _version(load_fixture, name):
    return RuleGroupVersion.from_response(load_fixture(name))


def test_diff_reports_every_kind_of_change(load_fixture):
    result = diff_versions(
        _version(load_fixture, "describe_v1_0.json"), _version(load_fixture, "describe_v1_1.json")
    )

    assert result.rules_added == ("CrossSiteScripting_COOKIE",)
    assert result.rules_removed == ("LegacyRule_QUERYARGUMENTS",)
    assert result.actions_changed == (ActionChange("SizeRestrictions_BODY", "Count", "Block"),)
    assert (result.capacity_old, result.capacity_new) == (700, 750)
    assert result.available_labels_added == (
        "awswaf:managed:aws:core-rule-set:CrossSiteScripting_Cookie",
    )
    assert result.available_labels_removed == (
        "awswaf:managed:aws:core-rule-set:LegacyRule_QueryArguments",
    )
    assert result.consumed_labels_added == (
        "awswaf:managed:aws:bot-control:signal:automated_browser",
    )
    assert result.consumed_labels_removed == ()


def test_diff_of_identical_versions_is_empty(load_fixture):
    version = _version(load_fixture, "describe_v1_0.json")

    result = diff_versions(version, version)

    assert result.rules_added == result.rules_removed == result.actions_changed == ()
    assert result.available_labels_added == result.available_labels_removed == ()
    assert result.consumed_labels_added == result.consumed_labels_removed == ()
    assert result.capacity_old == result.capacity_new == 700


def test_diff_reports_action_change_from_none(load_fixture):
    old = _version(load_fixture, "describe_minimal.json")
    resp = load_fixture("describe_minimal.json")
    resp["Rules"] = [{"Name": "RuleWithoutAction", "Action": {"Block": {}}}]
    new = RuleGroupVersion.from_response(resp)

    assert diff_versions(old, new).actions_changed == (
        ActionChange("RuleWithoutAction", None, "Block"),
    )
