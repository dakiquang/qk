import pytest
from botocore.exceptions import ClientError
from botocore.stub import Stubber

from waf_upgrade_check import aws

GROUP = "AWSManagedRulesCommonRuleSet"


def test_list_versions_follows_pagination(wafv2_client, load_fixture):
    base = {"VendorName": "AWS", "Name": GROUP, "Scope": "REGIONAL"}
    with Stubber(wafv2_client) as stub:
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

        result = aws.list_versions(wafv2_client, GROUP, "REGIONAL")

        stub.assert_no_pending_responses()
    assert result == ("Version_1.1", ["Version_1.10", "Version_1.1", "Version_1.0"])


def test_list_version_timestamps_follows_pagination(wafv2_client, load_fixture):
    base = {"VendorName": "AWS", "Name": GROUP, "Scope": "REGIONAL"}
    with Stubber(wafv2_client) as stub:
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

        result = aws.list_version_timestamps(wafv2_client, GROUP, "REGIONAL")

        stub.assert_no_pending_responses()
    assert result == (
        "Version_1.1",
        [("Version_1.10", 1767225600), ("Version_1.1", 1759276800), ("Version_1.0", 1751328000)],
    )


def test_get_web_acl_requests_name_scope_and_id(wafv2_client, load_fixture):
    response = load_fixture("web_acl_upgrade.json")
    with Stubber(wafv2_client) as stub:
        stub.add_response(
            "get_web_acl",
            response,
            {"Name": "example-web-acl", "Scope": "REGIONAL", "Id": "acl-id"},
        )

        result = aws.get_web_acl(wafv2_client, "example-web-acl", "acl-id", "REGIONAL")

        stub.assert_no_pending_responses()
    assert result["WebACL"] == response["WebACL"]


def test_describe_requests_the_given_version(wafv2_client, load_fixture):
    with Stubber(wafv2_client) as stub:
        stub.add_response(
            "describe_managed_rule_group",
            load_fixture("describe_v1_1.json"),
            {
                "VendorName": "AWS",
                "Name": GROUP,
                "Scope": "CLOUDFRONT",
                "VersionName": "Version_1.1",
            },
        )

        version = aws.describe(wafv2_client, GROUP, "CLOUDFRONT", "Version_1.1")

        stub.assert_no_pending_responses()
    assert version.name == "Version_1.1"
    assert version.capacity == 750


def test_describe_propagates_client_error(wafv2_client):
    with Stubber(wafv2_client) as stub:
        stub.add_client_error("describe_managed_rule_group", "WAFNonexistentItemException")

        with pytest.raises(ClientError) as error:
            aws.describe(wafv2_client, GROUP, "REGIONAL", "Version_9.9")

    assert error.value.response["Error"]["Code"] == "WAFNonexistentItemException"


def test_make_client_forces_us_east_1_for_cloudfront():
    assert aws.make_client("CLOUDFRONT", None, None).meta.region_name == "us-east-1"


def test_make_client_uses_given_region_for_regional():
    assert aws.make_client("REGIONAL", "eu-west-1", None).meta.region_name == "eu-west-1"
