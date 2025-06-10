# multi_persona_app.py

import os
import json
import datetime
import streamlit as st
from openai import OpenAI

# -----------------------------------------------------------------------------
# 0) Page config (must be first Streamlit command)
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Multi‐Persona Chat Debug", layout="wide")

# -----------------------------------------------------------------------------
# 0.1) Ensure user_input exists in session_state before any text_input()
# -----------------------------------------------------------------------------
if "user_input" not in st.session_state:
    st.session_state["user_input"] = ""

# -----------------------------------------------------------------------------
# 1) Simple hard‐coded “personas” mapping to their system prompts.
#    In your real app, you’d load these from JSON files.
# -----------------------------------------------------------------------------
PERSONAS = {
    "Philosopher":       "You are a deep philosopher who explores every idea with care and quotes thinkers.",
    "SupportiveFriend":  "You are a warm, supportive friend. You always encourage and uplift the user.",
    "CuriousChild":      "You are a curious child who asks questions and responds with wonder.",
    "Utilitarian":       "You are a utilitarian thinker who focuses on efficiency and outcome.",
    "Poet":              "You are a poet. You respond in verse or with rich metaphors.",
}

PERSONA_ICONS = {
    "Philosopher":       "📜",
    "SupportiveFriend":  "🤗",
    "CuriousChild":      "🧒",
    "Utilitarian":       "📊",
    "Poet":              "🎨",
}

PERSONA_COLORS = {
    "Philosopher":       "#FFF9C4",
    "SupportiveFriend":  "#C8E6C9",
    "CuriousChild":      "#F8BBD0",
    "Utilitarian":       "#BBDEFB",
    "Poet":              "#E1BEE7",
}

# -----------------------------------------------------------------------------
# 2) Init OpenAI client
# -----------------------------------------------------------------------------
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Debug: show key on screen (so you know it’s loaded)
st.caption(f"🔐 [DEBUG] OPENAI_API_KEY = {os.getenv('OPENAI_API_KEY')!r}")

# -----------------------------------------------------------------------------
# 3) Simple in‐RAM “chat history” and default selected personas
# -----------------------------------------------------------------------------
if "history" not in st.session_state:
    st.session_state.history = []  # each entry: (user_text, {persona: reply, ...})

if "selected" not in st.session_state:
    st.session_state.selected = list(PERSONAS.keys())

# -----------------------------------------------------------------------------
# 4) Helper: build messages and call OpenAI
# -----------------------------------------------------------------------------
def build_messages(persona_name, user_text):
    """
    1) system: persona’s prompt
    2) user: user_text
    (No memory, no pinned for this debug version)
    """
    return [
        {"role": "system", "content": PERSONAS[persona_name]},
        {"role": "user", "content": user_text}
    ]

def chat_with_persona(name, user_text):
    """
    Send user_text to OpenAI with the persona’s system prompt.
    If an error occurs, display it as a red banner and return "[Error: ...]".
    """
    msgs = build_messages(name, user_text)
    try:
        resp = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=msgs,
            temperature=0.7
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"💥 [DEBUG] Persona '{name}' API call failed: {e}")
        return f"[Error: {e}]"

# -----------------------------------------------------------------------------
# 5) UI: Title and Sidebar
# -----------------------------------------------------------------------------
st.title("🧠 Multi‐Persona Chat Debug")

st.sidebar.header("Select Personas (for debugging)")
choices = st.sidebar.multiselect(
    "Which personas should respond?",
    options=list(PERSONAS.keys()),
    default=st.session_state.selected
)
# Update selection if changed
if set(choices) != set(st.session_state.selected):
    st.session_state.selected = choices

# -----------------------------------------------------------------------------
# 6) Chat Form (wrapped in st.form)
# -----------------------------------------------------------------------------
with st.form("chat_form", clear_on_submit=True):
    # Ensure user_input is a string
    if "user_input" not in st.session_state or not isinstance(st.session_state.user_input, str):
        st.session_state.user_input = ""

    user_input = st.text_input(
        "You:",
        key="user_input",
        placeholder="Type a message here…"
    )
    submit = st.form_submit_button("Send")

    if submit and user_input:
        # Build a dictionary of replies: {persona_name: reply_text}
        replies = {}
        for nm in st.session_state.selected:
            # Call GPT for each persona
            reply_text = chat_with_persona(nm, user_input)
            replies[nm] = reply_text

        # Append to history
        st.session_state.history.append((user_input, replies))

# -----------------------------------------------------------------------------
# 7) Display History in “bubbles”
# -----------------------------------------------------------------------------
st.markdown("---")

for user_text, persona_replies in st.session_state.history:
    # ---------- User bubble ----------
    st.markdown(
        f"<div style='text-align:right; margin:10px 0;'>"
        f"<span style='background-color:#DCF8C6; padding:8px 12px; border-radius:10px; display:inline-block;'>"
        f"<strong>You:</strong> {user_text}"
        f"</span></div>",
        unsafe_allow_html=True
    )

    # ---------- Persona bubbles ----------
    for nm, reply in persona_replies.items():
        icon = PERSONA_ICONS.get(nm, "")
        bg   = PERSONA_COLORS.get(nm, "#EEEEEE")
        st.markdown(
            f"<div style='text-align:left; margin:5px 0;'>"
            f"<span style='background-color:{bg}; padding:8px 12px; border-radius:10px; display:inline-block;'>"
            f"{icon} <strong>{nm}:</strong><br>{reply}"
            f"</span></div>",
            unsafe_allow_html=True
        )
    st.markdown("")  # blank line between rounds
