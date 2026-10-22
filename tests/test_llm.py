import unittest
from types import SimpleNamespace

from chatbot.config import Settings
from chatbot.llm import LLMClient, estimate_tokens
from chatbot.prompts import SUMMARIZE_PROMPT


def delta_chunk(text):
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=text))], usage=None
    )


def usage_chunk(total_tokens):
    # Providers send usage in a final chunk whose ``choices`` list is empty.
    return SimpleNamespace(choices=[], usage=SimpleNamespace(total_tokens=total_tokens))


class FakeOpenAI:
    """Just enough of the OpenAI client for ``LLMClient``."""

    def __init__(self, chunks=None, summary_text="summary"):
        self.chunks = chunks or []
        self.summary_text = summary_text
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("stream"):
            return iter(self.chunks)
        message = SimpleNamespace(content=self.summary_text)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def make_settings(**overrides):
    values = dict(chat_model="chat-model", summarize_model="summary-model")
    values.update(overrides)
    return Settings(**values)


class StreamChatTests(unittest.TestCase):
    def test_collects_text_and_forwards_deltas(self):
        fake = FakeOpenAI([delta_chunk("Hel"), delta_chunk(None), delta_chunk("lo")])
        seen = []

        result = LLMClient(make_settings(), client=fake).stream_chat(
            [{"role": "user", "content": "hi"}], on_delta=seen.append
        )

        self.assertEqual(result.text, "Hello")
        self.assertEqual(seen, ["Hel", "lo"])

    def test_final_usage_chunk_with_empty_choices_is_handled(self):
        # Regression: ``chunk.choices[0]`` raised IndexError on this chunk.
        fake = FakeOpenAI([delta_chunk("Hi"), usage_chunk(321)])

        result = LLMClient(make_settings(), client=fake).stream_chat(
            [{"role": "user", "content": "hi"}]
        )

        self.assertEqual(result.text, "Hi")
        self.assertEqual(result.total_tokens, 321)

    def test_requests_usage_when_enabled(self):
        fake = FakeOpenAI([delta_chunk("x")])
        LLMClient(make_settings(), client=fake).stream_chat([])

        call = fake.calls[0]
        self.assertEqual(call["model"], "chat-model")
        self.assertTrue(call["stream"])
        self.assertEqual(call["stream_options"], {"include_usage": True})

    def test_usage_option_is_omitted_when_disabled(self):
        fake = FakeOpenAI([delta_chunk("x")])
        LLMClient(make_settings(include_stream_usage=False), client=fake).stream_chat([])

        self.assertNotIn("stream_options", fake.calls[0])

    def test_estimates_tokens_when_provider_reports_none(self):
        messages = [{"role": "user", "content": "a" * 40}]
        fake = FakeOpenAI([delta_chunk("b" * 20)])

        result = LLMClient(make_settings(), client=fake).stream_chat(messages)

        self.assertEqual(result.total_tokens, estimate_tokens(messages, "b" * 20))
        self.assertEqual(result.total_tokens, 15)

    def test_estimate_is_at_least_one(self):
        self.assertEqual(estimate_tokens([], ""), 1)


class SummarizeTests(unittest.TestCase):
    def test_uses_summarize_model_and_instruction(self):
        fake = FakeOpenAI(summary_text="the summary")
        history = [{"role": "user", "content": "hello"}]

        summary = LLMClient(make_settings(), client=fake).summarize(history)

        self.assertEqual(summary, "the summary")
        call = fake.calls[0]
        self.assertEqual(call["model"], "summary-model")
        self.assertEqual(call["messages"][0], {"role": "system", "content": SUMMARIZE_PROMPT})
        self.assertEqual(call["messages"][1:], history)
        self.assertNotIn("stream", call)

    def test_missing_content_becomes_empty_string(self):
        fake = FakeOpenAI(summary_text=None)
        self.assertEqual(LLMClient(make_settings(), client=fake).summarize([]), "")


if __name__ == "__main__":
    unittest.main()
