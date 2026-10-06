from unittest import TestCase

from crm.translations import get_crm_translations


class TestCRMTranslations(TestCase):
	def test_crm_runtime_translations_are_russian_only(self):
		self.assertEqual(get_crm_translations("en"), {})
		self.assertEqual(get_crm_translations(None), {})
		translations = get_crm_translations("ru_RU")
		self.assertEqual(translations["Messaging"], "Обмен сообщениями")
		self.assertEqual(translations["Call Analysis"], "Анализ звонков")
		self.assertEqual(translations["Summary"], "Краткий итог")
		self.assertEqual(translations["Key Points"], "Главное")
		self.assertEqual(translations["Next Steps"], "Следующие шаги")
		self.assertEqual(translations["Transcript"], "Расшифровка")
		self.assertEqual(translations["Completed"], "Готово")
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

	def test_wazzup_administration_and_unknown_delivery_are_translated(self):
		translations = get_crm_translations("ru")
		self.assertEqual(translations["Wazzup"], "Wazzup")
		self.assertEqual(translations["Connection Not Checked"], "Подключение не проверено")
		self.assertEqual(
			translations[
				"The provider may have accepted the message, but CRM did not receive a definitive result. Retrying may create a duplicate."
			],
			"Провайдер мог уже принять сообщение, но CRM не получила однозначный результат. Повторная отправка может создать дубликат.",
		)
		user_facing = {
			"Provider message delivery result is unknown.",
			"Provider rejected the message.",
			"Provider authentication failed.",
			"The messenger channel is unavailable.",
			"The message text is too long.",
			"The recipient is not configured.",
			"This channel supports text messages only.",
			"This channel supports individual chats only.",
			"The message text is required.",
			"Provider rate limit reached.",
			"Message accepted by provider.",
			"Channel can send messages.",
			"The provider reported a message delivery failure.",
		}
		for source in user_facing:
			with self.subTest(source=source):
				self.assertIn(source, translations)
				self.assertNotEqual(translations[source], source)

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

	def test_attachment_caption_and_size_limits_have_runtime_translations(self):
		user_facing = {
			"This channel cannot send text and an attachment together. Send them as separate messages.",
			"Text and attachments must be sent separately.",
			"The attachment exceeds the selected channel size limit of {0} MB.",
			"Send the text and attachment as separate messages.",
			"Send one Wazzup attachment without text.",
			"The attachment is unavailable for Wazzup.",
			"This attachment type cannot be sent.",
			"This channel cannot send voice messages.",
			"Wazzup supports MP4 video files only.",
			"The selected channel supports MP4 video files only.",
			"The attachment exceeds the Wazzup size limit.",
			"A public HTTPS site URL is required to send Wazzup attachments.",
			"Site encryption key is not configured.",
			"Reply target is unavailable for this conversation.",
			"Attachment content was rejected.",
			"Attachment could not be stored.",
		}
		translations = get_crm_translations("ru")
		self.assertEqual(user_facing - translations.keys(), set())
		self.assertTrue(all(translations[source] != source for source in user_facing))

	def test_wazzup_connection_and_diagnostic_labels_are_translated(self):
		user_facing = {
			"Telegram personal chats", "Wazzup API key", "Wazzup channel UUID",
			"API key source", "Load Wazzup channels", "Available Wazzup channels",
			"Active in CRM", "Check saved configuration", "Saved configuration diagnostics", "Configuration Checked", "Wazzup diagnostics refreshed.",
			"API access", "Selected Wazzup channel", "Webhook subscription",
			"CRM webhook configuration", "Actual incoming event", "No event observed",
			"Event received", "Not checked", "Could not verify", "Verified",
			"The Wazzup API key is invalid.", "The Wazzup API request is not permitted.",
			"The Wazzup API is temporarily unavailable. Try checking again.",
			"The Wazzup API rate limit was reached. Try checking again.",
			"The Wazzup API returned an unexpected response.",
			"The Wazzup API endpoint is not supported.",
			"Enter the Wazzup channel UUID, not its phone number or username.",
			"The selected channel is not available for this Wazzup API key.",
			"The selected Wazzup channel uses a different messenger.",
			"The selected Wazzup channel is not active.",
			"The Wazzup channel state could not be verified.",
			"The Wazzup webhook address or message subscription does not match this CRM.",
			"Configure a public HTTPS site URL and webhook secret before receiving Wazzup events.",
			"Channel settings changed during verification. Check the channel again.",
			"Configuration verified. Webhook delivery has not been verified.",
			"Select a Wazzup channel.", "Select a Wazzup channel for the API key.",
			"Enter a Wazzup channel UUID.", "Wazzup channels support API keys only.",
			"The messenger identity of a Wazzup channel with conversations cannot be changed. Create a separate channel.",
			"Wazzup configuration is invalid. Check the saved channel settings.",
			"Webhook events: {0} pending, {1} failed.",
			"Attachments: {0} pending, {1} failed.",
			"The Shared Webhook Secret must match the crmKey configured for the Wazzup integration; it is different from the Wazzup API key.",
		}
		translations = get_crm_translations("ru")
		self.assertEqual(user_facing - translations.keys(), set())
		self.assertTrue(all(translations[source] != source for source in user_facing))
