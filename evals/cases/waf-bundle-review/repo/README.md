# waf-upgrade-check

Check what breaks before you upgrade an AWS WAF managed rule group version.

> **Work in progress.** Nothing is released yet. Personal project, not affiliated with any company, no support commitment.

When you move a web ACL to a newer static version of an AWS Managed Rules rule group, some breakage is silent:

- **Overrides by rule name stop working.** AWS WAF silently ignores a rule action override whose rule name does not exist in the managed rule group ([`ManagedRuleGroupStatement`](https://docs.aws.amazon.com/waf/latest/APIReference/API_ManagedRuleGroupStatement.html)).
- **Your own rules may match labels the new version no longer adds.**
- **Capacity (WCU) can grow.**
- **A pinned version can be scheduled to expire**, after which AWS WAF uses the default version and blocks web ACL updates until you change it ([version life cycle](https://docs.aws.amazon.com/waf/latest/developerguide/waf-managed-rule-groups-versioning-lifecycle.html)).

`waf-upgrade-check` reads the rule group versions and your web ACL, and reports these before you upgrade. It only calls read APIs.

## Usage

List the available versions of a managed rule group; the current default is marked:

```console
$ waf-upgrade-check versions AWSManagedRulesCommonRuleSet --region eu-west-1
Version_1.10
Version_1.1 (default)
Version_1.0
Default version: Version_1.1
```

Compare two versions: rules added and removed, rule action changes, capacity (WCU), and available and consumed labels:

```console
$ waf-upgrade-check diff AWSManagedRulesCommonRuleSet Version_1.0 Version_1.1 --region eu-west-1
```

Check every AWS managed rule group in a web ACL against a target version. Read the web ACL from a file (the output of `aws wafv2 get-web-acl`) with `--web-acl-file PATH`, or fetch it with `--web-acl NAME --id ID`:

```console
$ waf-upgrade-check check --web-acl-file web-acl.json --region eu-west-1
ERROR  AWSManagedRulesCommonRuleSet  label-no-longer-emitted  rule BlockLegacyLabel matches LABEL awswaf:managed:aws:core-rule-set:LegacyRule_QueryArguments, not emitted by Version_1.1
ERROR  AWSManagedRulesCommonRuleSet  override-missing-rule  RuleActionOverrides entry LegacyRule_QUERYARGUMENTS in rule AWS-CRS is not a rule in Version_1.1
WARNING  AWSManagedRulesCommonRuleSet  capacity-increase  capacity 700 -> 750 WCU (+50); web ACL capacity 900
INFO  AWSManagedRulesCommonRuleSet  behind-default  pinned version Version_1.0 differs from default Version_1.1
INFO  AWSManagedRulesCommonRuleSet  rules-changed  Version_1.0 -> Version_1.1: 1 added, 1 removed, 1 action changed
Summary: 2 error(s), 1 warning(s), 2 info
```

`--target` selects the version to check against: `default` (the current default version, the default), `latest` (the version with the newest `LastUpdateTimestamp`), or a version name. A version name that a rule group in the web ACL does not have is a usage error. Only top-level rule groups from vendor `AWS` are checked; Marketplace rule groups are ignored.

Findings:

- `override-missing-rule` (error): a `RuleActionOverrides` or `ExcludedRules` entry names a rule that the target version does not have.
- `label-no-longer-emitted` (error): another rule matches a label or label namespace that the version in use adds and the target version does not.
- `version-unavailable` (error): the pinned version is no longer listed as available.
- `capacity-increase` (warning): the target version needs more WCU than the version in use.
- `behind-default` (info): the pinned version is not the current default.
- `rules-changed` (info): rules added, removed, or with a changed action between the version in use and the target.

Options for all commands:

- `--scope {REGIONAL,CLOUDFRONT}`: rule group scope, default `REGIONAL`. `CLOUDFRONT` always uses `us-east-1`; any other `--region` with it is an error.
- `--region REGION`: AWS region for `REGIONAL` scope. Defaults to your AWS configuration.
- `--profile PROFILE`: AWS named profile. Defaults to the standard AWS credential chain.
- `--format {text,json}`: output format, default `text`.

Exit codes: `0` on success; `1` when `check` reports at least one error finding; `2` on a usage error, a credential or configuration error, or an AWS API error. Errors are printed to stderr as `waf-upgrade-check: error: <message>`.

## License

[MIT](LICENSE).
