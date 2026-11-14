import unittest

from bundle.models import Bundle, BundleError, Policy, Statement, Version


class ModelsTest(unittest.TestCase):
    def test_bundle_holds_its_parts(self):
        policy = Policy(name="read-only", statement=Statement(effect="Allow", actions=["read"]))
        bundle = Bundle(name="web", capacity=2, policy=policy, versions=[Version(name="v1", created="2026-11-01")])
        self.assertEqual(bundle.policy.statement.actions, ["read"])
        self.assertEqual(bundle.versions[0].name, "v1")

    def test_versions_default_to_empty(self):
        policy = Policy(name="p", statement=Statement(effect="Deny", actions=[]))
        self.assertEqual(Bundle(name="web", capacity=1, policy=policy).versions, [])

    def test_bundle_error_is_a_value_error(self):
        self.assertTrue(issubclass(BundleError, ValueError))


if __name__ == "__main__":
    unittest.main()
