from unittest import TestCase

from crm.translations import RUSSIAN_TRANSLATIONS, get_crm_translations


class TestCRMTranslations(TestCase):
	def test_crm_runtime_translations_are_russian_only(self):
		self.assertEqual(get_crm_translations("en"), {})
		self.assertEqual(get_crm_translations(None), {})
		translations = get_crm_translations("ru_RU")
		self.assertEqual(translations["Messaging"], "Обмен сообщениями")
		self.assertEqual(translations["Play"], "Воспроизвести")
		self.assertEqual(translations["Pause"], "Пауза")
		self.assertEqual(translations["Resume"], "Продолжить")

	def test_gateway_brand_is_not_exposed_in_customer_translations(self):
		self.assertNotIn("Wazzup", " ".join(RUSSIAN_TRANSLATIONS))
		self.assertNotIn("Wazzup", " ".join(RUSSIAN_TRANSLATIONS.values()))
