import os  # Import for operating system interaction
from cachetools import cached, TTLCache  # Import for caching API responses
from typing import List, Dict  # Import for type hinting
import json  # Import for working with JSON data
import requests  # Import for making HTTP requests
from enum import Enum  # Import for creating enums
from datetime import datetime  # Import for working with timestamps

import streamlit as st  # Import for building the Streamlit web app
from sqlalchemy import create_engine
from groq import Groq  # Import for interacting with the Groq API
from typing import List, Dict  # Import for type hinting
from sqlalchemy.orm import sessionmaker

from model import Base, ChatMessage, Feedback

class Role(Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


CONFIG_FILE_NAME = "config.json"  # Configuration file name
API_KEY_ENV_VAR = "GROQ_API_KEY"  # Environment variable for Groq API key
DB_NAME = "chat_history.db"  # Database file name

@cached(cache=TTLCache(maxsize=100, ttl=300))  # Cache API responses for efficiency
def get_groq_models():
    """
    Fetches available models from the Groq API.
    Includes a retry mechanism for robustness.
    """
    api_key = os.getenv(API_KEY_ENV_VAR)  # Get API key from environment variable
    url = "https://api.groq.com/openai/v1/models"  # API endpoint
    headers = {
        "Authorization": f"Bearer {api_key}"  # Authorization header
    }
    for _ in range(3):  # Retry mechanism
        response = requests.get(url, headers=headers)
        if response.ok:
            try:
                models = response.json()["data"]  # Parse JSON response
                return [{"name": model["id"], "id": model["id"], "info": model.get("description", "")} for model in
                        models]  # Return a list of models
            except (KeyError, TypeError) as e:
                st.error(f"Error parsing models from the API response: {e}")
                return []
        else:
            st.error(f"Failed to fetch models from the API: {response.text}")
    return []


def create_groq_client(api_key: str) -> Groq:
    """
    Creates a Groq client instance using the provided API key.
    """
    os.environ[API_KEY_ENV_VAR] = api_key  # Set API key in environment variable
    return Groq()  # Create Groq client


def fetch_chat_response(client: Groq, history: List[Dict[str, str]], model: str) -> str:
    """
    Sends a chat request to the Groq API and retrieves the response.
    Handles potential errors.
    """
    try:
        response = client.chat.completions.create(
            model=model,  # Specify the model to use
            messages=history  # Send the chat history
        )
        return response.choices[0].message.content  # Extract the assistant's response
    except Exception as e:
        st.error(f"Error retrieving response from API: {e}")
        return "😅 Sorry, there was an error processing your request."


# _____
# History

def save_message(role: str, content: str, timestamp: str, model: Dict[str, str]):
    """
    Saves a chat message to the database.
    """
    engine = create_engine(f'sqlite:///{DB_NAME}')  # Connect to the database
    Session = sessionmaker(bind=engine)  # Create a session factory
    session = Session()  # Create a database session
    new_message = ChatMessage(
        role=role,
        content=content,
        timestamp=datetime.fromisoformat(timestamp),
        model_id=model["id"]  # Extract the model ID from the dictionary
    )
    session.add(new_message)  # Add the message to the session
    session.commit()  # Commit changes to the database
    session.close()  # Close the database session


def load_chat_history() -> List[Dict[str, str]]:
    """
    Loads chat history from the database.
    """
    engine = create_engine(f'sqlite:///{DB_NAME}')
    Session = sessionmaker(bind=engine)
    session = Session()
    chat_history = session.query(ChatMessage).order_by(ChatMessage.id).all()
    session.close()
    return [{"role": msg.role, "content": msg.content, "timestamp": msg.timestamp.isoformat(), "model_id": msg.model_id}
            for msg in chat_history]



def load_configuration() -> Dict[str, str]:
    """
    Loads the application configuration from config.json.
    """
    try:
        working_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(working_dir, CONFIG_FILE_NAME)
        with open(config_path) as config_file:
            return json.load(config_file)
    except FileNotFoundError:
        st.error(f"Configuration file '{CONFIG_FILE_NAME}' not found. Please ensure it exists.")
        return {}
    except json.JSONDecodeError:
        st.error("Failed to decode the configuration file. Please check the file format.")
        return {}


def format_timestamp(timestamp_iso: str) -> str:
    """
    Formats a timestamp in ISO 8601 format for display.
    """
    timestamp_dt = datetime.fromisoformat(timestamp_iso)
    return timestamp_dt.strftime("%Y-%m-%d %H:%M:%S")


def initialize_chat_history():
    """
    Initializes the chat history from the database, using Streamlit's session state.
    """
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = load_chat_history()


def display_chat_history():
    """
    Displays the chat history in the Streamlit app.
    """
    for i, chat_message in enumerate(st.session_state.chat_history):
        formatted_timestamp = format_timestamp(chat_message["timestamp"])
        with st.chat_message(chat_message["role"]):
            st.markdown(f"{chat_message['content']}<br><small>{formatted_timestamp} ⏰</small>", unsafe_allow_html=True)
        if i < len(st.session_state.chat_history) - 1:
            st.markdown("---")  # Add separator between messages

def handle_user_input(groq_client_instance: Groq, selected_model: Dict[str, str]):
    """
    Handles user input, sends requests to the Groq API, and displays the response.
    """
    user_message = st.chat_input("Ask LLAMA... 🦙")  # Get user input from chat box
    if user_message:
        st.chat_message(Role.USER.value).markdown(f"👤 {user_message}")  # Display user message
        timestamp = datetime.now().isoformat()  # Get current timestamp
        if selected_model:
            save_message(Role.USER.value, user_message, timestamp, selected_model)  # Save user message to database
            st.session_state.chat_history.append({
                "role": Role.USER.value,
                "content": user_message,
                "timestamp": timestamp,
                "model_id": selected_model["id"]  # Add model_id to the chat history
            })

            # Create a placeholder for the thinking animation
            lottie_thinking_placeholder = st.empty()

            # Display the thinking animation
            with lottie_thinking_placeholder.container():
                # st_lottie(LOTTIE_LOADING_URL, height=200, width=200, key="thinking")

                history_for_api = prepare_history_for_api()  # Prepare chat history for API request
                assistant_reply = fetch_chat_response(groq_client_instance, history_for_api, selected_model["id"])  # Send API request and get response

                add_assistant_reply(assistant_reply, selected_model)  # Add assistant's reply to the chat history
                display_assistant_reply(assistant_reply)  # Display assistant's reply

            # Clear the animation placeholder after the response
            lottie_thinking_placeholder.empty()

            # Clear the user input after sending
            st.text_input("User Input", value="", label_visibility="collapsed")
            st.rerun()
        else:
            st.error("No model selected. Please select a model from the sidebar.")


def prepare_history_for_api() -> List[Dict[str, str]]:
    """
    Prepares the chat history for sending to the Groq API.
    """
    return [
        {"role": Role.SYSTEM.value, "content": "You are my helpful assistant 🦙"},  # Add system instruction
        *[{"role": msg["role"], "content": msg["content"]} for msg in st.session_state.chat_history]  # Add chat history
    ]


def add_assistant_reply(reply: str, model: Dict[str, str]):
    """
    Adds the assistant's reply to the chat history.
    """
    timestamp = datetime.now().isoformat()  # Get current timestamp
    save_message(Role.ASSISTANT.value, reply, timestamp, model)  # Save assistant's reply to the database
    st.session_state.chat_history.append({
        "role": Role.ASSISTANT.value,
        "content": reply,
        "timestamp": timestamp,
        "model_id": model["id"],
        "id": len(st.session_state.chat_history)  # Ensure each message has a unique id
    })


def display_assistant_reply(reply: str):
    """
    Displays the assistant's reply in the Streamlit app.
    """
    st.markdown("---")  # Add separator between messages
    with st.chat_message(Role.ASSISTANT.value):
        # st_lottie(LOTTIE_SUCCESS_URL, height=150, width=150, key="reply_success")
        st.markdown(f"🤖 {reply}")


def initialize_db():
    """
    Creates the database tables if they don't exist.
    """
    engine = create_engine(f'sqlite:///{DB_NAME}')
    Base.metadata.create_all(engine)

# _____
# Feedbacks


def save_feedback(chat_message_id, is_positive, comment):
    """
    Saves user feedback for a chat message to the database.
    Handles updates to existing feedback.
    """
    engine = create_engine(f'sqlite:///{DB_NAME}')
    Session = sessionmaker(bind=engine)
    session = Session()

    # Check if feedback already exists for the given chat_message_id
    existing_feedback = session.query(Feedback).filter_by(chat_message_id=chat_message_id).first()

    if existing_feedback:
        # Update the existing feedback
        existing_feedback.is_positive = is_positive
        existing_feedback.comment = comment
        session.commit()
        st.success("Feedback updated!")
    else:
        # Insert new feedback
        new_feedback = Feedback(chat_message_id=chat_message_id, is_positive=is_positive, comment=comment)
        session.add(new_feedback)
        session.commit()
        st.success("Feedback saved!")

    session.close()


def clear_chat_history():
    """
    Clears the chat history from the database and the session state.
    """
    engine = create_engine(f'sqlite:///{DB_NAME}')
    Session = sessionmaker(bind=engine)
    session = Session()
    session.query(ChatMessage).delete()
    session.commit()
    session.close()
    st.session_state.chat_history = []


def search_chat_history(query: str):
    """
    Searches the chat history for messages containing a given query.
    """
    filtered_history = []
    for chat_message in st.session_state.chat_history:
        if query.lower() in chat_message["content"].lower():
            filtered_history.append(chat_message)
    return filtered_history

# _____
# Speach to text

def parse_models_info(file_path: str) -> Dict[str, str]:
    """
    Parses a models_info.md file and returns a dictionary of model descriptions.
    """
    models_info = {}
    with open(file_path, 'r') as file:
        lines = file.readlines()
        current_model_id = None
        current_model_description = []
        for line in lines:
            if line.startswith("**"):
                if current_model_id:
                    models_info[current_model_id] = "\n".join(current_model_description)
                current_model_id = line.split("**")[1].strip()
                current_model_description = []
            elif line.startswith("- Model ID:"):
                current_model_id = line.split(":")[1].strip()
            elif line.startswith("- "):
                current_model_description.append(line.strip())
        if current_model_id:
            models_info[current_model_id] = "\n".join(current_model_description)
    return models_info


# Directory for storing uploaded audio files
UPLOADS_DIR = "uploads"
if not os.path.exists(UPLOADS_DIR):
    os.makedirs(UPLOADS_DIR)


def transcribe_audio(client: Groq, audio_file_path, model="whisper-large-v3", language=None):
    """
    Transcribes audio using Groq's Whisper API.
    """
    try:
        with open(audio_file_path, "rb") as file:
            transcription = client.audio.transcriptions.create(
                file=(audio_file_path, file.read()),
                model=model,
                language=language
            )
        return transcription.text
    except Exception as e:
        st.error(f"Error transcribing audio: {e}")
        return None

#_____
# Views


def handle_user_input(groq_client_instance: Groq, selected_model: Dict[str, str]):
    """
    Handles user input, sends requests to the Groq API, and displays the response.
    """
    user_message = st.chat_input("Ask LLAMA... 🦙")  # Get user input from chat box
    if user_message:
        st.chat_message(Role.USER.value).markdown(f"👤 {user_message}")  # Display user message
        timestamp = datetime.now().isoformat()  # Get current timestamp
        if selected_model:
            save_message(Role.USER.value, user_message, timestamp, selected_model)  # Save user message to database
            st.session_state.chat_history.append({
                "role": Role.USER.value,
                "content": user_message,
                "timestamp": timestamp,
                "model_id": selected_model["id"]  # Add model_id to the chat history
            })

            # Create a placeholder for the thinking animation
            lottie_thinking_placeholder = st.empty()

            # Display the thinking animation
            with lottie_thinking_placeholder.container():
                # st_lottie(LOTTIE_LOADING_URL, height=200, width=200, key="thinking")

                history_for_api = prepare_history_for_api()  # Prepare chat history for API request
                assistant_reply = fetch_chat_response(groq_client_instance, history_for_api, selected_model["id"])  # Send API request and get response

                add_assistant_reply(assistant_reply, selected_model)  # Add assistant's reply to the chat history
                display_assistant_reply(assistant_reply)  # Display assistant's reply

            # Clear the animation placeholder after the response
            lottie_thinking_placeholder.empty()

            # Clear the user input after sending
            st.text_input("User Input", value="", label_visibility="collapsed")
            st.rerun()
        else:
            st.error("No model selected. Please select a model from the sidebar.")


def prepare_history_for_api() -> List[Dict[str, str]]:
    """
    Prepares the chat history for sending to the Groq API.
    """
    return [
        {"role": Role.SYSTEM.value, "content": "You are my helpful assistant 🦙"},  # Add system instruction
        *[{"role": msg["role"], "content": msg["content"]} for msg in st.session_state.chat_history]  # Add chat history
    ]


def add_assistant_reply(reply: str, model: Dict[str, str]):
    """
    Adds the assistant's reply to the chat history.
    """
    timestamp = datetime.now().isoformat()  # Get current timestamp
    save_message(Role.ASSISTANT.value, reply, timestamp, model)  # Save assistant's reply to the database
    st.session_state.chat_history.append({
        "role": Role.ASSISTANT.value,
        "content": reply,
        "timestamp": timestamp,
        "model_id": model["id"],
        "id": len(st.session_state.chat_history)  # Ensure each message has a unique id
    })


def display_assistant_reply(reply: str):
    """
    Displays the assistant's reply in the Streamlit app.
    """
    st.markdown("---")  # Add separator between messages
    with st.chat_message(Role.ASSISTANT.value):
        # st_lottie(LOTTIE_SUCCESS_URL, height=150, width=150, key="reply_success")
        st.markdown(f"🤖 {reply}")