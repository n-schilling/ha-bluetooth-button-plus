"""Privacy: nothing personal in the repository, nothing leaves the house."""

from __future__ import annotations

import ast
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "custom_components" / "bluetooth_button_plus"
SCANNED = [
    *PACKAGE.rglob("*.py"),
    *PACKAGE.rglob("*.json"),
    *PACKAGE.rglob("*.yaml"),
    *(ROOT / "tests").rglob("*.py"),
    ROOT / "README.md",
    ROOT / "CHANGELOG.md",
]

MAC = re.compile(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b")
IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")

# Only made-up addresses belong in the repository: the test prefix and the
# documentation ranges of RFC 5737
ALLOWED_MAC_PREFIX = "AA:BB:CC:DD:EE:"
ALLOWED_IPV4_PREFIXES = ("192.0.2.", "198.51.100.", "203.0.113.")
ALLOWED_MAIL_DOMAINS = ("users.noreply.github.com", "example.com")
# File names that merely look like an address
NOT_MAILS = ("icon@2x.png",)

# The integration speaks Bluetooth only; none of these may be imported
NETWORK_MODULES = {"aiohttp", "httpx", "requests", "urllib", "socket", "http", "ssl"}


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_no_real_addresses() -> None:
    """No Bluetooth or IP address of a real device, no personal e-mail address."""
    for path in SCANNED:
        text = _text(path)
        for mac in MAC.findall(text):
            assert mac.upper().startswith(ALLOWED_MAC_PREFIX), f"{path}: {mac}"
        for ip in IPV4.findall(text):
            assert ip.startswith(ALLOWED_IPV4_PREFIXES), f"{path}: {ip}"
        for mail in EMAIL.findall(text):
            assert mail in NOT_MAILS or mail.endswith(ALLOWED_MAIL_DOMAINS), f"{path}: {mail}"


def test_no_network_libraries() -> None:
    """Nothing is sent anywhere: the package imports no network library."""
    for path in PACKAGE.rglob("*.py"):
        tree = ast.parse(_text(path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                assert name.split(".")[0] not in NETWORK_MODULES, f"{path}: {name}"


def test_no_diagnostics() -> None:
    """There is nothing to download: the integration offers no diagnostics."""
    assert not (PACKAGE / "diagnostics.py").exists()
