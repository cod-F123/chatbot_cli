from openai import OpenAI
from db.db import create_tabels, get_session
from db.models import ChatSession, Message
import dotenv
import os
import time

dotenv.load_dotenv()


create_tabels()


# class Menu:
#     ...


# class Session:
#     ...


# class Chat:
#     ...


class ChatBot:

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

    def get_messages_from_db(self, session_id):

        db = get_session()

        try:

            return db.query(Message).filter_by(session_id=session_id)

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

        finally:
            db.close()

    def get_session(self, session_id=None):

        db = get_session()

        try:

            if session_id:

                return db.query(ChatSession).filter_by(session_id=session_id).first()

            else:

                return db.query(ChatSession).all()

        finally:

            db.close()

    def create_session(self, title=None):
        db = get_session()

        try:

            session = ChatSession(title=None)

            db.add(session)

            db.commit()

            return session

        finally:
            db.close()

    def bot(self, message):

        self.add_message({
            "role": "user", "content": message
        })

        response = self.llm.chat.completions.create(
            model="gpt-4.1-nano",
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

        self.add_message({
            "role": "assistant", "content": bot_response
        })

        return bot_response

    def chat(self):

        while True:

            user_input = input(
                "Ask Something (press 'q' to exit) : ").strip().lower()

            if user_input == 'q':

                print("Good Bay")
                break

            bot_answer = self.bot(user_input)

            print(bot_answer)


def main():
    chat_bot = ChatBot()
    chat_bot.chat()


if __name__ == "__main__":
    main()
