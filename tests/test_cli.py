import unittest

from chatbot.cli import ChatBotApp, OpenAIError, is_exit_command
from tests.fakes import FakeLLM, FakeRepository


class ScriptedIO:
    """Feeds scripted answers to ``input`` and records everything printed."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.prompts = []
        self.out = []

    def input(self, prompt=""):
        self.prompts.append(prompt)
        if not self.answers:
            raise EOFError
        answer = self.answers.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        return answer

    def print(self, *args, end="\n", **_kwargs):
        self.out.append("".join(str(a) for a in args) + end)

    @property
    def text(self):
        return "".join(self.out)


def make_app(answers, replies=()):
    io = ScriptedIO(answers)
    repo = FakeRepository()
    llm = FakeLLM(replies)
    app = ChatBotApp(repo, llm, 1000, input_fn=io.input, print_fn=io.print)
    return app, repo, llm, io


class ExitCommandTests(unittest.TestCase):
    def test_q_in_any_case_and_with_spaces(self):
        for text in ("q", "Q", "  q  "):
            with self.subTest(text=text):
                self.assertTrue(is_exit_command(text))

    def test_other_text_is_not_an_exit(self):
        for text in ("quit", "qq", "", "hello"):
            with self.subTest(text=text):
                self.assertFalse(is_exit_command(text))


class ChatScreenTests(unittest.TestCase):
    def test_messages_keep_their_original_casing(self):
        # Regression: user input used to be lower-cased before being sent.
        app, repo, llm, _io = make_app(["Hello World", "q"], replies=[("Hi!", 10)])
        session_id = repo.create_session("t").session_id

        app.run_chat(session_id)

        self.assertEqual(llm.chat_calls[0][-1], {"role": "user", "content": "Hello World"})

    def test_blank_input_is_ignored(self):
        app, repo, llm, _io = make_app(["", "   ", "q"])
        app.run_chat(repo.create_session("t").session_id)
        self.assertEqual(llm.chat_calls, [])

    def test_reply_is_printed(self):
        app, repo, _llm, io = make_app(["hi", "q"], replies=[("Hello back", 10)])
        app.run_chat(repo.create_session("t").session_id)
        self.assertIn("Hello back", io.text)

    def test_model_errors_do_not_end_the_chat(self):
        app, repo, llm, io = make_app(
            ["first", "second", "q"],
            replies=[OpenAIError("rate limited"), ("recovered", 10)],
        )
        app.run_chat(repo.create_session("t").session_id)

        self.assertIn("rate limited", io.text)
        self.assertIn("recovered", io.text)
        self.assertEqual(len(llm.chat_calls), 2)

    def test_ctrl_c_while_a_reply_streams_keeps_the_chat_open(self):
        app, repo, llm, io = make_app(
            ["first", "second", "q"],
            replies=[KeyboardInterrupt(), ("fine", 10)],
        )
        app.run_chat(repo.create_session("t").session_id)

        self.assertIn("[interrupted]", io.text)
        self.assertIn("fine", io.text)
        self.assertEqual(len(llm.chat_calls), 2)

    def test_end_of_input_leaves_the_chat(self):
        app, repo, _llm, _io = make_app([EOFError()])
        app.run_chat(repo.create_session("t").session_id)  # must not raise

    def test_ctrl_c_leaves_the_chat(self):
        app, repo, _llm, _io = make_app([KeyboardInterrupt()])
        app.run_chat(repo.create_session("t").session_id)  # must not raise


class MenuTests(unittest.TestCase):
    def test_create_open_chat_and_exit(self):
        app, repo, llm, io = make_app(
            ["n", "My title", "0", "hi", "q", "e"], replies=[("hello", 10)]
        )

        app.run()

        self.assertEqual([s.title for s in repo.list_sessions()], ["My title"])
        self.assertEqual(llm.chat_calls[0][-1]["content"], "hi")
        self.assertIn("[0]. My title", io.text)
        self.assertIn("Good Luck", io.text)

    def test_invalid_options_are_reported(self):
        app, _repo, _llm, io = make_app(["x", "9", "e"])
        app.run()
        self.assertIn("'x' is not a valid option", io.text)
        self.assertIn("'9' is not a valid option", io.text)

    def test_empty_state_is_shown(self):
        app, _repo, _llm, io = make_app(["e"])
        app.run()
        self.assertIn("Sessions Empty", io.text)

    def test_end_of_input_exits_the_menu(self):
        app, _repo, _llm, _io = make_app([])
        app.run()  # must not raise


if __name__ == "__main__":
    unittest.main()
