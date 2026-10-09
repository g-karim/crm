"""Check translations through Frappe's compiled catalogue, as CRM boot does."""

import ast
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po
from frappe.gettext.translate import get_translations_from_mo

from crm.touch_tracking_channels import CHANNEL_RULES
from crm.touch_tracking_ui import RULE_LABELS


class TestTouchTranslations(TestCase):
	def test_touch_settings_messages_survive_native_catalogue_compilation(self):
		root = Path(__file__).resolve().parents[2]
		keys = set(RULE_LABELS.values()) | set(CHANNEL_RULES.values())
		for relative in (
			"frontend/src/components/Settings/TouchSettings.vue",
			"frontend/src/components/TouchCell.vue",
			"frontend/src/utils/touchTracking.js",
		):
			content = (root / relative).read_text()
			keys.update(re.findall(r"__\(\s*'([^']*)'", content))
			keys.update(re.findall(r"new Error\('([^']*)'\)", content))
		keys.add("Could not load touch settings")  # Dynamic error fallback.
		for relative in (
			"crm/touch_tracking_ui.py",
			"crm/touch_tracking_internal.py",
			"crm/touch_tracking_channels.py",
			"crm/fcrm/doctype/crm_touch_settings/crm_touch_settings.py",
		):
			for node in ast.walk(ast.parse((root / relative).read_text())):
				if isinstance(node, ast.Dict):
					for key, value in zip(node.keys, node.values, strict=True):
						if (
							isinstance(key, ast.Constant)
							and key.value in ("label", "description")
							and isinstance(value, ast.Constant)
							and isinstance(value.value, str)
						):
							keys.add(value.value)
				if (
					isinstance(node, ast.Call)
					and isinstance(node.func, ast.Attribute)
					and node.func.attr == "_"
					and node.args
					and isinstance(node.args[0], ast.Constant)
					and isinstance(node.args[0].value, str)
				):
					keys.add(node.args[0].value)

		with (root / "crm/locale/ru.po").open("rb") as stream:
			catalogue = read_po(stream)
		with TemporaryDirectory() as directory:
			binary = Path(directory) / "crm.mo"
			with binary.open("wb") as stream:
				write_mo(stream, catalogue)
			with patch("frappe.gettext.translate.get_mo_path", return_value=binary):
				translations = get_translations_from_mo("ru", "crm")

		for key in keys:
			with self.subTest(key=key):
				translation = translations.get(key, "")
				self.assertRegex(translation, r"[А-Яа-яЁё]")
				self.assertEqual(re.findall(r"\{\d+\}", key), re.findall(r"\{\d+\}", translation))
