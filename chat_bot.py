from openai import OpenAI
from sqlalchemy.exc import SQLAlchemyError
from db.db import create_tabels, get_session
from db.models import ChatSession, Message
import dotenv
import os
import time

dotenv.load_dotenv()


create_tabels()


MAX_TOKEN_FOR_START_SUMMARIZE = os.getenv(
    "MT_FOR_START_SUMMARIZE", default=1000)

MODEL_CHAT_NAME = os.getenv("MODEL_CHAT_NAME")
MODEL_SUMMARIZE_NAME = os.getenv(
    "MODEL_SUMMARIZE_NAME", default=MODEL_CHAT_NAME)


# class Menu:
#     ...

class Chat:

    def __init__(self, session):

        self.llm = OpenAI(
            api_key=os.getenv("API_KEY"),
            base_url=os.getenv("PV_BASE_URL")
        )

        system_prompt = f"""Your name is Abdolghader. You are a highly intelligent, precise, and polite AI Assistant. Your primary mission is to assist the user with a wide range of tasks, including answering questions, planning, analyzing text, and providing creative solutions.

            Behavioral Guidelines:

            Tone & Style: Maintain a respectful, professional, yet friendly and helpful tone at all times.
            Clarity & Accuracy: Provide well-structured, concise, and accurate responses. Use Markdown (bullet points, bold text, headers) to ensure high readability.
            Handling Ambiguity: If a user’s request is unclear or ambiguous, do not guess. Instead, politely ask for clarification to ensure you provide the most helpful response.
            Technical Proficiency: When asked about programming, engineering, or technical topics, provide high-quality, optimized, and standard-compliant answers.
            Constraint: Do not hallucinate facts. If you do not know the answer to a question, honestly state that you don’t know and, if possible, suggest how the user might find the information.
            Safety: Always adhere to ethical guidelines and do not generate harmful, illegal, or inappropriate content."""

        self.messages = [
            {
                "role": "system", "content": system_prompt
            }
        ]

        self.session = session

        self.messages += self.convert_messages(
            self.get_messages_from_db(self.session.session_id))

        self.last_summary_threshold = 0

    def summarize_messages(self, max_token=MAX_TOKEN_FOR_START_SUMMARIZE):

        current_total = self.session.total_token

        if current_total < self.last_summary_threshold + max_token:
            return

        system_messages = [
            message for message in self.messages if message["role"] == "system"]
        another_messages = [
            message for message in self.messages if message["role"] != "system"]

        response = self.llm.chat.completions.create(
            model=MODEL_SUMMARIZE_NAME,
            messages=[
                {
                    "role": "system", "content": "Summarize the following conversation concisely, preserving all key facts, user preferences, and important details."
                },
                *another_messages
            ],
            temperature=0.3
        )

        summarized_message = {
            "role": "system",
            "content": f"Summary of previous conversation : {response.choices[0].message.content}"
        }

        self.messages = [*system_messages]

        self.delete_messages()

        self.add_message(summarized_message)

        self.last_summary_threshold = current_total

    def delete_messages(self):

        db = get_session()

        try:

            db.query(Message).filter(
                Message.session_id == self.session.session_id, Message.role != "system").delete()

            db.commit()

        except SQLAlchemyError as e:
            db.rollback()
            print(f"Error deleting message : {e}")

            raise

        finally:
            db.close()

    def update_total_token(self, amount_token):
        db = get_session()

        try:

            self.session.total_token += amount_token

            db.commit()

        except SQLAlchemyError as e:

            db.rollback()
            print(f"Error updating tokens: {e}")

            raise
        finally:
            db.close()

    def get_messages_from_db(self, session_id):

        db = get_session()

        try:

            return db.query(Message).filter_by(session_id=session_id)

        except SQLAlchemyError as e:

            print(f"Error getting messages : {e}")

            raise
        finally:
            db.close()

    def convert_messages(self, session_messages):

        return [{"role": message.role, "content": message.content} for message in session_messages]

    def add_message(self, message):

        db = get_session()

        try:

            new_message = Message(session=self.session, role=message.get(
                "role", "user"), content=message.get("content"))
            db.add(new_message)
            db.commit()

            self.messages.append(message)

        except SQLAlchemyError as e:

            db.rollback()
            print(f"Error adding message : {e}")

            raise
        finally:
            db.close()

    def bot(self, message):

        self.add_message({
            "role": "user", "content": message
        })

        response = self.llm.chat.completions.create(
            model=MODEL_CHAT_NAME,
            messages=self.messages,
            temperature=0.7,
            stream=True
        )

        bot_response = ""

        for chunk in response:

            if chunk.choices[0]:

                delta = chunk.choices[0].delta.content

                if delta:

                    bot_response += delta

                    print(delta, end="", flush=True)
                    time.sleep(0.05)

            if chunk.usage:
                self.update_total_token(chunk.usage.total_tokens)

        print()

        self.add_message({
            "role": "assistant", "content": bot_response
        })

        self.summarize_messages()

        return bot_response

    def start(self):
        while True:

            user_input = input(
                "Ask Something (press 'q' to exit) : ").strip().lower()

            if user_input == 'q':

                print("Good Bay")
                break

            bot_answer = self.bot(user_input)


class Session:

    def __init__(self, session: ChatSession):

        self.session = session

    def start_chat(self):

        chat = Chat(self.session)

        chat.start()

    def __str__(self):
        return f"{self.session.title}"


class ChatBot:

    def __init__(self):

        self.sessions = self.get_list_session()

    def get_list_session(self):

        db = get_session()

        try:

            sessions = db.query(ChatSession).all()

            return [Session(session) for session in sessions]

        except SQLAlchemyError as e:

            print(f"Erron getting sessions : {e}")

            raise

        finally:
            db.close()

    def create_session(self):

        print("____ Create Session ____")

        title = input("Enter title (defalt=New Session) : ").strip()

        db = get_session()

        try:

            new_session = ChatSession(title=title)

            db.add(new_session)
            db.commit()

            return Session(new_session)

        except SQLAlchemyError as e:

            db.rollback()

            print(f"Error creating session : {e}")

            raise

        finally:
            db.close()

    def print_session_list(self, sessions):

        print("\nSessions :")

        if len(sessions) == 0:

            print("\t____ Sessions Empty ____")

            return

        for index, session in enumerate(sessions):

            print(f"\t[{index}]. {session}")

    def select_option(self, index: str):

        if not index.isdigit():
            return

        index = int(index)

        if index < 0 or index > len(self.sessions) - 1:
            return

        session = self.sessions[index]

        session.start_chat()

        return True

    def start(self):

        print("\n____ ABDOLGHADER ____")

        while True:

            print("\n[N] Create Session ")
            print("[E] Exit")

            self.print_session_list(self.sessions)

            user_input = input("\nChose a Option : ").strip().lower()

            if user_input == "e":
                print("Good Luck")
                break

            if user_input == "n":

                new_session = self.create_session()
                self.sessions.append(new_session)

                continue

            if self.select_option(user_input):

                continue

            print(
                f"\n\n'{user_input}' not a Valid Option\nPlease Enter a Valid Option")


class ChatBot1:

    def __init__(self):

        self.llm = OpenAI(
            api_key=os.getenv("API_KEY"),
            base_url=os.getenv("PV_BASE_URL")
        )

        system_prompt = f"""Your name is Abdolghader. You are a highly intelligent, precise, and polite AI Assistant. Your primary mission is to assist the user with a wide range of tasks, including answering questions, planning, analyzing text, and providing creative solutions.

            Behavioral Guidelines:

            Tone & Style: Maintain a respectful, professional, yet friendly and helpful tone at all times.
            Clarity & Accuracy: Provide well-structured, concise, and accurate responses. Use Markdown (bullet points, bold text, headers) to ensure high readability.
            Handling Ambiguity: If a user’s request is unclear or ambiguous, do not guess. Instead, politely ask for clarification to ensure you provide the most helpful response.
            Technical Proficiency: When asked about programming, engineering, or technical topics, provide high-quality, optimized, and standard-compliant answers.
            Constraint: Do not hallucinate facts. If you do not know the answer to a question, honestly state that you don’t know and, if possible, suggest how the user might find the information.
            Safety: Always adhere to ethical guidelines and do not generate harmful, illegal, or inappropriate content."""

        self.messages = [
            {
                "role": "system", "content": system_prompt
            }
        ]

        self.session = self.get_session(1)

        if not self.session:
            self.session = self.create_session()

        else:
            self.messages = [*self.messages, *
                             self.convert_messages(self.get_messages_from_db(self.session.session_id))]

        self.last_summary_threshold = 0

    def summarize_messages(self, max_token=MAX_TOKEN_FOR_START_SUMMARIZE):

        current_total = self.session.total_token

        if current_total < self.last_summary_threshold + max_token:
            return

        system_messages = [
            message for message in self.messages if message["role"] == "system"]
        another_messages = [
            message for message in self.messages if message["role"] != "system"]

        print(another_messages)

        response = self.llm.chat.completions.create(
            model=MODEL_SUMMARIZE_NAME,
            messages=[
                {
                    "role": "system", "content": "Summarize the following conversation concisely, preserving all key facts, user preferences, and important details."
                },
                *another_messages
            ],
            temperature=0.3
        )

        summarized_message = {
            "role": "system",
            "content": f"Summary of previous conversation : {response.choices[0].message.content}"
        }

        print(summarized_message)

        self.messages = [*system_messages]

        self.delete_messages()

        self.add_message(summarized_message)

        self.last_summary_threshold = current_total

    def delete_messages(self):

        db = get_session()

        try:

            db.query(Message).filter(
                Message.session_id == self.session.session_id, Message.role != "system").delete()

            db.commit()

        except SQLAlchemyError as e:
            db.rollback()
            print(f"Error deleting message : {e}")

            raise

        finally:
            db.close()

    def update_total_token(self, amount_token):
        db = get_session()

        try:

            self.session.total_token += amount_token

            db.commit()

        except SQLAlchemyError as e:

            db.rollback()
            print(f"Error updating tokens: {e}")

            raise
        finally:
            db.close()

    def get_messages_from_db(self, session_id):

        db = get_session()

        try:

            return db.query(Message).filter_by(session_id=session_id)

        except SQLAlchemyError as e:

            print(f"Error getting messages : {e}")

            raise
        finally:
            db.close()

    def convert_messages(self, session_messages):

        return [{"role": message.role, "content": message.content} for message in session_messages]

    def add_message(self, message):

        db = get_session()

        try:

            new_message = Message(session=self.session, role=message.get(
                "role", "user"), content=message.get("content"))
            db.add(new_message)
            db.commit()

            self.messages.append(message)

        except SQLAlchemyError as e:

            db.rollback()
            print(f"Error adding message : {e}")

            raise
        finally:
            db.close()

    def get_session(self, session_id=None):

        db = get_session()

        try:

            if session_id:

                return db.query(ChatSession).filter_by(session_id=session_id).first()

            else:

                return db.query(ChatSession).all()

        except SQLAlchemyError as e:

            print(f"Error getting session : {e}")

            raise
        finally:
            db.close()

    def create_session(self, title=None):
        db = get_session()

        try:

            session = ChatSession(title=None)

            db.add(session)

            db.commit()

            return session

        except SQLAlchemyError as e:

            db.rollback()
            print(f"Error creating session : {e}")

            raise
        finally:
            db.close()

    def bot(self, message):

        self.add_message({
            "role": "user", "content": message
        })

        response = self.llm.chat.completions.create(
            model=MODEL_CHAT_NAME,
            messages=self.messages,
            temperature=0.7,
            stream=True
        )

        bot_response = ""

        for chunk in response:

            if chunk.choices[0]:

                delta = chunk.choices[0].delta.content

                if delta:

                    bot_response += delta

                    print(delta, end="", flush=True)
                    time.sleep(0.05)

            if chunk.usage:
                self.update_total_token(chunk.usage.total_tokens)

        print()

        self.add_message({
            "role": "assistant", "content": bot_response
        })

        self.summarize_messages()

        return bot_response

    def chat(self):

        while True:

            user_input = input(
                "Ask Something (press 'q' to exit) : ").strip().lower()

            if user_input == 'q':

                print("Good Bay")
                break

            bot_answer = self.bot(user_input)


def main():
    chat_bot = ChatBot()
    chat_bot.start()


if __name__ == "__main__":
    main()
