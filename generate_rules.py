#!/usr/bin/env python3
"""Generate Clash-compatible PT site domain rules from upstream site configs."""

from __future__ import annotations

import concurrent.futures
import ipaddress
import json
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


API_URL = (
    "https://api.github.com/repos/mantou568/pre-dessert-sites/contents/"
    "site_config/sites?ref=main&per_page=1000"
)
RAW_FILE_BASE = (
    "https://raw.githubusercontent.com/mantou568/pre-dessert-sites/main/"
    "site_config/sites/"
)
OUTPUT_FILE = Path(__file__).resolve().parent / "PrivateTracker.list"
REQUEST_TIMEOUT_SECONDS = 30
MAX_DOWNLOAD_WORKERS = 8
USER_AGENT = "Fone-1-pt-rules-generator"
DOMAIN_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$", re.IGNORECASE)


def fetch_json(url: str) -> Any:
    """Fetch and parse one JSON response, failing with a useful message."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Failed to fetch or parse {url}: {exc}") from exc


def list_site_files() -> list[str]:
    """Return the JSON filenames reported by the upstream directory API."""
    entries = fetch_json(API_URL)
    if not isinstance(entries, list):
        raise RuntimeError("Upstream directory response is not a JSON list")

    filenames = [
        entry["name"]
        for entry in entries
        if isinstance(entry, dict)
        and entry.get("type") == "file"
        and isinstance(entry.get("name"), str)
        and entry["name"].lower().endswith(".json")
    ]
    if not filenames:
        raise RuntimeError("Upstream site directory contains no JSON files")
    return sorted(filenames)


def extract_domain(filename: str) -> str | None:
    """Extract and normalize a config's top-level domain, if present."""
    url = RAW_FILE_BASE + urllib.parse.quote(filename, safe="")
    config = fetch_json(url)
    if not isinstance(config, dict):
        raise RuntimeError(f"{filename} does not contain a JSON object")
    if "domain" not in config:
        return None

    value = config["domain"]
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"{filename} has an empty or non-string domain")

    address = value.strip()
    parsed = urllib.parse.urlsplit(address if "://" in address else f"//{address}")
    if parsed.scheme and parsed.scheme.lower() not in {"http", "https"}:
        raise RuntimeError(f"{filename} uses an unsupported URL scheme: {parsed.scheme}")
    if parsed.username or parsed.password:
        raise RuntimeError(f"{filename} domain unexpectedly contains credentials")

    try:
        hostname = parsed.hostname
        # Accessing port validates malformed port values even though ports are omitted.
        _ = parsed.port
    except ValueError as exc:
        raise RuntimeError(f"{filename} has an invalid domain URL: {value}") from exc
    if not hostname:
        raise RuntimeError(f"{filename} has no hostname in domain: {value}")

    hostname = hostname.rstrip(".").lower()
    try:
        ipaddress.ip_address(hostname)
        # Clash DOMAIN rules accept hostnames; keep IPv4 literals as domain values.
        return hostname
    except ValueError:
        pass

    try:
        hostname = hostname.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise RuntimeError(f"{filename} has an invalid internationalized hostname") from exc

    labels = hostname.split(".")
    if len(labels) < 2 or any(not DOMAIN_LABEL.fullmatch(label) for label in labels):
        raise RuntimeError(f"{filename} has an invalid hostname: {hostname}")
    return hostname


def write_rules(domains: list[str]) -> None:
    """Atomically replace the output only after all source data is validated."""
    if not domains:
        raise RuntimeError("No valid PT site domains were found; keeping existing rules")

    content = "".join(f"DOMAIN,{domain}\n" for domain in domains)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="\n", dir=OUTPUT_FILE.parent, delete=False
    ) as temp_file:
        temp_file.write(content)
        temporary_path = Path(temp_file.name)
    temporary_path.replace(OUTPUT_FILE)


def main() -> None:
    filenames = list_site_files()
    domains: list[str] = []
    failures: list[str] = []

    # Fetch independent raw JSON files concurrently while keeping the API request single.
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_DOWNLOAD_WORKERS) as pool:
        futures = {pool.submit(extract_domain, name): name for name in filenames}
        for future in concurrent.futures.as_completed(futures):
            filename = futures[future]
            try:
                domain = future.result()
                if domain is not None:
                    domains.append(domain)
            except Exception as exc:  # Collect all failed filenames for useful CI logs.
                failures.append(f"{filename}: {exc}")

    if failures:
        details = "\n".join(f"- {failure}" for failure in sorted(failures))
        raise RuntimeError(f"Failed to process {len(failures)} of {len(filenames)} files:\n{details}")

    rules = sorted(set(domains))
    write_rules(rules)
    print(f"Read {len(filenames)} JSON files; generated {len(rules)} unique domain rules.")


if __name__ == "__main__":
    main()
