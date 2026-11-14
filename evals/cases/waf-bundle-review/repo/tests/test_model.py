import pytest

from waf_upgrade_check.model import RuleGroupVersion


def test_from_response_parses_full_describe(load_fixture):
    version = RuleGroupVersion.from_response(load_fixture("describe_v1_0.json"))

    assert version.name == "Version_1.0"
    assert version.capacity == 700
    assert version.rules == {
        "NoUserAgent_HEADER": "Block",
        "SizeRestrictions_BODY": "Count",
        "EC2MetaDataSSRF_BODY": "Block",
        "LegacyRule_QUERYARGUMENTS": "Block",
    }
    assert version.available_labels == frozenset(
        {
            "awswaf:managed:aws:core-rule-set:NoUserAgent_Header",
            "awswaf:managed:aws:core-rule-set:SizeRestrictions_Body",
            "awswaf:managed:aws:core-rule-set:LegacyRule_QueryArguments",
        }
    )
    assert version.consumed_labels == frozenset({"awswaf:managed:aws:bot-control:bot:verified"})
    assert version.label_namespace == "awswaf:managed:aws:core-rule-set:"


def test_from_response_tolerates_missing_optional_fields(load_fixture):
    version = RuleGroupVersion.from_response(load_fixture("describe_minimal.json"))

    assert version.rules == {"RuleWithoutAction": None}
    assert version.available_labels == frozenset()
    assert version.consumed_labels == frozenset()
    assert version.label_namespace is None


def test_from_response_treats_empty_action_as_none(load_fixture):
    resp = load_fixture("describe_minimal.json")
    resp["Rules"] = [{"Name": "EmptyAction", "Action": {}}]

    assert RuleGroupVersion.from_response(resp).rules == {"EmptyAction": None}


def test_from_response_rejects_action_with_several_keys(load_fixture):
    resp = load_fixture("describe_minimal.json")
    resp["Rules"] = [{"Name": "Ambiguous", "Action": {"Block": {}, "Count": {}}}]

    with pytest.raises(ValueError, match="exactly one rule action"):
        RuleGroupVersion.from_response(resp)
