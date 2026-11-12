"""Load model instructions and tool descriptions from packaged UTF-8 files."""

import json
from importlib.resources import files

_RESOURCES = files(__package__)

POLICY = _RESOURCES.joinpath("policy.txt").read_text(encoding="utf-8")
ROUTE = _RESOURCES.joinpath("route.txt").read_text(encoding="utf-8")
FINAL_ANSWER = _RESOURCES.joinpath("answer.txt").read_text(encoding="utf-8")
REPAIR = _RESOURCES.joinpath("repair.txt").read_text(encoding="utf-8")
TOOL_DESCRIPTIONS = json.loads(
    _RESOURCES.joinpath("tool_descriptions.json").read_text(encoding="utf-8")
)
