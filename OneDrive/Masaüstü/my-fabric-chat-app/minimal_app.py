# minimal_app.py

import streamlit as st

# -----------------------------------------------------------------------------
# 0) Page Configuration: MUST be first Streamlit command
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Minimal Persona Echo Test", layout="wide")

# -----------------------------------------------------------------------------
# 1) Dummy Persona List
# -----------------------------------------------------------------------------
DUMMY_PERSONAS = [
    "Anxious", "CuriousChild", "Daydreamer", "Depressed",
    "DevilAdvocate", "Empath", "Futurist", "Historian",
    "Imaginer", "Philosopher", "Poet", "Realist",
    "Scientist", "Skeptic", "SupportiveFriend", "Surrealist",
    "Technician", "Utilitarian"
]

DUMMY_ICONS = {
    "Anxious":          "😰",
    "CuriousChild":     "🧒",
    "Daydreamer":       "☁️",
    "Depressed":        "😔",
    "DevilAdvocate":    "😈",
    "Empath":           "❤️",
    "Futurist":         "🚀",
    "Historian":        "🏺",
    "Imaginer":         "🌟",
    "Philosopher":      "📜",
    "Poet":             "🎨",
    "Realist":          "🛠️",
    "Scientist":        "🔬",
    "Skeptic":          "❓",
    "SupportiveFriend": "🤗",
    "Surrealist":       "🌀",
    "Technician":       "🔧",
    "Utilitarian":      "📊"
}

DUMMY_COLORS = {
    name: "#DDDDDD" for name in DUMMY_PERSONAS
}

# -----------------------------------------------------------------------------
# 2) In‐Memory State Initialization
# -----------------------------------------------------------------------------
if "chat_history" not in st.session_state:
    # chat_history will be a list of tuples: (user_text, persona_replies_dict)
    st.session_state.chat_history = []

if "selected_personas" not in st.session_state:
    # By default, select all dummy personas
    st.session_state.selected_personas = DUMMY_PERSONAS.copy()

# -----------------------------------------------------------------------------
# 3) Dummy “chat_with_persona” Function
# -----------------------------------------------------------------------------
def dummy_chat_with_persona(name, user_text):
    """
    Instead of calling OpenAI, simply return a dummy reply:
    e.g. “Anxious heard: Hello world”
    """
    return f"{name} heard: {user_text}"

# -----------------------------------------------------------------------------
# 4) UI
# -----------------------------------------------------------------------------
st.title("🔍 Minimal Persona Echo Test")

# Show debug info: how many messages stored, which personas are selected
st.markdown(f"**🚩 Debug**: Selected = {st.session_state.selected_personas}  |  Messages = {len(st.session_state.chat_history)}")

# Sidebar: allow toggling which dummy personas to include
st.sidebar.header("Which Dummy Personas?")
choices = st.sidebar.multiselect(
    "Choose personas to “echo” back:",
    options=DUMMY_PERSONAS,
    default=st.session_state.selected_personas
)
# Update session_state.selected_personas if changed
if set(choices) != set(st.session_state.selected_personas):
    st.session_state.selected_personas = choices

# --------------------------------------------------------
#  4.1) Chat Form (wrapped in st.form to force “Send”)
# --------------------------------------------------------
with st.form("echo_form", clear_on_submit=True):
    # Make sure session_state["user_input"] always exists as a string
    if "user_input" not in st.session_state or not isinstance(st.session_state.user_input, str):
        st.session_state.user_input = ""

    user_input = st.text_input(
        "You:",
        key="user_input",
        placeholder="Type something here…"
    )

    # A small debug line inside the form
    st.markdown(
        f"<small>📝 (Inside form, current: <code>{repr(user_input)}</code>)</small>",
        unsafe_allow_html=True
    )

    submit = st.form_submit_button("Send")
    if submit and user_input:
        # Build dummy persona_replies
        replies = {}
        for name in st.session_state.selected_personas:
            replies[name] = dummy_chat_with_persona(name, user_input)

        # Append to history
        st.session_state.chat_history.append((user_input, replies))

# --------------------------------------------------------
#  4.2) Display chat_history in “bubbles”
# --------------------------------------------------------
for user_text, persona_replies in st.session_state.chat_history:
    # ------------- User bubble -------------
    st.markdown(
        f"<div style='text-align: right; margin:10px 0;'>"
        f"<span style='background-color:#DCF8C6; "
        f"padding:8px 12px; border-radius:10px; display:inline-block;'>"
        f"<strong>You:</strong> {user_text}"
        f"</span></div>",
        unsafe_allow_html=True
    )

    # ------------- Persona bubbles -------------
    for name, reply_text in persona_replies.items():
        icon = DUMMY_ICONS.get(name, "")
        bg = DUMMY_COLORS.get(name, "#EEEEEE")
        st.markdown(
            f"<div style='text-align: left; margin:5px 0;'>"
            f"<span style='background-color:{bg}; "
            f"padding:8px 12px; border-radius:10px; display:inline-block;'>"
            f"{icon} <strong>{name}:</strong><br>{reply_text}"
            f"</span></div>",
            unsafe_allow_html=True
        )
