import unittest

from chatbot.config import (
    DEFAULT_DATABASE_URL,
    DEFAULT_SUMMARY_THRESHOLD,
    ConfigError,
    load_settings,
)


class LoadSettingsTests(unittest.TestCase):
    def test_model_name_is_required(self):
        with self.assertRaises(ConfigError):
            load_settings({"API_KEY": "k"})

    def test_defaults(self):
        settings = load_settings({"MODEL_CHAT_NAME": "chat-model"})
        self.assertEqual(settings.chat_model, "chat-model")
        self.assertEqual(settings.summarize_model, "chat-model")
        self.assertEqual(settings.summarize_threshold, DEFAULT_SUMMARY_THRESHOLD)
        self.assertEqual(settings.database_url, DEFAULT_DATABASE_URL)
        self.assertIsNone(settings.api_key)
        self.assertIsNone(settings.base_url)
        self.assertTrue(settings.include_stream_usage)

    def test_threshold_from_env_is_an_int(self):
        # Regression: env values are strings, and "int + str" used to raise TypeError.
        settings = load_settings({"MODEL_CHAT_NAME": "m", "MT_FOR_START_SUMMARIZE": "250"})
        self.assertEqual(settings.summarize_threshold, 250)
        self.assertIsInstance(settings.summarize_threshold, int)

    def test_invalid_threshold_is_rejected(self):
        for bad in ("abc", "0", "-5"):
            with self.subTest(value=bad):
                with self.assertRaises(ConfigError):
                    load_settings({"MODEL_CHAT_NAME": "m", "MT_FOR_START_SUMMARIZE": bad})

    def test_separate_summarize_model(self):
        settings = load_settings({"MODEL_CHAT_NAME": "big", "MODEL_SUMMARIZE_NAME": "small"})
        self.assertEqual(settings.summarize_model, "small")

    def test_empty_optional_values_become_none(self):
        settings = load_settings({"MODEL_CHAT_NAME": "m", "API_KEY": "", "PV_BASE_URL": ""})
        self.assertIsNone(settings.api_key)
        self.assertIsNone(settings.base_url)

    def test_stream_usage_can_be_disabled(self):
        settings = load_settings({"MODEL_CHAT_NAME": "m", "INCLUDE_STREAM_USAGE": "false"})
        self.assertFalse(settings.include_stream_usage)


if __name__ == "__main__":
    unittest.main()
