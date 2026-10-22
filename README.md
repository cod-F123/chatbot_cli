# ChatBot CLI

A terminal chat client for any **OpenAI-compatible API**. Conversations are saved in a local SQLite database, replies are streamed as they are generated, and long conversations are summarized automatically so the context stays small.

## Features

- Multiple named chat sessions, stored with SQLAlchemy (SQLite by default)
- Streaming responses
- Automatic summarization once the context grows past a configurable token budget
- Works with any provider that speaks the OpenAI chat completions API (`PV_BASE_URL`)
- Separate, optional model for summaries
- Friendly handling of API errors, empty input, `Ctrl+C` and `Ctrl+D`
- Unit tests that run without network access or an API key

## Quick start

```bash
git clone https://github.com/cod-F123/chatbot_cli.git
cd chatbot_cli

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env             # then edit .env
python chat_bot.py
```

Python 3.11 or newer is recommended.

## Configuration

Settings are read from environment variables (a `.env` file is loaded automatically).

| Variable | Required | Default | Description |
|---|---|---|---|
| `MODEL_CHAT_NAME` | yes | – | Model used for the conversation |
| `API_KEY` | no | `OPENAI_API_KEY` | API key for the provider |
| `PV_BASE_URL` | no | OpenAI endpoint | Base URL of an OpenAI-compatible API |
| `MODEL_SUMMARIZE_NAME` | no | `MODEL_CHAT_NAME` | Model used to write summaries |
| `MT_FOR_START_SUMMARIZE` | no | `1000` | Summarize when the context reaches this many tokens |
| `DATABASE_URL` | no | `sqlite:///database.db` | SQLAlchemy database URL |
| `INCLUDE_STREAM_USAGE` | no | `true` | Request token usage while streaming (set `false` if your provider rejects `stream_options`) |

## Usage

```
____ ABDOLGHADER ____

[N] Create Session
[E] Exit

Sessions :
	[0]. Trip planning
	[1]. New Session

Choose an option :
```

- `N` creates a session (press Enter for the default title)
- a number opens that session
- inside a chat, `q` goes back to the menu
- `E`, `Ctrl+C` or `Ctrl+D` leaves the app

## How summarization works

After every reply the client looks at how many tokens the last request used (prompt + reply, as reported by the provider, or estimated at about 4 characters per token when the provider does not report usage). Once that reaches `MT_FOR_START_SUMMARIZE`, the whole history is sent to the summarization model and replaced, in one database transaction, by a single summary message. The next request then carries only the summary plus new messages.

If summarization fails, the reply is still delivered and the full history is kept; it is retried after the next message.

## Project structure

```
chat_bot.py            entry point (python chat_bot.py)
chatbot/
  config.py            environment settings and validation
  prompts.py           system and summarization prompts
  llm.py               streaming client wrapper around the OpenAI SDK
  repository.py        all database operations
  conversation.py      message history, token accounting, summarization
  cli.py               menu and chat screens
db/
  db.py                engine, session factory, table creation
  models.py            ChatSession and Message models
tests/                 unit tests (unittest)
```

The conversation logic depends only on a small repository and LLM interface, which is why the tests can use in-memory fakes instead of a real database or API.

## Running the tests

```bash
python -m unittest discover -s tests -t . -v
```

No API key or network connection is needed. The repository tests use an in-memory SQLite database.

## Notes and limitations

- Existing `database.db` files keep working; no schema migration is needed.
- Summaries are stored as `system` messages. A few OpenAI-compatible servers only accept a system message at the start of the conversation; if yours does, use a different provider or model for now.
- Token counts are cumulative per session and are informational; the summarization trigger uses the size of the latest context.
