from PIL import Image  # Import for image manipulation


from typing import List, Dict  # Import for type hinting

from functions import *


# from streamlit_lottie import st_lottie  # Import for displaying Lottie animations

# Define constants for the application
CONFIG_FILE_NAME = "config.json"  # Configuration file name

# UI settings
THEME_COLOR = "#00bfae"  # Theme color for the app

# Lottie animation URLs
# LOTTIE_WELCOME_URL = "https://lottie.host/6cc5c636-161e-4fe2-a29e-d0a010fb857d/oUxnN8jMLv.json"
# LOTTIE_LOADING_URL = "https://lottie.host/6db67e84-29ca-4df7-9aed-e918be35c04f/GUHZd8ZAiP.json"
# LOTTIE_SUCCESS_URL = "https://lottie.host/0d17b47d-7e01-4b7d-a8fb-f94b6c69dd48/jycOqQmo4J.json"
# LOTTIE_ERROR_URL = "https://lottie.host/caa8d9f2-7b02-4462-867d-4a5a1aa1a175/3HRdfJrk9m.json"
# LOTTIE_NO_DATA_URL = "https://lottie.host/aa234c54-eca8-4b61-a21c-83b5b1e82698/1EEUxyZ91a.json"

# Define an enum for different chat roles

    
    
def main():
    """
    Main function for the Streamlit application.
    """
    st.set_page_config(
        page_title="LLAMABOT",
        page_icon="🦙",
        layout="centered",
        initial_sidebar_state="expanded"
    )

    # Load configuration and initialize Groq client
    config = load_configuration()
    api_key_value = config.get(API_KEY_ENV_VAR)

    if not api_key_value:
        # st_lottie(LOTTIE_ERROR_URL, height=150, width=150, key="api_error")
        st.error("API key is missing in the configuration.")
        return

    groq_client_instance = create_groq_client(api_key_value)

    initialize_db()  # Initialize the database
    initialize_chat_history()  # Initialize the chat history

    # Display the main title
    # logo_image = Image.open("assets/logo-removebg-preview.png")
    # st.image(logo_image)

    # Load model descriptions
    models_info = parse_models_info("assets/models_info.md")

    # Create the sidebar with settings and chat history
    with st.sidebar:
        st.header("LLAMABOT Settings ⚙️")
        # st_lottie(LOTTIE_WELCOME_URL, height=100, width=100, key="welcome")
        groq_models = get_groq_models()  # Get models from the Groq API
        selected_model = st.selectbox("Select a Model", groq_models, format_func=lambda model: model["name"])  # Allow user to select a model
        # Display model description
        if selected_model:
            model_id = selected_model['id']
            model_description = models_info.get(model_id, "No description available.")
            st.markdown(f"**Model Description:** {model_description}")
        else:
            st.warning("No model selected. Please select a model to start chatting.")
            st.markdown("---")

        # Chat History section
        st.subheader("Chat History 📜")
        with st.expander("Expand Chat History", expanded=False):
            if st.session_state.chat_history:
                query = st.text_input("Search Chat History", placeholder="Enter your search term")
                if query:
                    filtered_history = search_chat_history(query)
                    for chat_message in filtered_history:
                        formatted_timestamp = format_timestamp(chat_message["timestamp"])
                        with st.chat_message(chat_message["role"]):
                            st.markdown(f"{chat_message['content']}<br><small>{formatted_timestamp} ⏰</small>",
                                        unsafe_allow_html=True)
                        st.markdown("---")
                else:
                    display_chat_history()
            else:
                # st_lottie(LOTTIE_NO_DATA_URL, height=150, width=150, key="no_data")
                st.info("No chat history available.")

        # Button to start a new chat
        if st.button("🆕", help="Start a new chat session"):
            clear_chat_history()  # Clear chat history
            st.rerun()

        # Speech-to-Text section
        st.markdown("---")
        st.header("Speech-to-Text 🎙️")
        uploaded_audio = st.file_uploader("Upload an audio file",
                                          type=["mp3", "mp4", "mpeg", "mpga", "m4a", "wav", "webm"])
        selected_language = st.selectbox("Select audio language (optional)", ["", "en", "fr", "es", "de"],
                                         help="Leave blank for auto-detect")

    # Display the chat history
    if st.session_state.chat_history:
        display_chat_history()
    else:
        # st_lottie(LOTTIE_NO_DATA_URL, height=200, width=200, key="no_chat_history")
        st.info("No chat history to display.")

    # Main Chat Area
    handle_user_input(groq_client_instance, selected_model)  # Handle user input and chat interactions

    # Display feedback buttons
    if st.session_state.chat_history:
        chat_message_id = st.session_state.chat_history[-1].get("id")

        # Feedback buttons using Unicode characters
        col1, col2 = st.columns(2)
        with col1:
            if st.button("👍", key=f"positive_feedback_{chat_message_id}"):
                # st_lottie(LOTTIE_SUCCESS_URL, height=100, width=100, key="positive_feedback")
                comment = st.text_input(f"Feedback for message {chat_message_id}")
                save_feedback(chat_message_id, True, comment)
        with col2:
            if st.button("👎", key=f"negative_feedback_{chat_message_id}"):
                # st_lottie(LOTTIE_ERROR_URL, height=100, width=100, key="negative_feedback")
                comment = st.text_input(f"Feedback for message {chat_message_id}")
                save_feedback(chat_message_id, False, comment)

    # Speech-to-Text functionality
    if uploaded_audio is not None:
        # Save uploaded audio file
        audio_file_path = os.path.join(UPLOADS_DIR, uploaded_audio.name)
        with open(audio_file_path, "wb") as f:
            f.write(uploaded_audio.read())

        # Display uploaded audio
        st.audio(uploaded_audio, format='audio/wav')

        if st.button("Transcribe"):
            with st.spinner("Transcribing..."):
                transcript = transcribe_audio(groq_client_instance, audio_file_path, language=selected_language)  # Transcribe audio
            if transcript:
                st.success("Transcription successful!")
                st.text_area("Transcription:", value=transcript)
            else:
                st.error("Transcription failed. Please try again.")


if __name__ == "__main__":
    main()