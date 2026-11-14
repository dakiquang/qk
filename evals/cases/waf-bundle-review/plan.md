# Add AWS MCP bundle mode, collect-script and agent skill

Status: draft, 2026-11-14

## Goal and out of scope

Goal: make `waf-upgrade-check` the extension arm of the AWS MCP Server. An agent reads AWS through AWS MCP `run_script` using a snippet that this package generates. The snippet returns a JSON bundle. `check --bundle` then answers "what breaks if I upgrade this managed rule group" fully offline. The work covers six parts: bundle format and loader, `check --bundle`, `collect-script`, tests, the agent skill, and the README and CHANGELOG.

Must not change:
- Existing findings, their messages, ordering and exit codes.
- Behaviour of `versions`, `diff`, `check --web-acl-file` and `check --web-acl`.
- `aws.py`, `model.py`, `diff.py` and `check.py`: no behaviour change.
- `pyproject.toml`: description and dependencies stay as they are.

Out of scope:
- Publishing to PyPI.
- Bundle support for `versions` and `diff`.
- Non-AWS vendors.
- Label consumers inside `RuleGroupReferenceStatement` and Firewall Manager rule groups (documented as a limit only).
- Any write API.
- Changes to CI workflows.

## Current state and evidence

- [Verified] `src/waf_upgrade_check/check.py`:
  - `RuleGroupCatalog(default, available: tuple[(name, LastUpdateTimestamp)], versions: Mapping[str, RuleGroupVersion])`.
  - `check_web_acl` treats a `default` that is missing from `versions` as not describable (`_described`, `default-not-describable`). Any other missing version raises `KeyError` (`catalog.versions[name]`).
  - `resolve_versions` parses timestamps with `botocore.utils.parse_to_aware_datetime`, which accepts ISO strings and epoch numbers (tests `test_resolve_latest_compares_iso_timestamps_across_offsets`, `AVAILABLE` ints).
- [Verified] `src/waf_upgrade_check/cli.py` `_cmd_check` has four stages:
  1. Reads the web ACL from a file or the API.
  2. Lists versions per group.
  3. Builds the `needed` set: in-use plus target from `resolve_versions`. `TargetError` becomes `UsageError`.
  4. Describes each needed version. It skips a default that is not listed and tolerates `WAFNonexistentItemException` for the default.

  `main` maps `UsageError`, `BotoCoreError` and `ClientError` to exit 2. `_client` rejects CLOUDFRONT with a region other than us-east-1. The `source` mutually exclusive group holds `--web-acl-file` and `--web-acl`.
- [Verified] `RuleGroupVersion.from_response` (model.py) needs `VersionName`, `Capacity` and `Rules`; labels and namespace are optional.
- [Verified] Tests:
  - `tests/test_cli.py::test_check_api_json` is the API-mode test. It uses `web_acl_upgrade.json` via GetWebACL, `list_versions_page1/2.json` (`NextMarker` `page-2-marker`, int timestamps) and `describe_v1_0/1_1.json`.
  - `test_check_undescribable_default_warns_and_checks_other_groups` covers the Windows and KBI case with the real fixtures in `tests/fixtures/aws/`.
  - The `no_client` fixture lives in `test_cli.py`. `conftest.py` provides `load_fixture` and isolates AWS env vars.
- [Verified] `tests/fixtures/aws/*_list.json` contain `NextMarker: "Version_1.0"` and ISO timestamp strings. `windows_list_rc_default.json` has default `Version_2.4_PLUS_RC_COUNT`, which is not in its Versions.
- [Verified] Done commands come from `.github/workflows/ci.yml`: `uv run --frozen ruff check .`, `uv run --frozen ruff format --check .`, `uv run --frozen pytest`. Ruff: line-length 100, rules E, F, I, B, UP, target py310.
- [Verified, real AWS MCP `run_script` calls on 2026-11-14 while writing this plan; read-only, public managed rule group metadata only]
  - `import datetime` is accepted, and `datetime.datetime.fromisoformat("2026-05-29T18:09:25.997000+00:00")` works. Top-level `await call_boto3(...)` works.
  - `ClientError` is not defined in the sandbox (NameError), even though the tool docs list it as pre-imported. The raised exception's `repr` is `ClientError("An error occurred (WAFNonexistentItemException) ...")` and `str(exc)` contains the code. So the snippet must use `except Exception as error:` plus `"WAFNonexistentItemException" in str(error)`.
  - The draft snippet body in "Planned changes" passed the code validator unchanged, with Windows unpinned and KBI pinned at `Version_1.0` embedded. It made these calls: GetCallerIdentity; for each group, List, then List again → 0 versions and no marker; Describe KBI `Version_1.0` and `Version_1.26`; no Describe for Windows.
  - Even after the loop finishes, the response carries a `warning` that pagination returned only the first page. That warning is expected and harmless; `api_calls` shows the follow-up calls.
  - Results come back under `return_value`.
- [Verified] Skills CLI discovers `skills/<name>/SKILL.md`. Frontmatter requires `name` and `description` (https://github.com/vercel-labs/skills/blob/main/docs/creating-skills.md).
- [Verified] AWS doc pages exist:
  - AWS MCP Server tools: https://docs.aws.amazon.com/agent-toolkit/latest/userguide/understanding-mcp-server-tools.html
  - RuleSummary has only `Name` and `Action`: https://docs.aws.amazon.com/waf/latest/APIReference/API_RuleSummary.html
  - AWS Managed Rules changelog (CRS entries are mostly "improved detection signatures"): https://docs.aws.amazon.com/waf/latest/developerguide/aws-managed-rule-groups-changelog.html
  - Firewall Manager WAF policies: https://docs.aws.amazon.com/waf/latest/developerguide/waf-policies.html
- [Inference, open each link before committing] Standard API reference URLs:
  - `API_ListAvailableManagedRuleGroupVersions.html`, `API_DescribeManagedRuleGroup.html`, `API_GetWebACL.html`, `API_RuleGroupReferenceStatement.html` under https://docs.aws.amazon.com/waf/latest/APIReference/
  - https://docs.aws.amazon.com/STS/latest/APIReference/API_GetCallerIdentity.html
  - https://docs.aws.amazon.com/service-authorization/latest/reference/list_awswafv2.html
  - https://docs.aws.amazon.com/waf/latest/developerguide/waf-labels.html
  - https://docs.aws.amazon.com/waf/latest/developerguide/aws-managed-rule-groups-baseline.html

## Decisions

| # | Decision | Why | Rejected |
|---|---|---|---|
| D1 | The snippet describes exactly what API mode describes for the given `--target`: each in-use version (pinned if listed, else the default) plus the resolved target (default / latest by newest `LastUpdateTimestamp`, ties go to the first in API order / an explicit name if listed). | Gives exact parity with API mode and the "only the versions needed" wording. Part 2's exit-2 message covers using a bundle with a different `--target`. | Always describing default and latest as well: more calls, and the CRS synthetic data would need a new describe fixture for `Version_1.10`. |
| D2 | The snippet is a generated header plus a constant body (`collect.py`). Literals are emitted with `repr()` for strings and `pprint.pformat(..., sort_dicts=False)` for the embedded web ACL. The body uses explicit `for` loops, no comprehensions, no `def`, no dunders, distinct loop variable names per response type (`rule`, `statement`, `page`, `entry`), and `import datetime` as its only import. | Matches the validator behaviour verified above. `repr` and `pformat` yield valid Python literals for any string, so nothing can be injected through a web ACL name or ID. | `json.dumps` embedding: JSON `true/false/null` are not Python. `string.Template` over the whole script: harder to read. |
| D3 | Groups are computed at runtime inside the snippet from `web_acl["WebACL"]["Rules"]`, in both modes. With `--web-acl-file` the header assigns the embedded literal; with `--web-acl` the header calls GetWebACL. | One body for both modes. GetWebACL appears only in API-mode snippets. | Precomputing groups in Python for file mode: two code paths. |
| D4 | `collect-script --scope REGIONAL` requires `--region` (exit 2: `collect-script --scope REGIONAL requires --region`). CLOUDFRONT uses us-east-1 and rejects other regions with the existing message. | The sandbox has no local AWS config, so a missing region would read an unknown region silently. | Passing `region_name=None`: undefined region. |
| D5 | Missing data in a bundle:<br>• A version needed by `resolve_versions` that is absent and not the group's default → `UsageError`, exit 2: `bundle file PATH has no description of GROUP version VERSION; describe it or run collect-script again with --target TARGET`.<br>• An absent default (listed or not) → left out of `RuleGroupCatalog.versions`, so the existing `default-not-describable` warning applies.<br>• A web ACL group missing from `rule_groups` → `BundleError`. | The snippet only omits a default when it is unlisted or describing it raised `WAFNonexistentItemException`. | Failing on an absent default: that would break Windows and BotControl. |
| D6 | Factor `_needed_versions(refs, listed, target)` out of `_cmd_check` and share it between API mode and bundle mode. `check_web_acl` is unchanged. | A single definition of "needed". | Duplicating the selection loop. |
| D7 | `bundle.py` owns `FORMAT = "waf-upgrade-check/bundle/v1"`, `BundleError(ValueError)`, `Bundle` (frozen dataclass: `web_acl`, `catalogs`) and `load_bundle(path) -> Bundle`. `collect.py` imports `FORMAT`. `caller`, if present, must be an object; `scope` must be REGIONAL or CLOUDFRONT. Neither is stored, because `check` does not use them. | One source for the format string; no dead fields. | Storing `account`: unused. |
| D8 | With `--bundle`, `--scope`, `--region` and `--profile` are ignored and no client is created. `--id` with `--bundle` → exit 2 `--id cannot be used with --bundle`. `--bundle` joins the existing required mutually exclusive `source` group. | Spec part 2. Same style as the existing `--id` rules. | — |
| D9 | `collect-script` takes `--scope`, `--region`, `--web-acl`/`--web-acl-file` (required, mutually exclusive), `--id` and `--target`. It does not take `--profile` or `--format`. Split `_common_options` into a scope/region parent reused by both. | Those options have no meaning for a printed snippet. | Inheriting all common options. |
| D10 | Tests run the snippet with `compile(..., flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)` plus `asyncio.run` against a fake async `call_boto3`. The fake raises `botocore.exceptions.ClientError` for WAFNonexistentItemException, as the sandbox does. Parity tests run API mode (Stubber) and bundle mode in the same test and compare outputs. | Proves "same findings" without copying expected lists. | Comparing against hard-coded expectations only. |

## Planned changes

New files:
- `src/waf_upgrade_check/bundle.py`
  - `FORMAT`, `BundleError`, `Bundle`, `load_bundle(path)`.
  - Validation order:
    1. File is readable JSON (`cannot read bundle file PATH: ...`).
    2. Top level is an object and `format == FORMAT` (`bundle file PATH has format X; expected waf-upgrade-check/bundle/v1`).
    3. `scope` is valid.
    4. `web_acl.WebACL` is an object.
    5. `rule_groups` is an object.
    6. Each `rule_groups.<g>` has `list_versions` (an object with a `Versions` list of objects that have `Name`; `CurrentDefaultVersion` is optional and may be null) and `versions` (an object).
    7. Each `versions.<v>` builds with `RuleGroupVersion.from_response`. Catch `KeyError`, `TypeError` and `ValueError` → `BundleError` naming `rule_groups.<g>.versions.<v>`. The response's `VersionName` must equal `<v>`.
    8. `caller` is optional and must be an object.
    9. Every group in `check.managed_references(web_acl)` must be in `rule_groups` (`bundle file PATH has no rule_groups entry for GROUP; run collect-script again`).
    - Missing keys produce `bundle file PATH is missing <dotted.key>`.
    - Catalog: `RuleGroupCatalog(default, tuple((e["Name"], e.get("LastUpdateTimestamp")) for e in Versions), {v: RuleGroupVersion})`.
- `src/waf_upgrade_check/collect.py`
  - `build_script(scope, region, target, *, web_acl=None, web_acl_name=None, web_acl_id=None) -> str`, where exactly one of `web_acl` or (`web_acl_name` and `web_acl_id`) is given.
  - Header: a comment that it is read-only and should be pasted into AWS MCP `run_script` (no `__`); `import datetime`; `SCOPE`, `REGION` and `TARGET` set via `repr`; then either `web_acl = <pformat literal>` or a GetWebACL `call_boto3`.
  - Body: the validated draft below. Template lines stay at or under 100 characters, and call_boto3 calls are split across lines.

    ```python
    identity = await call_boto3(service_name="sts", operation_name="GetCallerIdentity",
                                region_name=REGION, params={})
    uses = {}
    for rule in web_acl["WebACL"].get("Rules", []):
        statement = rule.get("Statement", {}).get("ManagedRuleGroupStatement")
        if not statement or statement.get("VendorName") != "AWS":
            continue
        group = statement.get("Name")
        if group not in uses:
            uses[group] = []
        uses[group].append(statement.get("Version"))
    rule_groups = {}
    for group in uses:
        params = {"VendorName": "AWS", "Name": group, "Scope": SCOPE}
        default = None
        entries = []
        while True:
            page = await call_boto3(service_name="wafv2",
                                    operation_name="ListAvailableManagedRuleGroupVersions",
                                    region_name=REGION, params=params)
            if page.get("CurrentDefaultVersion"):
                default = page.get("CurrentDefaultVersion")
            page_entries = page.get("Versions", [])
            for entry in page_entries:
                entries.append(entry)
            marker = page.get("NextMarker")
            if not marker or not page_entries:
                break
            params = {"VendorName": "AWS", "Name": group, "Scope": SCOPE, "NextMarker": marker}
        # names list + latest by newest stamp (str -> fromisoformat(s.replace("Z", "+00:00"))
        # .timestamp(), ValueError -> skip; numbers used as-is; strict > so first max wins)
        # wanted = in-use per pinned (None -> default; pinned if in names) + target
        # (default | latest | TARGET if in names), deduplicated, order kept
        described = {}
        for version_name in wanted:
            if version_name == default and default not in names:
                continue
            try:
                described[version_name] = await call_boto3(service_name="wafv2",
                    operation_name="DescribeManagedRuleGroup", region_name=REGION,
                    params={"VendorName": "AWS", "Name": group, "Scope": SCOPE,
                            "VersionName": version_name})
            except Exception as error:
                if version_name != default or "WAFNonexistentItemException" not in str(error):
                    raise
        rule_groups[group] = {"list_versions": {"CurrentDefaultVersion": default,
                                                "Versions": entries},
                              "versions": described}
    result = {"format": FORMAT, "scope": SCOPE, "web_acl": web_acl,
              "rule_groups": rule_groups, "caller": {"account": identity.get("Account")}}
    result
    ```

    The `FORMAT` value is emitted as a literal via `repr(bundle.FORMAT)`.
- `skills/waf-upgrade-check/SKILL.md` (under 120 lines)
  - Frontmatter: `name: waf-upgrade-check`, plus a `description` that triggers on "is it safe to upgrade / what breaks if I move a web ACL to a newer AWS WAF managed rule group version, using the AWS MCP Server".
  - Body:
    - Prerequisites: AWS MCP Server connected (`run_script`); `waf-upgrade-check --version` works, otherwise point to the README install.
    - Step 1: run `run_script` with a 3-line GetCallerIdentity script. Show the account and ARN, then ask the user to confirm the account and which web ACL (name, id, scope, region) before reading anything. Prefer `--web-acl-file` when the user has an export.
    - Step 2: `waf-upgrade-check collect-script (--web-acl NAME --id ID | --web-acl-file PATH) --scope S --region R --target T`.
    - Step 3: run the printed snippet unchanged with `run_script`. Check that `api_calls` contains only GetCallerIdentity, GetWebACL, ListAvailableManagedRuleGroupVersions and DescribeManagedRuleGroup. The pagination warning is expected. On a validator or API error, stop and report it; do not rewrite the snippet.
    - Step 4: save `return_value` as JSON to a file outside the repository (for example under `mktemp -d`).
    - Step 5: `waf-upgrade-check check --bundle FILE --target T --format json`. Exit 0 means no errors, 1 means error findings, 2 means a usage or bundle problem. If the message says a version is missing, rerun collect-script with the same `--target`.
    - Step 6: report error findings first, as decisions for the user (group, what breaks, options: drop or rename the override, update the label rule, stay pinned). Then warnings, then info.
    - Rules: never call write APIs (Create/Update/Delete/Put/Associate/Disassociate/Tag…); never change the web ACL or apply an upgrade; only suggest changes.
- `tests/test_bundle.py`, `tests/test_collect.py`, and an optional `tests/fixtures/` addition only if a test needs one. The plan avoids new fixtures by reusing the existing ones.

Edited files:
- `src/waf_upgrade_check/cli.py`
  - Add `--bundle FILE` to `source`.
  - Add the `--id` with `--bundle` error.
  - Add `_needed_versions` and split `_cmd_check` into `_api_inputs(args) -> (web_acl, catalogs)` and `_bundle_inputs(args) -> (web_acl, catalogs)`. The bundle path calls `load_bundle` (`BundleError` → `UsageError`), applies `_needed_versions`, then applies the D5 missing-version check. It never calls `_client`.
  - Add `_region(args)`, which raises `UsageError`; `_client` and collect-script both use it.
  - Add the `collect-script` subparser and `_cmd_collect_script`. That handler reuses `_read_web_acl` for `--web-acl-file`, applies the `--web-acl` without `--id` and `--id` with `--web-acl-file` errors, and writes `build_script(...)` to stdout. It returns 0 and never creates a client.
  - Share the `--target` definition through a small helper.
- `tests/conftest.py`
  - Move `no_client` here from `test_cli.py`.
  - Add a `fake_aws` fixture: a `FakeAws` with `calls` (service, operation, region, params) and an async `call_boto3(*, service_name, operation_name, region_name=None, params=None)`. It serves deep copies of:
    - GetWebACL → `web_acl_upgrade.json`
    - sts GetCallerIdentity → `{"Account": "123456789012", ...}`
    - Lists keyed by (Name, NextMarker):
      - CRS → page1 and page2
      - KBI → fixture, then on `Version_1.0` `{"Versions": []}` (real behaviour)
      - Windows → fixture, then on `Version_1.0` `{"Versions": [], "NextMarker": "Version_1.0"}` (exercises the empty-page stop)
    - Describes keyed by (Name, VersionName) → CRS 1.0 and 1.1, KBI 1.0 and 1.26
    - An `errors` dict of (Name, VersionName) → `ClientError`
    - Unknown calls, or more than 50 calls, raise `AssertionError`.
  - Add a `run_snippet(snippet, call_boto3) -> dict` fixture: compile with `PyCF_ALLOW_TOP_LEVEL_AWAIT`, `eval` into a namespace that has only `call_boto3`, `asyncio.run` the coroutine, return `namespace["result"]`.
- `tests/test_cli.py`
  - Extract the Windows+KBI web ACL and stub setup of `test_check_undescribable_default_warns_and_checks_other_groups` into helpers; keep that test's assertions.
  - Add `--bundle`/`--web-acl-file` and `--bundle`/`--web-acl` cases to `test_usage_errors_exit_2`.
  - Add the `--bundle x --id y` case to `test_check_option_errors_exit_2`.
  - Add the parity tests (Steps 4 and 5).
- `README.md`: rewritten (Step 7).
- `CHANGELOG.md`: Unreleased section (Step 7).

## Steps

1. **bundle.py.** Write the module per D7. In `tests/test_bundle.py`, build a valid bundle dict from the fixtures (web_acl_upgrade, CRS list with ISO stamps, describe 1.0 and 1.1). Tests:
   - `load_bundle` returns catalogs equal to the hand-built `RuleGroupCatalog`.
   - A parametrized list of mutations, each giving `BundleError` with the expected fragment and the path: wrong format, format missing, bad scope, missing `web_acl.WebACL`, missing `rule_groups`, missing `list_versions.Versions`, missing `versions`, describe missing `Capacity`, `VersionName` mismatch, referenced group missing, `caller` not an object.

   Done when `uv run --frozen pytest tests/test_bundle.py` passes.
2. **`check --bundle`.** Change cli.py per D5, D6 and D8. Tests in `test_cli.py` or `test_bundle.py`, using `no_client`:
   - A bundle without CRS `Version_1.1` → exit 2 with stderr exactly `waf-upgrade-check: error: bundle file PATH has no description of AWSManagedRulesCommonRuleSet version Version_1.1; describe it or run collect-script again with --target default`. Here 1.1 is the default but listed, so it counts as a missing default: replace this example with a missing in-use `Version_1.0` to hit the error branch, and assert that a missing listed default gives `default-not-describable` with exit 0 on `web_acl_clean.json` data.
   - The mutual exclusion and `--id` cases.

   Done when the existing CLI tests are unchanged and green, and the new tests pass.
3. **collect.py and `collect-script`.** Implement per D1–D4 and D9. `tests/test_collect.py`:
   - (a) Static check, both modes: parse with `ast.PyCF_ONLY_AST | ast.PyCF_ALLOW_TOP_LEVEL_AWAIT`. Assert there is no `ast.Attribute`/`ast.Name` containing `"__"`. Assert every `call_boto3` call has constant `service_name` in {`wafv2`, `sts`} and constant `operation_name` matching `^(Get|List|Describe)[A-Za-z]+$`. Assert the set of operations is exactly {GetCallerIdentity, GetWebACL, ListAvailableManagedRuleGroupVersions, DescribeManagedRuleGroup} for `--web-acl` and the same without GetWebACL for `--web-acl-file`.
   - (b) File mode on the Windows+KBI ACL, with a `Description` containing `'`, `"` and `\n`:
     - the bundle's `web_acl` equals the file;
     - no GetWebACL call and no Describe for Windows;
     - Windows listing stops after the empty page that still has a marker;
     - KBI Versions has all 7 entries;
     - `caller.account` is `123456789012`;
     - `load_bundle` accepts the bundle written with `json.dumps`.
   - (c) Target selection on CRS (int timestamps), parametrized; assert the described (Name, VersionName) set from `fake_aws.calls`:
     - `default` → {1.0, 1.1}
     - `latest` → {1.0, 1.10}; the test adds a fake describe for 1.10 as a copy of 1.1 with `VersionName` changed
     - `Version_1.1` → {1.0, 1.1}
     - `Version_9.9` → {1.0}
   - (d) A listed default whose describe raises WAFNonexistentItemException → bundle without it; `check --bundle` on `web_acl_clean.json` data gives exactly the `default-not-describable` output of `test_check_default_describe_nonexistent_warns`.
   - (e) A non-default describe raising WAFAccessDeniedException → `run_snippet` raises.
   - (f) CLOUDFRONT without `--region` → every fake call has `region_name == "us-east-1"`.
   - (g) Exit 2 with exact messages, using `no_client`: REGIONAL without `--region`; CLOUDFRONT plus `--region eu-west-1`; `--web-acl` without `--id`; `--id` with `--web-acl-file`; an unreadable `--web-acl-file`.

   Done when the tests pass.
4. **API-mode parity.** In `test_cli.py`:
   1. Run the `test_check_api_json` stubs and argv with `--format json` and capture the output.
   2. Monkeypatch `aws.make_client` to raise.
   3. `main(["collect-script", "--web-acl", "example-web-acl", "--id", WEB_ACL_ID, "--region", "us-east-1"])` and capture the snippet.
   4. `run_snippet` with `fake_aws`.
   5. Write `bundle.json` in `tmp_path`.
   6. `main(["check", "--bundle", path, "--format", "json"]) == 1`.
   7. Assert the JSON output equals the API-mode output.

   Done when the test passes.
5. **Undescribable-default parity.** Same pattern with the extracted Windows+KBI helpers and `--web-acl-file` (text format), comparing against the API-mode run. Done when the test passes.
6. **Skill.** Write `skills/waf-upgrade-check/SKILL.md` per Planned changes. Done when it has frontmatter with `name` and `description`, is under 120 lines, and gives the six agent steps from the task in order.
7. **README and CHANGELOG.**
   - README order:
     1. Title and new description line: "Find what breaks before you upgrade an AWS WAF managed rule group version — an extension for agents on the AWS MCP Server, and a CLI."
     2. WIP note.
     3. Problem (keep the four bullets and links).
     4. **Use with AWS MCP**: `npx skills add dakiquang/waf-upgrade-check`; what the agent does (the six steps, short); a sample session of 6–8 lines, marked as an example, with a placeholder account `123456789012`.
     5. **Install the CLI**: `pipx install waf-upgrade-check` (not yet published); from source `uv tool install git+https://github.com/dakiquang/waf-upgrade-check`, or clone plus `uv run waf-upgrade-check`.
     6. **Commands**: versions; diff; check with `--bundle` / `--web-acl-file` / `--web-acl`, `--target`, the findings list kept; collect-script with its options. Note that `--bundle` ignores `--scope`, `--region` and `--profile`.
     7. Options.
     8. **Exit codes**: 0, 1, and 2 (now including bundle errors and a missing version in a bundle).
     9. GitHub Actions example: OIDC `aws-actions/configure-aws-credentials` (pin the current major tag checked on its releases page at implementation time), `astral-sh/setup-uv@v10.3.3` (the version already in `ci.yml`), and `uvx --from git+https://github.com/dakiquang/waf-upgrade-check waf-upgrade-check check --web-acl-file waf/web-acl.json --region eu-west-1`.
     10. **Read-only IAM policy** JSON: Version 2012-10-17; Allow the four actions on `"*"`. Note that the AWS MCP Server may need its own permissions (link its docs).
     11. **Known limits**: the three from the task, with links (RuleSummary, changelog, RuleGroupReferenceStatement, Firewall Manager).
     12. Links for every AWS claim, as listed in Current state.
     13. License.
   - CHANGELOG Unreleased:
     - Added: bundle format `waf-upgrade-check/bundle/v1`; `check --bundle FILE` (offline, exits 2 naming a missing group or version); `collect-script` command; agent skill `skills/waf-upgrade-check`.
     - Changed: README is organized around AWS MCP.

   Done when every link has been opened and resolves (the Inference list above).
8. Run the qk-verify commands. Done when all three exit 0.

## Verification

```qk-verify
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
```

Manual, optional, not a done criterion (needs a connected AWS MCP Server): pipe `uv run --frozen waf-upgrade-check collect-script --web-acl-file tests/fixtures/web_acl_upgrade.json --region us-east-1` into `run_script`. Confirm the validator accepts it and `api_calls` contains only Get/List/Describe. This file mode reads no account resource.

## Risks

- Changes to the AWS MCP validator could reject the snippet. Signal: a `run_script` error naming a field or attribute. Response: the skill tells the agent to stop and report. Re-validate the body with the manual check above, and keep its constructs plain (D2).
- `fromisoformat` differs from `parse_to_aware_datetime` for unusual timestamp formats. Signal: `check --bundle --target latest` exits 2 naming the latest version. This fails closed; the user reruns, or describes the version via a manual run_script.
- The sandbox may change its exception type or message. Signal: the default describe error is no longer tolerated (run_script fails on Windows or BotControl). Response: widen the match to `getattr(error, "response", {})`, avoiding dunders.
- The bundle contains the account's web ACL configuration. The skill requires saving it outside the repository. The README says the same.
- The size of a large web ACL embedded as a literal is not measured against run_script input limits. Signal: tool error on input size. Response: use `--web-acl NAME --id ID` instead.

## Open questions

- D1 reading: should the snippet describe only in-use plus resolved target (planned), or always add default and latest so one bundle serves every `--target`? The plan proceeds with D1 unless told otherwise.
- D4: requiring `--region` for REGIONAL in `collect-script` is a planning choice, not in the task text.
