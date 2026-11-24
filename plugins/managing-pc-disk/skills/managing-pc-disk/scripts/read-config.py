"""Read optional local disk-management settings as data."""
import json
import os
from pathlib import Path
import sys

path = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
path /= "managing-pc-disk/config.json"

try:
    with path.open(encoding="utf-8") as config_file:
        config = json.load(config_file)
except FileNotFoundError:
    sys.exit(0)
except (OSError, ValueError) as error:
    sys.exit(f"Could not read disk management settings: {error}")

if not isinstance(config, dict):
    sys.exit("Disk management settings must be a JSON object")

key = sys.argv[1]
values = [config.get(key, "")] if key == "workspace_note" else config.get(key, [])
if not isinstance(values, list) or any(
    not isinstance(value, str) or any(char in value for char in "\r\n\0")
    for value in values
):
    sys.exit(f"Invalid disk management setting: {key}")

for value in values:
    if key == "workspace_note":
        print(value)
        continue
    directory = os.path.abspath(os.path.expanduser(value)) if value.startswith(("/", "~/")) else ""
    if not directory or directory == "/":
        sys.exit(f"Expected an absolute directory or ~/ path in {key}")
    print(directory)
