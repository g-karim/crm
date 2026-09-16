from unittest import TestCase

from crm.translations import RUSSIAN_TRANSLATIONS, get_crm_translations


class TestCRMTranslations(TestCase):
	def test_crm_runtime_translations_are_russian_only(self):
		self.assertEqual(get_crm_translations("en"), {})
		self.assertEqual(get_crm_translations(None), {})
		translations = get_crm_translations("ru_RU")
		self.assertEqual(translations["Messaging"], "Обмен сообщениями")
		self.assertEqual(translations["Try Again"], "Повторить")
		self.assertEqual(translations["Play"], "Воспроизвести")
		self.assertEqual(translations["Pause"], "Пауза")
		self.assertEqual(translations["Resume"], "Продолжить")
		self.assertEqual(
			translations["Check sending conversation"],
			"Проверить переписку отправки",
		)
		self.assertEqual(translations["Cancel"], "Отменить")
		self.assertEqual(
			translations["Could not move attachments to the selected conversation."],
			"Не удалось перенести вложения в выбранную переписку.",
		)
		self.assertEqual(
			translations[
				"The Avito integration is not configured. Enter the Client ID and Client Secret in the Avito channel settings, then connect the channel. The message was saved locally with an error status."
			],
			"Интеграция Avito не настроена. Укажите Client ID и Client Secret в настройках канала Avito, затем подключите канал. Сообщение сохранено локально со статусом ошибки.",
		)

	def test_gateway_brand_is_not_exposed_in_customer_translations(self):
		self.assertNotIn("Wazzup", " ".join(RUSSIAN_TRANSLATIONS))
		self.assertNotIn("Wazzup", " ".join(RUSSIAN_TRANSLATIONS.values()))

	def test_user_facing_avito_errors_have_runtime_translations(self):
		user_facing = {
			"This account does not have access to the Avito Messenger API. Switch to a subscription that includes the Messenger API, then try again.",
			"Avito credentials belong to another account. Create a separate channel for it.",
			"This Avito account is already connected to another channel.",
			"Avito account identity received.",
			"Avito V3 webhook registered.",
			"Avito webhook status received.",
			"Avito webhook removed.",
			"Avito request failed.",
			"Avito image size must be between 1 byte and 24 MiB.",
			"Avito image format could not be reliably confirmed.",
			"Avito accepted the image request without a provider message id; delivery is ambiguous.",
			"Avito message text cannot exceed 1000 characters.",
			"Avito rejected the delete request.",
			"Avito delete result is unknown.",
		}
		translations = get_crm_translations("ru_RU")
		self.assertEqual(user_facing - translations.keys(), set())
		self.assertTrue(all(translations[source] != source for source in user_facing))
