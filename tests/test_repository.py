"""Repository tests against an in-memory SQLite database (needs SQLAlchemy)."""

import unittest

from sqlalchemy.pool import StaticPool

from chatbot.repository import Repository
from db.db import create_tables, make_engine, make_session_factory
from db.models import DEFAULT_TITLE


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        # StaticPool keeps a single connection, so the in-memory database
        # survives across the short-lived sessions the repository opens.
        self.engine = make_engine(
            "sqlite://",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        create_tables(self.engine)
        self.repo = Repository(make_session_factory(self.engine))

    def tearDown(self):
        self.engine.dispose()

    # -- sessions --------------------------------------------------------------

    def test_blank_title_gets_the_default(self):
        for blank in ("", "   "):
            with self.subTest(title=blank):
                created = self.repo.create_session(blank)
                self.assertEqual(created.title, DEFAULT_TITLE)

    def test_custom_title_is_trimmed_and_kept(self):
        self.assertEqual(self.repo.create_session("  Plans  ").title, "Plans")

    def test_sessions_are_listed_in_creation_order(self):
        first = self.repo.create_session("a")
        second = self.repo.create_session("b")
        listed = self.repo.list_sessions()
        self.assertEqual([s.session_id for s in listed], [first.session_id, second.session_id])
        self.assertEqual([s.title for s in listed], ["a", "b"])

    # -- messages --------------------------------------------------------------

    def test_messages_come_back_in_order_for_their_own_session_only(self):
        one = self.repo.create_session("one").session_id
        two = self.repo.create_session("two").session_id
        self.repo.add_message(one, "user", "hi")
        self.repo.add_message(two, "user", "other")
        self.repo.add_message(one, "assistant", "hello")

        self.assertEqual(
            self.repo.get_messages(one),
            [
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "hello"},
            ],
        )

    def test_all_role_names_fit(self):
        # "assistant" is longer than the old String(4) column.
        sid = self.repo.create_session("r").session_id
        for role in ("system", "user", "assistant"):
            self.repo.add_message(sid, role, role)
        self.assertEqual(
            [m["role"] for m in self.repo.get_messages(sid)], ["system", "user", "assistant"]
        )

    # -- tokens ----------------------------------------------------------------

    def test_tokens_accumulate(self):
        sid = self.repo.create_session("t").session_id
        self.repo.add_tokens(sid, 40)
        self.repo.add_tokens(sid, 2)
        (session,) = self.repo.list_sessions()
        self.assertEqual(session.total_token, 42)

    # -- summaries ---------------------------------------------------------------

    def test_replace_with_summary_only_touches_that_session(self):
        one = self.repo.create_session("one").session_id
        two = self.repo.create_session("two").session_id
        self.repo.add_message(one, "user", "q")
        self.repo.add_message(one, "assistant", "a")
        self.repo.add_message(two, "user", "keep me")

        self.repo.replace_with_summary(one, "the summary")

        self.assertEqual(
            self.repo.get_messages(one), [{"role": "system", "content": "the summary"}]
        )
        self.assertEqual(
            self.repo.get_messages(two), [{"role": "user", "content": "keep me"}]
        )


if __name__ == "__main__":
    unittest.main()
