import unittest

from chatbot.conversation import Conversation
from chatbot.prompts import SUMMARY_PREFIX, SYSTEM_PROMPT
from tests.fakes import FakeLLM, FakeRepository


class ConversationTestCase(unittest.TestCase):
    def setUp(self):
        self.repo = FakeRepository()
        self.session_id = self.repo.create_session("test").session_id

    def make(self, llm, threshold=1000):
        return Conversation(self.repo, llm, self.session_id, threshold)


class SendTests(ConversationTestCase):
    def test_reply_is_returned_and_both_messages_are_stored(self):
        llm = FakeLLM([("Hello there", 40)])
        conversation = self.make(llm)

        reply = conversation.send("Hi")

        self.assertEqual(reply, "Hello there")
        self.assertEqual(
            self.repo.get_messages(self.session_id),
            [
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello there"},
            ],
        )

    def test_streamed_text_is_forwarded(self):
        seen = []
        self.make(FakeLLM([("abc", 10)])).send("hi", on_delta=seen.append)
        self.assertEqual(seen, ["abc"])

    def test_system_prompt_is_first_and_not_persisted(self):
        llm = FakeLLM([("ok", 10)])
        self.make(llm).send("hi")

        self.assertEqual(llm.chat_calls[0][0], {"role": "system", "content": SYSTEM_PROMPT})
        self.assertTrue(
            all(m["role"] != "system" for m in self.repo.get_messages(self.session_id))
        )

    def test_existing_history_is_loaded(self):
        self.repo.add_message(self.session_id, "user", "earlier question")
        self.repo.add_message(self.session_id, "assistant", "earlier answer")
        llm = FakeLLM([("new answer", 10)])

        self.make(llm).send("new question")

        sent = llm.chat_calls[0]
        self.assertEqual(
            [m["content"] for m in sent[1:]],
            ["earlier question", "earlier answer", "new question"],
        )

    def test_tokens_accumulate_in_the_repository(self):
        conversation = self.make(FakeLLM([("a", 30), ("b", 50)]))
        conversation.send("one")
        conversation.send("two")
        self.assertEqual(self.repo.tokens[self.session_id], 80)

    def test_empty_reply_is_not_stored(self):
        self.make(FakeLLM([("", 5)])).send("hi")
        self.assertEqual(
            self.repo.get_messages(self.session_id), [{"role": "user", "content": "hi"}]
        )


class SummarizationTests(ConversationTestCase):
    def test_no_summary_below_threshold(self):
        llm = FakeLLM([("a", 99)])
        self.make(llm, threshold=100).send("hi")
        self.assertEqual(llm.summarize_calls, [])
        self.assertEqual(len(self.repo.get_messages(self.session_id)), 2)

    def test_threshold_applies_to_context_size_not_cumulative_total(self):
        # Two replies of 60 tokens: cumulative 120 > 100, but the context is only 60.
        llm = FakeLLM([("a", 60), ("b", 60)])
        conversation = self.make(llm, threshold=100)
        conversation.send("one")
        conversation.send("two")
        self.assertEqual(llm.summarize_calls, [])

    def test_history_is_replaced_by_a_summary_at_the_threshold(self):
        llm = FakeLLM([("answer", 100)], summary="  they talked  ")
        conversation = self.make(llm, threshold=100)

        conversation.send("question")

        expected = SUMMARY_PREFIX + "they talked"
        self.assertEqual(
            self.repo.get_messages(self.session_id),
            [{"role": "system", "content": expected}],
        )
        self.assertEqual(
            conversation.messages,
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "system", "content": expected},
            ],
        )
        self.assertEqual(conversation.context_tokens, 0)

    def test_summary_input_excludes_base_prompt_but_has_the_exchange(self):
        llm = FakeLLM([("answer", 500)])
        self.make(llm, threshold=100).send("question")

        self.assertEqual(
            llm.summarize_calls[0],
            [
                {"role": "user", "content": "question"},
                {"role": "assistant", "content": "answer"},
            ],
        )

    def test_next_request_is_sent_with_the_summary_instead_of_history(self):
        llm = FakeLLM([("answer", 500), ("second answer", 10)], summary="the gist")
        conversation = self.make(llm, threshold=100)
        conversation.send("question")
        conversation.send("follow-up")

        sent = llm.chat_calls[1]
        self.assertEqual(
            [m["content"] for m in sent[1:]],
            [SUMMARY_PREFIX + "the gist", "follow-up"],
        )

    def test_summarization_failure_keeps_history_and_still_returns_reply(self):
        llm = FakeLLM([("answer", 500)], summarize_error=RuntimeError("boom"))
        with self.assertLogs("chatbot.conversation", level="WARNING"):
            reply = self.make(llm, threshold=100).send("question")

        self.assertEqual(reply, "answer")
        self.assertEqual(len(self.repo.get_messages(self.session_id)), 2)

    def test_blank_summary_keeps_history(self):
        llm = FakeLLM([("answer", 500)], summary="   ")
        self.make(llm, threshold=100).send("question")
        self.assertEqual(len(self.repo.get_messages(self.session_id)), 2)


if __name__ == "__main__":
    unittest.main()
