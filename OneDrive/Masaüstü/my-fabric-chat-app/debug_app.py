# debug_app.py

import os
import streamlit as st
from openai import OpenAI

# 1) Page config
st.set_page_config(page_title="Debug GPT Access", layout="wide")

# 2) Initialize client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 2a) Show (debug) what the key actually is (or isn’t)
st.caption(f"🔐 [DEBUG] OPENAI_API_KEY = {os.getenv('OPENAI_API_KEY')!r}")

# 3) Simple in-RAM “conversation history”
if "history" not in st.session_state:
    st.session_state.history = []

# 4) chat_with_persona that logs any exceptions visibly
def chat_with_persona_direct(user_text):
    msgs = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": user_text}
    ]
    try:
        resp = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=msgs,
            temperature=0.7
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"💥 [DEBUG] OpenAI call failed: {e}")
        return f"[Error: {e}]"

# 5) UI: a simple form to send a single prompt
st.title("🔍 Debug: Can I reach OpenAI?")

with st.form("debug_form", clear_on_submit=True):
    user_input = st.text_input("You:", key="dbg_input", placeholder="Type something like 'Hello!'…")
    submit = st.form_submit_button("Send")
    if submit and user_input:
        # Call GPT directly (no personas, no memory)
        reply = chat_with_persona_direct(user_input)
        st.session_state.history.append((user_input, reply))

# 6) Display the history
for u, r in st.session_state.history:
    st.markdown(f"**You:** {u}")
    st.markdown(f"**GPT:** {r}")
