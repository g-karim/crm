from unittest import TestCase

from crm.translations import RUSSIAN_TRANSLATIONS, get_crm_translations


class TestCRMTranslations(TestCase):
	def test_crm_runtime_translations_are_russian_only(self):
		self.assertEqual(get_crm_translations("en"), {})
		self.assertEqual(get_crm_translations(None), {})
		self.assertEqual(get_crm_translations("ru_RU")["Messaging"], "Обмен сообщениями")
		self.assertEqual(get_crm_translations("ru_RU")["Call Analysis"], "Анализ звонков")
		self.assertEqual(get_crm_translations("ru_RU")["Summary"], "Краткий итог")
		self.assertEqual(get_crm_translations("ru_RU")["Key Points"], "Главное")
		self.assertEqual(get_crm_translations("ru_RU")["Next Steps"], "Следующие шаги")
		self.assertEqual(get_crm_translations("ru_RU")["Transcript"], "Расшифровка")
		self.assertEqual(get_crm_translations("ru_RU")["Completed"], "Готово")

	def test_gateway_brand_is_not_exposed_in_customer_translations(self):
		self.assertNotIn("Wazzup", " ".join(RUSSIAN_TRANSLATIONS))
		self.assertNotIn("Wazzup", " ".join(RUSSIAN_TRANSLATIONS.values()))
