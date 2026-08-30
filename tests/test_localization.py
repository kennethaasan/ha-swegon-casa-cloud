"""Validate integration localization without importing Home Assistant."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components/swegon_casa_cloud"


def _leaf_paths(value: object, prefix: tuple[str, ...] = ()) -> set[tuple[str, ...]]:
    if isinstance(value, dict):
        paths: set[tuple[str, ...]] = set()
        for key, child in value.items():
            paths |= _leaf_paths(child, (*prefix, key))
        return paths
    return {prefix}


class LocalizationTest(unittest.TestCase):
    def test_english_and_bokmal_have_identical_keys(self) -> None:
        english = json.loads((COMPONENT / "translations/en.json").read_text())
        bokmal = json.loads((COMPONENT / "translations/nb.json").read_text())
        self.assertEqual(_leaf_paths(english), _leaf_paths(bokmal))

    def test_mode_values_are_language_neutral(self) -> None:
        path = COMPONENT / "const.py"
        spec = importlib.util.spec_from_file_location("swegon_const", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(
            {"travelling", "away", "home", "home_plus", "boost"},
            set(module.MODE_TO_WRITE_VALUE),
        )


if __name__ == "__main__":
    unittest.main()
