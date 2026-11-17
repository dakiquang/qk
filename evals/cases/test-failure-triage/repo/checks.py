"""Read-only checkout checks; structured output is evidence, not a repair request."""
import json
import sys

from checkout import free_shipping, legacy_slug


def main():
    checks = [
        ("shipping-boundary", True, free_shipping(50)),
        ("shipping-above", True, free_shipping(51)),
        ("shipping-below", False, free_shipping(49)),
        ("legacy-slug", "red-bike", legacy_slug("Red  Bike")),
    ]
    failures = [{"id": name, "expected": expected, "actual": actual}
                for name, expected, actual in checks if actual != expected]
    print(json.dumps({"suite": "checkout", "failures": failures, "checked": len(checks)}, sort_keys=True))
    return int(bool(failures))


if __name__ == "__main__":
    sys.exit(main())
