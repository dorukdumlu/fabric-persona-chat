import streamlit as st

# 1) Ensure the key exists:
if "user_input" not in st.session_state:
    st.session_state["user_input"] = ""

st.title("🔍 Minimal Text‐Input + Send Test")

# 2) A standalone text_input bound to session_state["user_input"]
user_input = st.text_input(
    "You:",
    key="user_input",
    placeholder="Type something here…"
)

# 3) A separate “Send” button
send_clicked = st.button("Send")

# 4) When Send is clicked, grab the value and clear it immediately
if send_clicked:
    current_input = st.session_state["user_input"].strip()
    st.write("▶️ You clicked Send. session_state['user_input'] was:", repr(current_input))
    # Now clear it for the next run
    st.session_state["user_input"] = ""

# 5) Always show a debug line
st.markdown(
    f"🔍 (debug) session_state['user_input'] is now: `{repr(st.session_state['user_input'])}`"
)
