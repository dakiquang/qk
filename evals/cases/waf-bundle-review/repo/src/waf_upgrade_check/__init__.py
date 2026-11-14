"""Check what breaks before you upgrade an AWS WAF managed rule group version."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("waf-upgrade-check")
except PackageNotFoundError:  # running from a source tree without installation
    __version__ = "0.0.0"
