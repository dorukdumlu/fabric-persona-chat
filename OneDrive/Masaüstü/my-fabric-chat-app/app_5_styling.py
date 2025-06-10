# app_step5_styling_livepreview_fixed.py

import os
import json
import datetime
import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI

# -----------------------------------------------------------------------------
# 0) Page config (must be first Streamlit command)
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Step 5: Styled Persona Fabric", layout="wide")

# -----------------------------------------------------------------------------
# 0.1) Initialize session state keys
# -----------------------------------------------------------------------------
if "user_input" not in st.session_state:
    st.session_state["user_input"] = ""
if "history" not in st.session_state:
    st.session_state["history"] = []

# -----------------------------------------------------------------------------
# 1) Paths & Globals
# -----------------------------------------------------------------------------
PERSONA_DIR = "personas"
MEMORY_FILE = "persona_memory_step5.json"
LOG_FILE    = "chat_log_step5.txt"

PERSONA_ICONS = {
    "Philosopher":      "📜",
    "SupportiveFriend": "🤗",
    "CuriousChild":     "🧒",
    "Utilitarian":      "📊",
    "Poet":             "🎨",
    "Historian":        "🏺",
    "DevilAdvocate":    "😈",
    "Scientist":        "🔬",
    "Empath":           "❤️",
    "Technician":       "🔧",
    "Imaginer":         "🌟",
    "Depressed":        "😔",
    "Anxious":          "😰",
    "Daydreamer":       "☁️",
    "Futurist":         "🚀",
    "Surrealist":       "🌀",
    "Realist":          "🛠️",
    "Skeptic":          "❓",
}

PERSONA_COLORS = {
    "Philosopher":      "#FFF9C4",
    "SupportiveFriend": "#C8E6C9",
    "CuriousChild":     "#F8BBD0",
    "Utilitarian":      "#BBDEFB",
    "Poet":             "#E1BEE7",
    "Historian":        "#FAF3DD",
    "DevilAdvocate":    "#E0E0E0",
    "Scientist":        "#B2EBF2",
    "Empath":           "#FFCDD2",
    "Technician":       "#B2DFDB",
    "Imaginer":         "#FFFDE7",
    "Depressed":        "#ECEFF1",
    "Anxious":          "#FFEBEE",
    "Daydreamer":       "#E3F2FD",
    "Futurist":         "#FFF3E0",
    "Surrealist":       "#F3E5F5",
    "Realist":          "#CFD8DC",
    "Skeptic":          "#FFECB3",
}

# -----------------------------------------------------------------------------
# 2) Load/Save Persona JSONs
# -----------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_personas():
    if not os.path.isdir(PERSONA_DIR):
        os.makedirs(PERSONA_DIR, exist_ok=True)
    persons = {}
    for fname in os.listdir(PERSONA_DIR):
        if not fname.lower().endswith(".json"):
            continue
        path = os.path.join(PERSONA_DIR, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and data.get("name"):
                persons[data["name"]] = data
        except Exception:
            continue
    return persons

def save_persona_to_disk(persona_data):
    try:
        name = persona_data["name"]
        filepath = os.path.join(PERSONA_DIR, f"{name}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(persona_data, f, ensure_ascii=False, indent=2)
        load_personas.clear()
        return True
    except Exception as e:
        st.error(f"Failed to save persona '{persona_data.get('name','?')}': {e}")
        return False

def delete_persona_from_disk(persona_name):
    try:
        path = os.path.join(PERSONA_DIR, f"{persona_name}.json")
        if os.path.exists(path):
            os.remove(path)
            load_personas.clear()
            return True
        return False
    except Exception as e:
        st.error(f"Failed to delete persona '{persona_name}': {e}")
        return False

def clone_persona_on_disk(persona_name):
    persons = load_personas()
    original = persons.get(persona_name)
    if not original:
        return None
    base = persona_name + "_copy"
    new_name = base
    i = 1
    while os.path.exists(os.path.join(PERSONA_DIR, f"{new_name}.json")):
        new_name = f"{base}{i}"
        i += 1
    new_data = dict(original)
    new_data["name"] = new_name
    if save_persona_to_disk(new_data):
        return new_name
    return None

# -----------------------------------------------------------------------------
# 2.1) Initialize "selected" after loading personas
# -----------------------------------------------------------------------------
persons = load_personas()
if "selected" not in st.session_state:
    st.session_state["selected"] = list(persons.keys())

# -----------------------------------------------------------------------------
# 3) OpenAI Client
# -----------------------------------------------------------------------------
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# -----------------------------------------------------------------------------
# 4) Memory + Pinned Load/Save
# -----------------------------------------------------------------------------
def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            data = json.loads(open(MEMORY_FILE, "r", encoding="utf-8").read())
            mem = {}
            pinned = {}
            for name in load_personas().keys():
                mem[name] = data.get(name, [])
                pinned[name] = data.get("pinned", {}).get(name, [])
            return mem, pinned
        except Exception:
            pass
    return {n: [] for n in load_personas().keys()}, {n: [] for n in load_personas().keys()}

def save_memory():
    try:
        to_save = {}
        for pname, msgs in st.session_state.mem.items():
            to_save[pname] = msgs
        to_save["pinned"] = st.session_state.pinned
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(to_save, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"Error saving memory: {e}")

if "mem" not in st.session_state or "pinned" not in st.session_state:
    mem_loaded, pinned_loaded = load_memory()
    st.session_state.mem = mem_loaded
    st.session_state.pinned = pinned_loaded

# -----------------------------------------------------------------------------
# 5) Chat Helpers
# -----------------------------------------------------------------------------
def build_messages(persona_name, user_text):
    persons = load_personas()
    prompt = persons[persona_name]["prompt"]
    messages = [{"role": "system", "content": prompt}]
    for entry in st.session_state.pinned.get(persona_name, []):
        messages.append(entry)
    for entry in st.session_state.mem.get(persona_name, []):
        messages.append(entry)
    messages.append({"role": "user", "content": user_text})
    return messages

def chat_with_persona(pname, user_text):
    msgs = build_messages(pname, user_text)
    try:
        resp = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=msgs,
            temperature=0.7
        )
        reply = resp.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"💥 [DEBUG] Persona '{pname}' API call failed: {e}")
        reply = f"[Error: {e}]"
    st.session_state.mem.setdefault(pname, []).append({"role": "user", "content": user_text})
    st.session_state.mem[pname].append({"role": "assistant", "content": reply})
    save_memory()
    return reply

def fuse_persona_replies(persona_replies):
    combined = ""
    for nm, txt in persona_replies.items():
        combined += f"[{nm}]: {txt}\n\n"
    system_prompt = (
        "You are a skilled synthesizer. Given multiple expert responses labeled by persona, "
        "produce a single concise answer in a unified voice, omitting the labels."
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Please fuse these persona replies:\n\n{combined}"}
    ]
    try:
        resp = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.7
        )
        fused = resp.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"💥 [DEBUG] Fusion call failed: {e}")
        fused = f"[Fusion Error: {e}]"
    return fused

def log_conversation(user_input, persona_replies, fused_reply):
    timestamp = datetime.datetime.now().isoformat()
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as logfile:
            logfile.write(f"[{timestamp}] You: {user_input}\n")
            for nm, ans in persona_replies.items():
                logfile.write(f"[{timestamp}] [{nm}]: {ans}\n")
            logfile.write(f"[{timestamp}] [Fusion]: {fused_reply}\n\n")
    except Exception as e:
        st.error(f"Failed to write to log: {e}")

# -----------------------------------------------------------------------------
# 6) CSS Styling
# -----------------------------------------------------------------------------
st.markdown(
    """
    <style>
      @media (max-width: 600px) {
        .chat-bubble, .persona-bubble {
          width: 90% !important;
          margin-left: auto !important;
          margin-right: auto !important;
        }
      }
      .tooltip {
        position: relative;
        display: inline-block;
      }
      .tooltip .tooltiptext {
        visibility: hidden;
        width: 220px;
        background-color: #333;
        color: #fff;
        text-align: left;
        border-radius: 6px;
        padding: 8px;
        position: absolute;
        z-index: 1;
        bottom: 125%;
        left: 50%;
        margin-left: -110px;
        opacity: 0;
        transition: opacity 0.3s;
      }
      .tooltip:hover .tooltiptext {
        visibility: visible;
        opacity: 1;
      }
    </style>
    """,
    unsafe_allow_html=True
)

# -----------------------------------------------------------------------------
# 7) UI: Title + Tabs
# -----------------------------------------------------------------------------
st.title("🧠 Persona Fabric: Step 5 (Styled)")

tab1, tab2 = st.tabs(["💬 Chat", "👥 Manage Personas"])

# ==== TAB 1: Chat ====
with tab1:
    persons = load_personas()
    if not persons:
        st.warning("No personas found. Go to 'Manage Personas' to add one.")
    else:
        st.sidebar.header("Chat Controls")
        if st.sidebar.button("🔄 Clear All Memory & Chat"):
            st.session_state.mem = {n: [] for n in persons.keys()}
            st.session_state.pinned = {n: [] for n in persons.keys()}
            st.session_state.history = []
            if os.path.exists(MEMORY_FILE):
                os.remove(MEMORY_FILE)
            st.experimental_rerun()

        st.sidebar.markdown("---")
        st.sidebar.header("Select Personas")
        selected = st.sidebar.multiselect(
            "Choose one or more personas:",
            options=list(persons.keys()),
            default=st.session_state.get("selected", list(persons.keys()))
        )
        if set(selected) != set(st.session_state.get("selected", [])):
            old = st.session_state.get("selected", [])
            new_list = [p for p in old if p in selected]
            for p in selected:
                if p not in new_list:
                    new_list.append(p)
            st.session_state.selected = new_list

        st.sidebar.markdown("---")
        st.sidebar.markdown("**Your API key must be set in `OPENAI_API_KEY`.**")

        if not st.session_state.selected:
            st.warning("Please select at least one persona.")
        else:
            view_mode = st.sidebar.radio("View Mode:", ["Single Feed", "Tabbed"])
            st.subheader(f"Chatting with: {', '.join(st.session_state.selected)}")

            # Speech-to-Text widget
            st.markdown("**Speak instead of typing:**")
            speech_html = """
            <div>
              <button id="recBtn" style="font-size:1.5rem; padding:10px;">🎤</button>
              <script>
                const btn = document.getElementById('recBtn');
                const recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
                recognition.lang = 'en-US';
                recognition.interimResults = false;
                recognition.maxAlternatives = 1;
                btn.onclick = () => { recognition.start(); };
                recognition.onresult = (event) => {
                  const transcript = event.results[0][0].transcript;
                  Streamlit.setComponentValue(transcript);
                };
                recognition.onerror = () => {
                  Streamlit.setComponentValue("");
                };
              </script>
            </div>
            """
            transcript = components.html(speech_html, height=100)
            if transcript:
                st.session_state["user_input"] = transcript

            if not isinstance(st.session_state.get("user_input", ""), str):
                st.session_state["user_input"] = ""

            with st.form("chat_form_step5", clear_on_submit=True):
                user_input = st.text_input(
                    "You:", key="user_input", placeholder="Type your message here…"
                )
                st.markdown(
                    f"<div style='font-size:0.9rem; color:gray;'>🔍 Typed: <code>{repr(user_input)}</code></div>",
                    unsafe_allow_html=True
                )
                submit = st.form_submit_button("Send")

                if submit and user_input:
                    persona_replies = {}
                    current = user_input
                    for nm in st.session_state.selected:
                        r = chat_with_persona(nm, current)
                        persona_replies[nm] = r
                        current = r
                    fused = fuse_persona_replies(persona_replies)
                    st.session_state.history.append((user_input, persona_replies, fused))
                    log_conversation(user_input, persona_replies, fused)

            search_term = st.text_input(
                "🔍 Search History", key="search_history", placeholder="Enter keyword…"
            )
            if search_term:
                filtered = [
                    (u, pr_dict, fz)
                    for (u, pr_dict, fz) in st.session_state.history
                    if (search_term.lower() in u.lower())
                       or any(search_term.lower() in ans.lower() for ans in pr_dict.values())
                       or search_term.lower() in fz.lower()
                ]
            else:
                filtered = st.session_state.history

            st.markdown("---")

            if view_mode == "Single Feed":
                for u_text, pr_dict, f_text in filtered:
                    st.markdown(
                        f"<div class='chat-bubble' style='text-align:right; margin:10px 0;'>"
                        f"<span style='background-color:#DCF8C6; padding:8px 12px; border-radius:10px;'>"
                        f"<strong>You:</strong> {u_text}"
                        f"</span></div>",
                        unsafe_allow_html=True
                    )
                    for nm, ans in pr_dict.items():
                        icon = PERSONA_ICONS.get(nm, "")
                        bg   = PERSONA_COLORS.get(nm, "#EEEEEE")
                        pdata = load_personas()[nm]
                        tagline = pdata.get("prompt","").splitlines()[0]
                        last_active = ""
                        for uu, pp, ff in reversed(st.session_state.history):
                            if nm in pp:
                                last_active = pp[nm]
                                break
                        tooltip_text = (
                            f"<strong>{icon} {nm}</strong><br>"
                            f"<em>Role:</em> {pdata.get('role','')}<br>"
                            f"<em>Tagline:</em> {tagline}<br>"
                            f"<em>Last:</em> {last_active[:50]}…"
                        )
                        st.markdown(
                            f"<div class='persona-bubble tooltip' style='text-align:left; margin:5px 0;'>"
                            f"<span style='background-color:{bg}; padding:8px 12px; border-radius:10px; display:inline-block;'>"
                            f"{icon} <strong>{nm}:</strong><br>{ans}"
                            f"</span>"
                            f"<span class='tooltiptext'>{tooltip_text}</span>"
                            f"</div>",
                            unsafe_allow_html=True
                        )
                    st.markdown(
                        f"""<details>
<summary style="font-weight:600; cursor:pointer;">Fusion (synthesized answer):</summary>
<div style="white-space:pre-wrap; margin-top:0.5rem; background-color:#EEE; padding:10px; border-radius:5px;">
{f_text}
</div>
</details>""",
                        unsafe_allow_html=True
                    )
                    st.markdown("")

            else:  # Tabbed view
                tabs = ["User"] + st.session_state.selected
                tab_objs = st.tabs(tabs)
                for idx, label in enumerate(tabs):
                    with tab_objs[idx]:
                        st.subheader(f"{label} Messages")
                        for u_text, pr_dict, f_text in filtered:
                            if label == "User":
                                st.markdown(
                                    f"<div class='chat-bubble' style='text-align:right; margin:10px 0;'>"
                                    f"<span style='background-color:#DCF8C6; padding:8px 12px; border-radius:10px;'>"
                                    f"<strong>You:</strong> {u_text}"
                                    f"</span></div>",
                                    unsafe_allow_html=True
                                )
                            else:
                                if label in pr_dict:
                                    st.markdown(
                                        f"<div class='chat-bubble' style='text-align:right; margin:10px 0;'>"
                                        f"<span style='background-color:#DCF8C6; padding:8px 12px; border-radius:10px;'>"
                                        f"<strong>You:</strong> {u_text}"
                                        f"</span></div>",
                                        unsafe_allow_html=True
                                    )
                                    icon = PERSONA_ICONS.get(label, "")
                                    bg   = PERSONA_COLORS.get(label, "#EEEEEE")
                                    pdata = load_personas()[label]
                                    tagline = pdata.get("prompt","").splitlines()[0]
                                    last_active = ""
                                    for uu, pp, ff in reversed(st.session_state.history):
                                        if label in pp:
                                            last_active = pp[label]
                                            break
                                    tooltip_text = (
                                        f"<strong>{icon} {label}</strong><br>"
                                        f"<em>Role:</em> {pdata.get('role','')}<br>"
                                        f"<em>Tagline:</em> {tagline}<br>"
                                        f"<em>Last:</em> {last_active[:50]}…"
                                    )
                                    ans = pr_dict[label]
                                    st.markdown(
                                        f"<div class='persona-bubble tooltip' style='text-align:left; margin:5px 0;'>"
                                        f"<span style='background-color:{bg}; padding:8px 12px; border-radius:10px; display:inline-block;'>"
                                        f"{icon} <strong>{label}:</strong><br>{ans}"
                                        f"</span>"
                                        f"<span class='tooltiptext'>{tooltip_text}</span>"
                                        f"</div>",
                                        unsafe_allow_html=True
                                    )

# … earlier code …

# ==== TAB 2: Manage Personas ====
with tab2:
    st.header("👥 Manage Personas")
    st.markdown(
        "Create, edit, clone, or delete personas. "
        "Each persona lives in `personas/<name>.json`."
    )

    persons = load_personas()
    if not persons:
        st.info("No persona JSONs found. Create a new one below:")
        name_new = st.text_input("New Persona Name", key="new_name_step5")
        if name_new and st.button("Create Persona"):
            template = {
                "name": name_new,
                "role": "New Role",
                "prompt": "Enter the system prompt here…",
                "goals": ["Goal 1", "Goal 2"],
                "quirks": ["Quirk 1", "Quirk 2"]
            }
            if save_persona_to_disk(template):
                st.success(f"Created '{name_new}'. Reload to see it.")
    else:
        for pname, pdata in persons.items():
            with st.expander(f"🔹 **{pdata['name']}**  •  {pdata.get('role','')}"):
                st.markdown(
                    f"**Role:** {pdata.get('role','')}  \n"
                    f"**Prompt (first line):** {pdata.get('prompt','').splitlines()[0]}"
                )
                col1, col2, col3 = st.columns([1,1,1])
                with col1:
                    if st.button(f"Edit##{pname}", key=f"edit_{pname}_step5"):
                        st.session_state[f"editing_{pname}"] = True
                with col2:
                    if st.button(f"Clone##{pname}", key=f"clone_{pname}_step5"):
                        newname = clone_persona_on_disk(pname)
                        if newname:
                            st.success(f"Cloned to '{newname}'. Reload to see it.")
                        else:
                            st.error("Clone failed.")
                with col3:
                    if st.button(f"Delete##{pname}", key=f"delete_{pname}_step5"):
                        if delete_persona_from_disk(pname):
                            st.warning(f"Deleted '{pname}'. Reload to refresh.")
                        else:
                            st.error("Delete failed.")
                st.markdown("---")

                # === Debug: confirm edit flag ===
                if st.session_state.get(f"editing_{pname}", False):
                    st.write(f"🛠️ [DEBUG] EDIT MODE is active for: {pname}")

                # Only show the form when edit flag is True
                if st.session_state.get(f"editing_{pname}", False):
                    with st.form(f"form_edit_{pname}_step5"):
                        st.subheader(f"✏️ Editing '{pname}'")

                        # 1) Role field
                        new_role = st.text_input(
                            "Role:",
                            value=pdata.get("role",""),
                            key=f"role_{pname}_step5"
                        )

                        # 2) Prompt field
                        new_prompt = st.text_area(
                            "Prompt:",
                            value=pdata.get("prompt",""),
                            height=120,
                            key=f"prompt_{pname}_step5"
                        )
                        # Debug: show what new_prompt actually is
                        st.write(f"🛠️ [DEBUG] new_prompt for {pname} is: '''{new_prompt}'''")

                        # 3) Goals
                        new_goals = st.text_area(
                            "Goals (one per line):",
                            value="\n".join(pdata.get("goals", [])),
                            height=80,
                            key=f"goals_{pname}_step5"
                        )

                        # 4) Quirks
                        new_quirks = st.text_area(
                            "Quirks (one per line):",
                            value="\n".join(pdata.get("quirks", [])),
                            height=80,
                            key=f"quirks_{pname}_step5"
                        )

                        # === Live‐Preview Field & API Call ===
                        test_query = st.text_input(
                            "🎯 Test Query (live preview):",
                            key=f"test_{pname}_step5"
                        )
                        if test_query:
                            st.write(f"🛠️ [DEBUG] test_query for {pname} is: '{test_query}'")
                            with st.spinner("Running live preview…"):
                                try:
                                    resp = client.chat.completions.create(
                                        model="gpt-3.5-turbo",
                                        messages=[
                                            {"role": "system", "content": new_prompt},
                                            {"role": "user",   "content": test_query}
                                        ],
                                        temperature=0.7
                                    )
                                    preview_ans = resp.choices[0].message.content.strip()
                                    st.markdown(f"**Preview →** {preview_ans}")
                                except Exception as e:
                                    st.error(f"🛑 Live‐preview API error: {e}")

                        # === Save Button ===
                        save_button = st.form_submit_button("💾 Save Changes")
                        if save_button:
                            updated = {
                                "name": pname,
                                "role": new_role,
                                "prompt": new_prompt,
                                "goals": [g.strip() for g in new_goals.splitlines() if g.strip()],
                                "quirks": [q.strip() for q in new_quirks.splitlines() if q.strip()]
                            }
                            if save_persona_to_disk(updated):
                                st.success(f"Saved '{pname}'. Rerunning…")
                                st.session_state[f"editing_{pname}"] = False
                                st.experimental_rerun()
                            else:
                                st.error("Save failed.")
