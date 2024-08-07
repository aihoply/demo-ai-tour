from openai import OpenAI
import chainlit as cl
from load_dotenv import load_dotenv
import os

load_dotenv()

# Initialize the OpenAI client with your API key
client = OpenAI(
    organization= os.getenv("ORG_ID"),
    api_key=os.getenv("OPENAI_API_KEY"),
    project=os.getenv("PROJECT_ID"),
)

@cl.on_chat_start
def start_chat():
    cl.user_session.set(
        "message_history",
        [{"role": "system", "content": "You are a helpful assistant."}],
    )

@cl.on_message
async def main(message: cl.Message):
    message_history = cl.user_session.get("message_history")
    message_history.append({"role": "user", "content": message.content})

    msg = cl.Message(content="")
    await msg.send()

    # Create a new thread
    thread = client.beta.threads.create()

    # Create a new message in the thread
    openai_message = client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=message.content  # Use the content of the Chainlit message
    )

    # Make sure you use a valid assistant ID
    assistant_id = os.getenv("ASSISTANT_ID")

    # Stream the response from the assistant
    stream = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant_id,
        stream=True
    )

    for event in stream:
        if event.event == "thread.message.delta" and event.data.delta.content:
            await msg.stream_token(event.data.delta.content[0].text.value)

    message_history.append({"role": "assistant", "content": msg.content})
    await msg.update()
