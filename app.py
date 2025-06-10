import os
import json
import datetime
import base64
import glob
import re
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components
from pathlib import Path
import base64
import datetime


from openai import OpenAI

from persona_helpers import (
    load_personas,
    instantiate_persona_objects,
    save_persona_to_disk,
    delete_persona_from_disk,
    clone_persona_on_disk,
    Persona
)
from memory import (
    load_all_memory,
    save_all_memory,
    enforce_memory_config,
    add_memory_entry
)
# 1. Must be first Streamlit command:
st.set_page_config(page_title="Persona Fabric Chat", layout="wide", initial_sidebar_state="expanded")

# 2. Inject global TTS script if any
components.html(
    """
    <script>
      window.playTTS = (rawText) => {
        const utter = new SpeechSynthesisUtterance(rawText);
        utter.rate = 1.0;
        utter.pitch = 1.0;
        window.speechSynthesis.speak(utter);
      };
    </script>
    """,
    height=0,
)

# 3. Define header function
def show_header_with_css():
    # Height of the header bar inside the main content
    header_height = 50  # in px; adjust if needed
    padding_below = 10  # extra space under header

    css = f"""
    <style>
    /* The header container will live inside the main content column (block-container).
       We use position: sticky so it stays visible at top when scrolling the main area. */
    .header-container {{
        position: sticky;
        top: 0;
        left: 0;
        /* width: 100% of its parent (block-container) */
        width: 100%;
        height: {header_height}px;
        background-color: rgba(255, 255, 255, 0.95); /* slightly opaque white */
        display: flex;
        align-items: center;
        padding: 0 16px;  /* padding inside header: adjust left/right as desired */
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        z-index: 100;  /* should be above content but below Streamlit top bar */
    }}
    .header-container img {{
        height: {header_height - 12}px;  /* leave some vertical padding */
        width: auto;
        margin-right: 8px;
    }}
    .header-container .powered {{
        font-size: 0.8rem;
        color: #666;
    }}
    /* Push the block-container content down by header_height + padding_below */
    main > div.block-container {{
        padding-top: {header_height + padding_below}px !important;
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

    # Render the header inside main content
    logo_path = Path(__file__).parent / "assets" / "outlier_logo.png"
    if logo_path.exists():
        data = logo_path.read_bytes()
        b64 = base64.b64encode(data).decode()
        html = f"""
        <div class="header-container">
          <img src="data:image/png;base64,{b64}" alt="Outlier AI logo"/>
          <div class="powered">Powered by Outlier AI, All rights reserved.</div>
        </div>
        """
        st.markdown(html, unsafe_allow_html=True)
    else:
        # If logo not found, warn in sidebar so you notice path issues
        st.sidebar.warning(f"Logo not found at {logo_path}")

# 4. Call header immediately, before any other st.* UI rendering
show_header_with_css()

# 5. Now the rest of your UI
st.markdown(
    """
    <div style="display:flex; align-items:center; justify-content:space-between; width:100%; margin-bottom:10px;">
      <h1 style="margin:0;">🧠 Persona Fabric Chat 1.4.0 (Beta)</h1>
      <span style="font-size:0.9rem; color:gray;">Created by Doruk Dumlu</span>
    </div>
    <hr/>
    """,
    unsafe_allow_html=True
)
# If not already present, ask user for a Room ID
if "room_id" not in st.session_state:
    room_input = st.text_input(
        "🔑 Room ID (leave blank for ‘default’):",
        value="",
        key="room_id_input"
    ).strip()
    st.session_state["room_id"] = room_input if room_input else "default"

ROOM_ID = st.session_state["room_id"]
MEMORY_FILE = f"persona_memory_{ROOM_ID}.json"
LOG_FILE = f"chat_log_{ROOM_ID}.txt"
st.session_state["MEMORY_FILE"] = MEMORY_FILE

# Initialize session_state keys if missing
if "user_input" not in st.session_state:
    st.session_state["user_input"] = ""
if "history" not in st.session_state:
    # Each entry: (user_text, {persona:reply}, fused_text)
    st.session_state["history"] = []
if "selected" not in st.session_state:
    st.session_state["selected"] = []
if "mem" not in st.session_state:
    st.session_state["mem"] = {}
if "pinned" not in st.session_state:
    st.session_state["pinned"] = {}
if "likes" not in st.session_state:
    st.session_state["likes"] = {}
if "theme" not in st.session_state:
    st.session_state["theme"] = "Light"
if "latencies" not in st.session_state:
    st.session_state["latencies"] = {}
if "api_cache" not in st.session_state:
    st.session_state["api_cache"] = {}
if "shared_mem" not in st.session_state:
    st.session_state["shared_mem"] = []
if "last_active" not in st.session_state:
    st.session_state["last_active"] = {}
if "clear_on_next_run" not in st.session_state:
    st.session_state["clear_on_next_run"] = False


# ───────────────────────────────────────────────────────────────────────────────
# CONSTANTS: Icons & Colors per Persona
# ───────────────────────────────────────────────────────────────────────────────

PERSONA_ICONS = {
    "Philosopher":           "📜",
    "Scientist":             "🔬",
    "Empath":                "❤️",
    "Imaginer":              "🌟",
    "Depressed":             "😔",
    "Anxious":               "😰",
    "Daydreamer":            "☁️",
    "Futurist":              "🚀",
    "Surrealist":            "🌀",
    "Realist":               "🛠️",
    "Skeptic":               "❓",
    "Contrarian":            "🦅",
    "Synesthete":            "🎨",
    "Minimalist":            "⚪",
    "ChaoticMuse":           "🎭",
    "TherapeuticListener":   "🛋️",
    "SchizophrenicMind":     "🤯",
    "DevilAdvocate":         "😈",
    "Pacifist":              "🕊️",
    "Technologist":          "🤖",
    "Manipulative":          "🕴️",
    "Narcissist":            "🦚",
    "ConspiracyTheorist":    "🧐",
    "Philanthropist":        "🤲",
    "PassiveAggressive":     "😒",
    "Gaslighter":            "💡",
    "Cynic":                 "😏",
    "Perfectionist":         "🎯",
    "InconvenientEthicist":  "⚖️",
    "RadicalExistentialist": "🕶️"
}

PERSONA_COLORS_LIGHT = {
    "Philosopher":           "#FFF9C4",
    "Scientist":             "#B2EBF2",
    "Empath":                "#FFCDD2",
    "Imaginer":              "#FFFDE7",
    "Depressed":             "#ECEFF1",
    "Anxious":               "#FFEBEE",
    "Daydreamer":            "#E3F2FD",
    "Futurist":              "#FFF3E0",
    "Surrealist":            "#F3E5F5",
    "Realist":               "#CFD8DC",
    "Skeptic":               "#FFECB3",
    "Contrarian":            "#FFCDD2",
    "Synesthete":            "#E1BEE7",
    "Minimalist":            "#F5F5F5",
    "ChaoticMuse":           "#FFF9C4",
    "SchizophrenicMind":     "#E0BBE4",
    "TherapeuticListener":   "#B2DFDB",
    "DevilAdvocate":         "#D32F2F",
    "Pacifist":              "#1976D2",
    "Technologist":          "#388E3C",
    "PassiveAggressive":     "#F44336",
    "Gaslighter":            "#9C27B0",
    "Cynic":                 "#607D8B",
    "Perfectionist":         "#2196F3",
    "Manipulative":          "#D32F2F",
    "Narcissist":            "#FFC107",
    "ConspiracyTheorist":    "#795548",
    "Philanthropist":        "#4CAF50",
    "InconvenientEthicist":  "#FF5722",
    "RadicalExistentialist": "#8E44AD"
}

PERSONA_COLORS_DARK = {
    name: "#2C2C2C"
    for name in PERSONA_ICONS.keys()
}

PERSONA_COLORS_PASTEL = {
    "Philosopher":           "#FFEFD5",
    "Scientist":             "#E6E6FA",
    "Empath":                "#FFDAB9",
    "Imaginer":              "#FAFAD2",
    "Depressed":             "#DCDCDC",
    "Anxious":               "#FFE4E1",
    "Daydreamer":            "#E0FFFF",
    "Futurist":              "#F5F5DC",
    "Surrealist":            "#FFF0F5",
    "Realist":               "#D3D3D3",
    "Skeptic":               "#FFFACD",
    "Contrarian":            "#FFDAB9",
    "Synesthete":            "#E6E6FA",
    "Minimalist":            "#F0F8FF",
    "ChaoticMuse":           "#FFF9C4",
    "SchizophrenicMind":     "#E0BBE4",
    "TherapeuticListener":   "#B2DFDB",
    "DevilAdvocate":         "#F8BBD0",
    "Pacifist":              "#B3E5FC",
    "Technologist":          "#C8E6C9",
    "PassiveAggressive":     "#FFCDD2",
    "Gaslighter":            "#E1BEE7",
    "Cynic":                 "#CFD8DC",
    "Perfectionist":         "#BBDEFB",
    "Manipulative":          "#F8BBD0",
    "Narcissist":            "#FFE082",
    "ConspiracyTheorist":    "#D7CCC8",
    "Philanthropist":        "#C8E6C9",
    "InconvenientEthicist":  "#FFAB91",
    "RadicalExistentialist": "#D1C4E9"
}


# ───────────────────────────────────────────────────────────────────────────────
# HELPER: Inject CSS & JavaScript
# ───────────────────────────────────────────────────────────────────────────────

def inject_css_and_js():
    css_and_js = """
    <style>
      /* 1) Persona‐Card Styles (Collapsible) */
      .persona-card {
        width: 240px;
        border: 1px solid #CCC;
        border-radius: 6px;
        margin: 0.5rem;
        box-shadow: 1px 1px 4px rgba(0,0,0,0.1);
        overflow: hidden;
      }
      .persona-card .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.4rem 0.6rem;
        font-weight: 600;
        cursor: pointer;
      }
      .persona-card .card-header span {
        display: inline-block;
        vertical-align: middle;
      }
      .persona-card .card-header .toggle-btn {
        font-size: 1.2rem;
        line-height: 1;
      }
      .persona-card .card-body {
        display: none;
        padding: 0.6rem;
        background: #FFF;
        white-space: pre-wrap;
      }

      /* Panels */
      .initial-panel, .reflex-panel, .meta-panel {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        margin-bottom: 1rem;
      }

      /* Compact Multiselect Tags (Sidebar) */
      div[data-baseweb="select"] > div[class*="MenuList"] {
        max-height: 100px !important;
        overflow-y: auto !important;
      }
      div[data-baseweb="select"] div[data-baseweb="tag"] {
        font-size: 0.75rem !important;
        padding: 2px 4px !important;
        margin: 2px 2px !important;
      }
      div[data-baseweb="select"] .valueContainer {
        flex-wrap: wrap !important;
        gap: 2px !important;
      }
      div[data-baseweb="select"] {
        width: 200px !important;
      }

      /* Mobile / Responsive Tweaks */
      @media (max-width: 600px) {
        .initial-panel, .reflex-panel, .meta-panel {
          flex-direction: column;
        }
        .persona-card {
          width: 100%;
        }
        #stSidebar, #stHeader, #stFooter {
          display: none;
        }
        .chat-bubble, .persona-bubble {
          width: 100% !important;
          margin: 5px 0 !important;
        }
        .chat-bubble-text, .persona-bubble-text {
          display: none !important;
        }
        .collapsed {
          display: inline !important;
        }
      }

      /* Two-column “Chatting with:” list */
      .chatting-with-list {
        list-style-type: disc;
        padding-left: 1.2rem;
        columns: 2;
        column-gap: 2rem;
        margin-bottom: 1rem;
      }
      .chatting-with-list li {
        margin-bottom: 0.2rem;
        font-size: 1rem;
      }
      @media (max-width: 600px) {
        .chatting-with-list {
          columns: 1;
        }
      }
    </style>

    <script>
      function toggleBody(elemId) {
        const card = document.getElementById(elemId);
        if (!card) return;
        const body = card.querySelector('.card-body');
        const btn  = card.querySelector('.toggle-btn');
        if (!body || !btn) return;
        if (body.style.display === 'block') {
          body.style.display = 'none';
          btn.innerText = '▼';
        } else {
          body.style.display = 'block';
          btn.innerText = '▲';
        }
      }
    </script>
    """
    st.markdown(css_and_js, unsafe_allow_html=True)


inject_css_and_js()


# ───────────────────────────────────────────────────────────────────────────────
# FUNCTION: Load personas (cached)
# ───────────────────────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False, ttl=1)  # ttl=1 second forces reload
def cached_load_personas():
    """
    Look for every JSON file under ./personas (relative to this .py),
    parse it, and return a dict mapping <filename-without-.json>→<parsed JSON>.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    persona_dir = os.path.join(base_dir, "personas")

    if not os.path.isdir(persona_dir):
        return {}  # nothing found

    loaded = {}
    pattern = os.path.join(persona_dir, "*.json")
    for filepath in glob.glob(pattern):
        try:
            name = os.path.splitext(os.path.basename(filepath))[0]
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            loaded[name] = data
        except Exception as e:
            st.warning(f"⚠️ Could not load {filepath}: {e}")
            continue

    return loaded


# ───────────────────────────────────────────────────────────────────────────────
# ATTEMPT TO LOAD ALL PERSONAS
# ───────────────────────────────────────────────────────────────────────────────

persons = cached_load_personas()

if not persons:
    st.warning(
        "⚠️ No personas were found by cached_load_personas(). "
        "Please confirm that your JSON files live in the “personas/” folder "
        "(next to this script), that each filename ends in .json, "
        "and that the JSON syntax is valid."
    )

# ───────────────────────────────────────────────────────────────────────────────
# INITIALIZE SESSION STATE FOR PERSONA SELECTION
# ───────────────────────────────────────────────────────────────────────────────

if "selected" not in st.session_state or not st.session_state["selected"]:
    st.session_state["selected"] = list(persons.keys())

# ───────────────────────────────────────────────────────────────────────────────
# LOAD MEMORY ON STARTUP (IF NEEDED)
# ───────────────────────────────────────────────────────────────────────────────

needs_memory_initialization = (
    "mem" not in st.session_state
    or not st.session_state.get("mem")
    or "pinned" not in st.session_state
    or not st.session_state.get("pinned")
    or "shared_mem" not in st.session_state
    or not st.session_state.get("shared_mem")
)

if needs_memory_initialization:
    persona_names = list(persons.keys())
    m, p, shared = load_all_memory(persona_names)
    st.session_state["mem"] = m
    st.session_state["pinned"] = p
    st.session_state["shared_mem"] = shared

# ───────────────────────────────────────────────────────────────────────────────
# INITIALIZE OpenAI CLIENT
# ───────────────────────────────────────────────────────────────────────────────

api_key = os.getenv("OPENAI_API_KEY", "")
if not api_key:
    st.error("⚠️ OPENAI_API_KEY environment variable is missing.")
    client = None
else:
    client = OpenAI(api_key=api_key)


# ───────────────────────────────────────────────────────────────────────────────
# FUNCTION: Build messages for a given persona (Initial round only)
# ───────────────────────────────────────────────────────────────────────────────

def build_messages(persona_name: str, user_text: str) -> list[dict[str, str]]:
    persons_local = load_personas()
    pdata = persons_local[persona_name]
    messages: list[dict[str, str]] = []

    # (1) Shared‐memory system message
    shared = st.session_state.get("shared_mem", [])
    if shared:
        shared_text = "\n\n".join(entry["content"] for entry in shared)
        messages.append({
            "role": "system",
            "content": "Shared context (what all personas have said so far):\n\n" + shared_text
        })

    # (2) Few‐shot examples (if any)
    for ex in pdata.get("examples", []):
        messages.append({"role": "user", "content": ex["user"]})
        messages.append({"role": "assistant", "content": ex["assistant"]})

    # (3) Persona’s dynamic system prompt (initial round)
    base_prompt = pdata["rounds"]["initial"]

    # (3b) Parameter tags
    param_labels = []
    for param_name, default_val in pdata.get("parameters", {}).items():
        sess_key = f"{persona_name}_{param_name}"
        val = st.session_state.get(sess_key, default_val)
        param_labels.append(f"{param_name}={val}")
    if param_labels:
        base_prompt = base_prompt + "\n\n[" + ", ".join(param_labels) + "]"

    messages.append({"role": "system", "content": base_prompt})

    # (4) Pinned entries for this persona
    for entry in st.session_state["pinned"].get(persona_name, []):
        if isinstance(entry, dict):
            messages.append(entry)
        elif isinstance(entry, tuple) and len(entry) == 2:
            messages.append({"role": "assistant", "content": entry[1]})

    # (5) Last 3 raw memory entries
    all_raw = st.session_state["mem"].get(persona_name, [])
    last_n = 3
    recent_entries = all_raw[-last_n:] if len(all_raw) > last_n else all_raw[:]
    for entry in recent_entries:
        messages.append(entry)

    # (6) Finally, append the new user turn
    messages.append({"role": "user", "content": user_text})
    return messages


# ───────────────────────────────────────────────────────────────────────────────
# FUNCTION: Chat with a single persona (Initial or a custom system prompt)
# ───────────────────────────────────────────────────────────────────────────────

def chat_with_persona(persona_name: str, user_text_or_prompt: str, is_initial: bool = True) -> str:
    """
    If is_initial=True, build messages with build_messages(). Otherwise, send user_text_or_prompt
    directly as a single system message to that persona.
    """
    if is_initial:
        msgs = build_messages(persona_name, user_text_or_prompt)
    else:
        # Custom system prompt only
        msgs = [{"role": "system", "content": user_text_or_prompt}]

    start = datetime.datetime.now()
    try:
        resp = client.chat.completions.create(
            model="gpt-3.5-turbo-16k",
            messages=msgs,
            temperature=0.7
        )
        reply = resp.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"💥 [DEBUG] Persona '{persona_name}' API call failed: {e}")
        reply = f"[Error: {e}]"

    latency = (datetime.datetime.now() - start).total_seconds()
    st.session_state["latencies"].setdefault(persona_name, []).append(latency)

    if is_initial:
        timestamp = datetime.datetime.now().isoformat()
        user_entry = {"role": "user", "content": user_text_or_prompt, "ts": timestamp}
        assistant_entry = {"role": "assistant", "content": reply, "ts": timestamp}

        st.session_state["mem"].setdefault(persona_name, []).append(user_entry)
        st.session_state["mem"][persona_name].append(assistant_entry)

        enforce_memory_config(persona_name, st.session_state["mem"], st.session_state["pinned"])
        add_memory_entry(persona_name, reply, st.session_state["mem"], st.session_state["pinned"])

        st.session_state["shared_mem"].append({
            "role": "assistant",
            "content": f"[Shared] {persona_name} replied: {reply}",
            "ts": timestamp
        })
        save_all_memory(st.session_state["mem"], st.session_state["pinned"], st.session_state["shared_mem"])

    return reply


# ───────────────────────────────────────────────────────────────────────────────
# FUNCTION: Render “reflexive” or “meta” persona prompt with placeholder substitution
# ───────────────────────────────────────────────────────────────────────────────

def render_persona_prompt(persona_name: str,
                          round_name: str,
                          selected: list[str],
                          last_round1: dict[str, str],
                          last_round2: dict[str, str]) -> str:
    """
    - persona_name:    e.g. "Empath"
    - round_name:      "reflexive" or "meta"
    - selected:        the ordered list of currently selected personas
    - last_round1:     dict mapping persona→its Round 1 text
    - last_round2:     dict mapping persona→its Round 2 text
    """
    template = cached_load_personas()[persona_name]["rounds"].get(round_name, "").strip()

    try:
        my_idx = selected.index(persona_name)
    except ValueError:
        return template

    num_selected = len(selected)
    if num_selected == 0:
        return template

    # Peer for Round 1 placeholder: next persona in list
    peer1_idx = (my_idx + 1) % num_selected
    peer1_name = selected[peer1_idx]
    quote1 = last_round1.get(peer1_name, "")

    # Peer for Round 2 placeholder: next after peer1
    peer2_idx = (peer1_idx + 1) % num_selected
    peer2_name = selected[peer2_idx]
    quote2 = last_round2.get(peer2_name, "")

    rendered = template
    rendered = re.sub(r"\{\{QUOTE_PEER_R1\}\}", quote1, rendered)
    rendered = re.sub(r"\{\{QUOTE_PEER_R2\}\}", quote2, rendered)
    return rendered


# ───────────────────────────────────────────────────────────────────────────────
# FUNCTION: Fuse persona replies
# ───────────────────────────────────────────────────────────────────────────────

def fuse_persona_replies(persona_replies: dict[str, str]) -> str:
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
            model="gpt-3.5-turbo-16k",
            messages=messages,
            temperature=0.7
        )
        fused = resp.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"💥 [DEBUG] Fusion call failed: {e}")
        fused = f"[Fusion Error: {e}]"
    return fused


# ───────────────────────────────────────────────────────────────────────────────
# FUNCTION: Log conversation to file
# ───────────────────────────────────────────────────────────────────────────────

def log_conversation(user_input: str, persona_replies: dict[str, str], fused_reply: str):
    timestamp = datetime.datetime.now().isoformat()
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as logfile:
            logfile.write(f"[{timestamp}] You: {user_input}\n")
            for nm, ans in persona_replies.items():
                logfile.write(f"[{timestamp}] [{nm}]: {ans}\n")
            logfile.write(f"[{timestamp}] [Fusion]: {fused_reply}\n\n")
    except Exception as e:
        st.error(f"Failed to write to log: {e}")


tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "💬 Chat",
    "👥 Manage Personas",
    "⚙️ Settings",
    "ℹ️ Info",
    "📊 Analytics"
])


# ==============================================================================#
# TAB 1: Chat
# ==============================================================================#
with tab1:
    persons = cached_load_personas()
    if not persons:
        st.warning("No personas found. Go to 'Manage Personas' to add one.")
    else:
        # ───────────────────────────────────────────────────────────────────────
        # Sidebar: Chat Controls, Persona Selection/Reordering, Memory Controls
        # ───────────────────────────────────────────────────────────────────────
        with st.sidebar:
            st.header("Chat Controls")

            # 1) “Clear All Memory & History” button
            if st.button("🔄 Clear All Memory & History"):
                st.session_state["mem"] = {n: [] for n in persons.keys()}
                st.session_state["pinned"] = {n: [] for n in persons.keys()}
                st.session_state["history"] = []
                st.session_state["likes"] = {}
                st.session_state["latencies"] = {}
                if os.path.exists(st.session_state["MEMORY_FILE"]):
                    os.remove(st.session_state["MEMORY_FILE"])
                if os.path.exists(LOG_FILE):
                    os.remove(LOG_FILE)
                st.success("Cleared memory & history. Refresh to reset.")

            st.markdown("---")

            # 2) “Choose Personas” expander
            with st.expander("▶ Choose Personas", expanded=True):
                st.write("Select which personas should participate:")
                valid_names = list(persons.keys())
                new_selected = []
                for name in valid_names:
                    is_checked = name in st.session_state.get("selected", [])
                    if st.checkbox(name, value=is_checked, key=f"cb_{name}"):
                        new_selected.append(name)
                st.session_state["selected"] = new_selected

            st.markdown("---")

            # 3) Pinned Messages
            st.write("**Pinned Messages**")
            for pname, pinned_list in st.session_state["pinned"].items():
                if pinned_list:
                    st.subheader(f"{pname}")
                    for (ridx, txt) in pinned_list:
                        st.text(f"Round {ridx}: {txt[:30]}…")

            # 4) Memory Controls
            st.markdown("---")
            st.subheader("🗑️ Memory Controls")

            all_personas = list(persons.keys())
            target_persona = st.selectbox(
                "Persona to manage:",
                options=all_personas,
                index=0,
                key="memory_persona_select"
            )

            forget_mode = st.radio(
                "Forget method:",
                options=["Older than days", "First N entries"],
                key="forget_mode_radio"
            )

            if forget_mode == "Older than days":
                days = st.number_input(
                    "Days (older than):",
                    min_value=1,
                    value=7,
                    step=1,
                    key="forget_days_input"
                )
                if st.button("Clear memory older than days", key="forget_old_btn"):
                    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
                    old_list = st.session_state["mem"].get(target_persona, [])
                    new_list, removed_count = [], 0
                    for entry in old_list:
                        try:
                            entry_ts = datetime.datetime.fromisoformat(entry.get("ts", "")[:19])
                        except Exception:
                            new_list.append(entry)
                            continue
                        if entry_ts < cutoff:
                            removed_count += 1
                        else:
                            new_list.append(entry)
                    st.session_state["mem"][target_persona] = new_list
                    save_all_memory(
                        st.session_state["mem"],
                        st.session_state["pinned"],
                        st.session_state["shared_mem"]
                    )
                    st.success(
                        f"Removed {removed_count} entries older than {days} days from “{target_persona}.”"
                    )
            else:  # “First N entries”
                n = st.number_input(
                    "Number of entries to remove:",
                    min_value=1,
                    value=1,
                    step=1,
                    key="forget_first_n_input"
                )
                if st.button("Clear first N memory entries", key="forget_first_btn"):
                    old_list = st.session_state["mem"].get(target_persona, [])
                    if not old_list:
                        st.warning(f"No memory to clear for “{target_persona}.”")
                    else:
                        removed_chunk = old_list[:n]
                        st.session_state["mem"][target_persona] = old_list[n:]
                        save_all_memory(
                            st.session_state["mem"],
                            st.session_state["pinned"],
                            st.session_state["shared_mem"]
                        )
                        st.success(
                            f"Removed first {min(n, len(removed_chunk))} entries from “{target_persona}.”"
                        )

            # 5) Pin Memory Items
            st.markdown("---")
            st.subheader("📌 Pin Memory Items")

            pin_persona = st.selectbox(
                "Select persona to view memory:",
                options=all_personas,
                index=0,
                key="pin_persona_select"
            )

            mem_entries = st.session_state["mem"].get(pin_persona, [])
            if mem_entries:
                with st.expander(f"{pin_persona} memory entries ({len(mem_entries)})"):
                    for idx, entry in enumerate(mem_entries):
                        role = entry.get("role", "")
                        content = entry.get("content", "")
                        ts = entry.get("ts", "")[:19]
                        st.markdown(f"**{idx + 1}. [{role}]** {content}  \n_ts: {ts}_")
                        already_pinned = any(
                            isinstance(p, dict) and p.get("content") == content and p.get("role") == role
                            for p in st.session_state["pinned"].get(pin_persona, [])
                        )
                        if not already_pinned:
                            if st.button(f"Pin entry #{idx + 1}", key=f"pin_mem_{pin_persona}_{idx}"):
                                st.session_state["pinned"].setdefault(pin_persona, []).append(entry)
                                save_all_memory(
                                    st.session_state["mem"],
                                    st.session_state["pinned"],
                                    st.session_state["shared_mem"]
                                )
                                st.success(f"Pinned entry #{idx + 1} for “{pin_persona}.”")
                        else:
                            if st.button(f"Unpin entry #{idx + 1}", key=f"unpin_mem_{pin_persona}_{idx}"):
                                new_pins = [
                                    p for p in st.session_state["pinned"].get(pin_persona, [])
                                    if not (isinstance(p, dict) and p.get("content") == content and p.get("role") == role)
                                ]
                                st.session_state["pinned"][pin_persona] = new_pins
                                save_all_memory(
                                    st.session_state["mem"],
                                    st.session_state["pinned"],
                                    st.session_state["shared_mem"]
                                )
                                st.success(f"Unpinned entry #{idx + 1} for “{pin_persona}.”")
                        st.markdown("---")
            else:
                st.write(f"No memory entries found for “{pin_persona}.”")

            st.markdown("---")
            st.markdown("**Make sure OPENAI_API_KEY is set.**")

        if not st.session_state["selected"]:
            st.warning("Select at least one persona.")
            st.stop()

        # ───────────────────────────────────────────────────────────────────────
        # Main Chat Area
        # ───────────────────────────────────────────────────────────────────────

        view_mode = st.radio("View Mode:", ["Single Feed", "Tabbed"], horizontal=True)

        selected_personas = st.session_state["selected"]
        persona_list_html = "<strong>Chatting with:</strong><br><br>"
        persona_list_html += "<ul class='chatting-with-list'>"
        for p in selected_personas:
            persona_list_html += f"<li>{p}</li>"
        persona_list_html += "</ul>"
        st.markdown(persona_list_html, unsafe_allow_html=True)

        # Timeline Sidebar
        history_len = len(st.session_state["history"])
        if history_len > 0:
            timeline_html = "<div id='timeline-sidebar'>"
            for idx_round, (u, pr, fz) in enumerate(st.session_state["history"]):
                preview = u[:20].replace('"', '&quot;') + "…"
                dot_class = "timeline-dot"
                liked_flag = any(
                    st.session_state["likes"].get((idx_round, nm), False)
                    for nm in pr.keys()
                )
                if liked_flag:
                    dot_class += " liked"
                timeline_html += (
                    f"<a href='#round-{idx_round}'><div class='{dot_class}' "
                    f"data-preview='{preview}'></div></a>"
                )
            timeline_html += "</div>"
            st.markdown(timeline_html, unsafe_allow_html=True)

        # ───────────────────────────────────────────────────────────────────────
        # Input Form (with STT widget)
        # ───────────────────────────────────────────────────────────────────────

        if st.session_state["clear_on_next_run"]:
            st.session_state["user_input"] = ""
            st.session_state["clear_on_next_run"] = False

        with st.form("chat_form", clear_on_submit=False):
            components.html(
                """
                <div id="stt-widget" style="margin-bottom:8px;">
                  <button id="start-btn" style="
                       background-color:#4CAF50;
                       color:white;
                       border:none;
                       border-radius:4px;
                       padding:6px 12px;
                       font-size:14px;
                       cursor:pointer;
                      ">
                    🎤 Speak
                  </button>
                  <span id="stt-status" style="margin-left:8px;color:gray;font-size:0.9rem;">
                    (click 🎤 and speak…)
                  </span>
                </div>

                <script>
                  const statusSpan = document.getElementById("stt-status");
                  const startBtn = document.getElementById("start-btn");

                  if (!("webkitSpeechRecognition" in window) && !("SpeechRecognition" in window)) {
                    startBtn.disabled = true;
                    statusSpan.textContent = "— Speech recognition not supported";
                  } else {
                    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
                    const recognition = new SpeechRec();
                    recognition.lang = "en-US";
                    recognition.interimResults = false;
                    recognition.maxAlternatives = 1;

                    recognition.onstart = () => {
                      statusSpan.textContent = "Listening…";
                    };
                    recognition.onerror = (event) => {
                      statusSpan.textContent = "Error: " + event.error;
                    };
                    recognition.onend = () => {
                      statusSpan.textContent = "(click 🎤 to speak)";
                    };
                    recognition.onresult = (event) => {
                      const transcript = event.results[0][0].transcript;
                      const inputBox = window.parent.document.querySelector('input[aria-label="You:"]');
                      if (inputBox) {
                        inputBox.value = transcript;
                      }
                      const submitBtn = window.parent.document.querySelector('button[data-testid="stFormSubmit"]');
                      if (submitBtn) {
                        submitBtn.click();
                      }
                    };

                    startBtn.addEventListener("click", () => {
                      recognition.start();
                    });
                  }
                </script>
                """,
                height=0,
            )

            user_input = st.text_input(
                "You:", key="user_input", placeholder="Type your message here…"
            )

            send_clicked = st.form_submit_button("Send")

        # ───────────────────────────────────────────────────────────────────────
        # Handle “Send” → Round 1 (Initial) + Round 2 (Reflexive) + Round 3 (Meta)
        # ───────────────────────────────────────────────────────────────────────

        if send_clicked:
            user_text = user_input.strip()
            if not user_text:
                st.warning("Please type something before pressing Send.")
            else:
                # ── ROUND 1: INITIAL REPLIES ────────────────────────────────────────
                initial_replies: dict[str, str] = {}
                for persona_name in st.session_state["selected"]:
                    reply = chat_with_persona(persona_name, user_text, is_initial=True)
                    initial_replies[persona_name] = reply
                    st.session_state["last_active"][persona_name] = datetime.datetime.now().strftime("%I:%M %p")

                st.session_state["__initial_replies__"] = initial_replies
                last_round1 = initial_replies.copy()
                all_initial_block = "\n\n".join(f"[{p}]: {txt}" for p, txt in initial_replies.items())

                # ── ROUND 2: REFLEXIVE COMMENTS ──────────────────────────────────────
                reflexive_replies: dict[str, str] = {}
                for persona_name in st.session_state["selected"]:
                    reflexive_prompt = render_persona_prompt(
                        persona_name=persona_name,
                        round_name="reflexive",
                        selected=st.session_state["selected"],
                        last_round1=last_round1,
                        last_round2={}
                    )
                    # Substitute {{ALL_INITIAL}} if present
                    reflexive_prompt = reflexive_prompt.replace("{{ALL_INITIAL}}", all_initial_block)

                    reflexive_comment = chat_with_persona(persona_name, reflexive_prompt, is_initial=False)
                    reflexive_replies[persona_name] = reflexive_comment
                    st.session_state["last_active"][persona_name] = datetime.datetime.now().strftime("%I:%M %p")

                st.session_state["__reflexive_replies__"] = reflexive_replies
                last_round2 = reflexive_replies.copy()
                all_reflex_block = "\n\n".join(f"[{p}]: {c}" for p, c in reflexive_replies.items())

                # ── ROUND 3: META COMMENTARY ────────────────────────────────────────
                meta_replies: dict[str, str] = {}
                for persona_name in st.session_state["selected"]:
                    meta_prompt = render_persona_prompt(
                        persona_name=persona_name,
                        round_name="meta",
                        selected=st.session_state["selected"],
                        last_round1=last_round1,
                        last_round2=last_round2
                    )
                    # Substitute {{ALL_REFLEX}} if present
                    meta_prompt = meta_prompt.replace("{{ALL_REFLEX}}", all_reflex_block)

                    meta_comment = chat_with_persona(persona_name, meta_prompt, is_initial=False)
                    meta_replies[persona_name] = meta_comment
                    st.session_state["last_active"][persona_name] = datetime.datetime.now().strftime("%I:%M %p")

                st.session_state["__meta_replies__"] = meta_replies

                # Save user’s text for fusion/logging
                st.session_state["__last_user__"] = user_text

                # Prepare “download all‐rounds” JSON payload
                metasynth = {
                    "user_message": user_text,
                    "initial_replies": initial_replies,
                    "reflex_replies": reflexive_replies,
                    "meta_replies": meta_replies,
                    "generated_at": datetime.datetime.now().isoformat()
                }
                json_str = json.dumps(metasynth, ensure_ascii=False, indent=2)
                b64 = base64.b64encode(json_str.encode("utf-8")).decode("utf-8")
                href = f"<a href='data:application/json;base64,{b64}' download='metasynth_all_rounds.json'>📥 Download All-Rounds JSON</a>"
                st.markdown(href, unsafe_allow_html=True)

                # Schedule clearing the input box on next run
                st.session_state["clear_on_next_run"] = True

        # ───────────────────────────────────────────────────────────────────────
        # COLLAPSIBLE PANELS & FUSION TOOLBAR (with Meta-Commentary)
        # ───────────────────────────────────────────────────────────────────────

        if "__initial_replies__" in st.session_state:
            st.markdown("### ▼ Initial Replies")
            st.markdown("<div class='initial-panel'>", unsafe_allow_html=True)
            for pname, reply in st.session_state["__initial_replies__"].items():
                avatar = cached_load_personas()[pname].get("avatar", PERSONA_ICONS.get(pname, ""))
                last_ts = st.session_state.get("last_active", {}).get(pname, "Now")
                if st.session_state["theme"] == "Dark":
                    bgcolor = PERSONA_COLORS_DARK.get(pname, "#333333")
                    txtcolor = "#FFFFFF"
                elif st.session_state["theme"] == "Pastel":
                    bgcolor = PERSONA_COLORS_PASTEL.get(pname, "#FFFFFF")
                    txtcolor = "#000000"
                else:
                    bgcolor = PERSONA_COLORS_LIGHT.get(pname, "#EEEEEE")
                    txtcolor = "#000000"

                safe_reply = reply.replace("'", "&#39;").replace("\n", "<br>")
                st.markdown(f"""
                  <details style="background:{bgcolor}; color:{txtcolor}; border-radius:6px; margin-bottom:8px; padding:0;">
                    <summary style="padding:0.6rem; cursor:pointer; list-style:none;">
                      {avatar}&nbsp;<strong>{pname}</strong> &nbsp;🕒 {last_ts} <span style="float:right;">▼</span>
                    </summary>
                    <div style="padding:0.6rem; background:#FFF; color:#000; border-top:1px solid #CCC; border-bottom-left-radius:6px; border-bottom-right-radius:6px;">
                      {safe_reply}
                    </div>
                  </details>
                """, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("---")

        if "__reflexive_replies__" in st.session_state:
            st.markdown("### ▼ Reflexive Comments")
            st.markdown("<div class='reflex-panel'>", unsafe_allow_html=True)
            for pname, comment in st.session_state["__reflexive_replies__"].items():
                avatar = cached_load_personas()[pname].get("avatar", PERSONA_ICONS.get(pname, ""))
                last_ts = st.session_state.get("last_active", {}).get(pname, "Now")
                if st.session_state["theme"] == "Dark":
                    bgcolor = PERSONA_COLORS_DARK.get(pname, "#333333")
                    txtcolor = "#FFFFFF"
                elif st.session_state["theme"] == "Pastel":
                    bgcolor = PERSONA_COLORS_PASTEL.get(pname, "#FFFFFF")
                    txtcolor = "#000000"
                else:
                    bgcolor = PERSONA_COLORS_LIGHT.get(pname, "#EEEEEE")
                    txtcolor = "#000000"

                safe_comment = comment.replace("'", "&#39;").replace("\n", "<br>")
                st.markdown(f"""
                  <details style="background:{bgcolor}; color:{txtcolor}; border-radius:6px; margin-bottom:8px; padding:0;">
                    <summary style="padding:0.6rem; cursor:pointer; list-style:none;">
                      {avatar}&nbsp;<strong>{pname} (on others)</strong> &nbsp;🕒 {last_ts} <span style="float:right;">▼</span>
                    </summary>
                    <div style="padding:0.6rem; background:#FFF; color:#000; border-top:1px solid #CCC; border-bottom-left-radius:6px; border-bottom-right-radius:6px;">
                      {safe_comment}
                    </div>
                  </details>
                """, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("---")

        if "__meta_replies__" in st.session_state:
            st.markdown("### ▼ Meta-Commentary")
            st.markdown("<div class='meta-panel'>", unsafe_allow_html=True)
            for pname, comment in st.session_state["__meta_replies__"].items():
                avatar = cached_load_personas()[pname].get("avatar", PERSONA_ICONS.get(pname, ""))
                last_ts = st.session_state.get("last_active", {}).get(pname, "Now")
                if st.session_state["theme"] == "Dark":
                    bgcolor = PERSONA_COLORS_DARK.get(pname, "#333333")
                    txtcolor = "#FFFFFF"
                elif st.session_state["theme"] == "Pastel":
                    bgcolor = PERSONA_COLORS_PASTEL.get(pname, "#FFFFFF")
                    txtcolor = "#000000"
                else:
                    bgcolor = PERSONA_COLORS_LIGHT.get(pname, "#EEEEEE")
                    txtcolor = "#000000"

                safe_meta = comment.replace("'", "&#39;").replace("\n", "<br>")

                st.markdown(f"""
                  <details style="background:{bgcolor}; color:{txtcolor}; border-radius:6px; margin-bottom:8px; padding:0;">
                    <summary style="padding:0.6rem; cursor:pointer; list-style:none;">
                      {avatar}&nbsp;<strong>{pname} (meta)</strong> &nbsp;🕒 {last_ts} <span style="float:right;">▼</span>
                    </summary>
                    <div style="padding:0.6rem; background:#FFF; color:#000; border-top:1px solid #CCC; border-bottom-left-radius:6px; border-bottom-right-radius:6px;">
                      {safe_meta}
                    </div>
                  </details>
                """, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("---")

        # ───────────────────────────────────────────────────────────────────────
        # FUSION TOOLBAR (requires Initial + Reflexive + Meta)
        # ───────────────────────────────────────────────────────────────────────

        if ("__initial_replies__" in st.session_state) and ("__reflexive_replies__" in st.session_state) and ("__meta_replies__" in st.session_state):
            col1, col2 = st.columns([1, 1])
            with col1:
                if st.button("🔗 Final Fuse All"):
                    initial_block = "\n\n".join(
                        f"[{p}]: {a}" for p, a in st.session_state["__initial_replies__"].items()
                    )
                    reflex_block = "\n\n".join(
                        f"[{p}]: {c}" for p, c in st.session_state["__reflexive_replies__"].items()
                    )
                    meta_block = "\n\n".join(
                        f"[{p}]: {m}" for p, m in st.session_state["__meta_replies__"].items()
                    )
                    combined_text = (
                        "Initial Replies (Round 1):\n\n" + initial_block
                        + "\n\nReflexive Comments (Round 2):\n\n" + reflex_block
                        + "\n\nMeta-Commentary (Round 3):\n\n" + meta_block
                    )
                    fused = fuse_persona_replies({"all": combined_text})
                    st.session_state["__fused_all_rounds__"] = fused

                    # Append to history & log
                    st.session_state["history"].append((
                        st.session_state["__last_user__"],
                        st.session_state["__initial_replies__"],
                        fused
                    ))
                    log_conversation(
                        st.session_state["__last_user__"],
                        st.session_state["__initial_replies__"],
                        fused
                    )

                    # Clear state for next round
                    del st.session_state["__initial_replies__"]
                    del st.session_state["__reflexive_replies__"]
                    del st.session_state["__meta_replies__"]
                    del st.session_state["__last_user__"]

            with col2:
                metasynth = {
                    "user_message": st.session_state.get("__last_user__", ""),
                    "initial_replies": st.session_state.get("__initial_replies__", {}),
                    "reflex_replies": st.session_state.get("__reflexive_replies__", {}),
                    "meta_replies":   st.session_state.get("__meta_replies__", {}),
                    "generated_at":   datetime.datetime.now().isoformat()
                }
                json_str = json.dumps(metasynth, ensure_ascii=False, indent=2)
                b64 = base64.b64encode(json_str.encode("utf-8")).decode("utf-8")
                href = f"<a href='data:application/json;base64,{b64}' download='metasynth_all_rounds.json'>📥 Download All-Rounds JSON</a>"
                st.markdown(href, unsafe_allow_html=True)

            st.markdown("---")

            if "__fused_all_rounds__" in st.session_state:
                st.markdown("### 📦 Final Fused Result")
                fused_text = st.session_state["__fused_all_rounds__"].replace("\n", "<br>")
                st.markdown(f"""
                  <div style="background:#EFEFEF; padding:1rem; border-radius:6px; white-space: pre-wrap;">
                    {fused_text}
                  </div>
                """, unsafe_allow_html=True)

        elif "__last_user__" in st.session_state:
            st.info("Adjust any panels above, then click 🔗 Final Fuse All when ready.")

        # ───────────────────────────────────────────────────────────────────────
        # HISTORY DISPLAY (Single Feed or Tabbed)
        # ───────────────────────────────────────────────────────────────────────

        def highlight(text: str, term: str) -> str:
            if not term:
                return text
            low_text = text.lower()
            low_term = term.lower().strip()
            if low_term == "":
                return text
            result = ""
            i = 0
            L = len(low_term)
            while True:
                idx = low_text.find(low_term, i)
                if idx == -1:
                    result += text[i:]
                    break
                result += text[i:idx]
                match_str = text[idx:idx + L]
                result += f"<mark>{match_str}</mark>"
                i = idx + L
            return result

        search_term = st.text_input("🔍 Search History", key="search_history", placeholder="Keyword…")

        if search_term:
            filtered = [
                (u, pr, fz)
                for (u, pr, fz) in st.session_state["history"]
                if search_term.lower() in u.lower()
                or any(search_term.lower() in ans.lower() for ans in pr.values())
                or (fz and search_term.lower() in fz.lower())
            ]
        else:
            filtered = st.session_state["history"]

        last_persona = None
        if st.session_state["history"]:
            last_persona = st.session_state["selected"][-1]

        st.markdown("<a name='bottom'></a>", unsafe_allow_html=True)

        if view_mode == "Single Feed":
            for orig_idx, (u_text, pr_dict, f_text) in enumerate(filtered):
                if search_term:
                    low_term = search_term.lower()
                    if (
                        low_term not in u_text.lower()
                        and all(low_term not in ans.lower() for ans in pr_dict.values())
                        and (f_text is None or low_term not in f_text.lower())
                    ):
                        continue

                st.markdown(f'<a name="round-{orig_idx}"></a>', unsafe_allow_html=True)
                st.markdown(
                    f'<div style="font-size:0.9rem; margin-bottom:4px;">'
                    f'<a href="#round-{orig_idx}">➤ Jump to round {orig_idx}</a>'
                    f'</div>',
                    unsafe_allow_html=True
                )

                # User bubble
                u_disp = highlight(u_text, search_term)
                st.markdown(
                    f"""
                    <div class='chat-bubble' style='text-align:right; margin:10px 0;'>
                      <span style='background-color:#DCF8C6; padding:8px 12px; border-radius:10px;'>
                        <strong>You:</strong> <span class='chat-bubble-text'>{u_disp}</span>
                        <span class='collapsed'>
                          {PERSONA_ICONS.get('CuriousChild','…')}&nbsp;{u_disp[:20]}…
                        </span>
                      </span>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                # Persona bubbles
                for nm, ans in pr_dict.items():
                    pdata = cached_load_personas()[nm]
                    icon = pdata.get("avatar", PERSONA_ICONS.get(nm, ""))
                    tagline = pdata.get("tagline", "")

                    if st.session_state["theme"] == "Dark":
                        bg = PERSONA_COLORS_DARK.get(nm, "#333333")
                        txtc = "#FFFFFF"
                    elif st.session_state["theme"] == "Pastel":
                        bg = PERSONA_COLORS_PASTEL.get(nm, "#FFFFFF")
                        txtc = "#000000"
                    else:
                        bg = PERSONA_COLORS_LIGHT.get(nm, "#EEEEEE")
                        txtc = "#000000"

                    last_ts = st.session_state.get("last_active", {}).get(nm, "Now")
                    profile_html = (
                        f"<span class='profile-card'>{icon} <strong>{nm}</strong>"
                        f"<div class='card-content'>"
                        f"<div><strong>Tagline:</strong> {tagline}</div>"
                        f"<div><strong>Last active:</strong> {last_ts}</div>"
                        f"</div></span>"
                    )

                    ans_disp = highlight(ans, search_term)
                    st.markdown(
                        f"""
                        <div class='persona-bubble tooltip' style='text-align:left; margin:5px 0;'>
                          <div style='background-color:{bg}; color:{txtc}; padding:8px 12px; border-radius:10px;'>
                            {profile_html}<br>
                            <span class='persona-bubble-text'>{ans_disp}</span>
                            <span class='collapsed'>{icon}&nbsp;{ans_disp[:20]}…</span>
                          </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                    col_like, col_pin, col_play = st.columns([1, 1, 1])
                    liked_flag = st.session_state["likes"].get((orig_idx, nm), False)
                    pinned_flag = any(
                        (orig_idx, nm) == ent
                        for ent_list in st.session_state["pinned"].values()
                        for ent in ent_list
                    )
                    with col_like:
                        if st.button("👍", key=f"like_{orig_idx}_{nm}"):
                            st.session_state["likes"][(orig_idx, nm)] = True
                    with col_pin:
                        if st.button("📌", key=f"pin_{orig_idx}_{nm}"):
                            st.session_state["pinned"].setdefault(nm, []).append((orig_idx, ans))
                            save_all_memory(
                                st.session_state["mem"],
                                st.session_state["pinned"],
                                st.session_state["shared_mem"]
                            )
                    with col_play:
                        raw_ans_for_tts = ans.replace("'", "\\'").replace("\n", " ")
                        st.markdown(
                            f"<button onclick=\"playTTS('{raw_ans_for_tts}')\">🔊 Play</button>",
                            unsafe_allow_html=True
                        )
                    st.markdown("")  # spacer

                # Fused reply
                if f_text:
                    fused_disp = highlight(f_text, search_term)
                    st.markdown(
                        f"""
                        <details>
                          <summary style="font-weight:600; cursor:pointer;">Fusion:</summary>
                          <div style="white-space:pre-wrap; margin-top:0.5rem; background-color:#EEE; padding:10px; border-radius:5px;">
                            {fused_disp}
                          </div>
                        </details>
                        """,
                        unsafe_allow_html=True
                    )

                st.markdown("")  # spacer

        else:  # Tabbed view
            tab_labels = ["User"]
            for nm in st.session_state["selected"]:
                label = nm
                if nm == last_persona:
                    label = f"{nm} ⭐"
                tab_labels.append(label)

            tab_objs = st.tabs(tab_labels)
            for idx_tab, label in enumerate(tab_labels):
                with tab_objs[idx_tab]:
                    st.subheader(f"{label} Messages")
                    for idx_round, (u_text, pr_dict, f_text) in enumerate(filtered):
                        orig_idx = st.session_state["history"].index((u_text, pr_dict, f_text))
                        st.markdown(f'<a name="round-{orig_idx}"></a>', unsafe_allow_html=True)
                        st.markdown(
                            f'<div style="font-size:0.9rem; margin-bottom:4px;">'
                            f'<a href="#round-{orig_idx}">➤ Jump to round {orig_idx}</a>'
                            f'</div>',
                            unsafe_allow_html=True
                        )
                        if label.startswith("User"):
                            u_disp = highlight(u_text, search_term)
                            st.markdown(
                                f"<div class='chat-bubble' style='text-align:right; margin:10px 0;'>"
                                f"  <span style='background-color:#DCF8C6; padding:8px 12px; border-radius:10px;'>"
                                f"    <strong>You:</strong> <span class='chat-bubble-text'>{u_disp}</span>"
                                f"    <span class='collapsed'>{PERSONA_ICONS.get('CuriousChild','…')}&nbsp;{u_disp[:20]}…</span>"
                                f"  </span>"
                                f"</div>",
                                unsafe_allow_html=True
                            )
                        else:
                            persona_name = label.replace(" ⭐", "")
                            if persona_name in pr_dict:
                                u_disp = highlight(u_text, search_term)
                                st.markdown(
                                    f"<div class='chat-bubble' style='text-align:right; margin:10px 0;'>"
                                    f"  <span style='background-color:#DCF8C6; padding:8px 12px; border-radius:10px;'>"
                                    f"    <strong>You:</strong> <span class='chat-bubble-text'>{u_disp}</span>"
                                    f"    <span class='collapsed'>{PERSONA_ICONS.get('CuriousChild','…')}&nbsp;{u_disp[:20]}…</span>"
                                    f"  </span>"
                                    f"</div>",
                                    unsafe_allow_html=True
                                )

                                pdata = cached_load_personas()[persona_name]
                                icon = pdata.get("avatar", PERSONA_ICONS.get(persona_name, ""))
                                tagline = pdata.get("tagline", "")
                                if st.session_state["theme"] == "Dark":
                                    bg = PERSONA_COLORS_DARK.get(persona_name, "#333333")
                                    txtc = "#FFFFFF"
                                elif st.session_state["theme"] == "Pastel":
                                    bg = PERSONA_COLORS_PASTEL.get(persona_name, "#FFF")
                                    txtc = "#000000"
                                else:
                                    bg = PERSONA_COLORS_LIGHT.get(persona_name, "#EEEEEE")
                                    txtc = "#000000"

                                last_active = ""
                                for uu, pp, ff in reversed(st.session_state["history"]):
                                    if persona_name in pp:
                                        last_active = pp[persona_name]
                                        break

                                ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                                profile_html = (
                                    f"<span class='profile-card'>"
                                    f"{icon} <strong>{persona_name}</strong>"
                                    f"<div class='card-content'>"
                                    f"<div><strong>Avatar:</strong> {icon}</div>"
                                    f"<div><strong>Tagline:</strong> {tagline}</div>"
                                    f"<div style='margin-top:4px;'><strong>Last said:</strong> “{last_active[:40]}…”</div>"
                                    f"<div style='font-size:0.8em; color:#666; margin-top:4px;'>Active: {ts}</div>"
                                    f"</div>"
                                    f"</span>"
                                )

                                ans_disp = highlight(pr_dict[persona_name], search_term)
                                highlight_border = ""
                                if persona_name == last_persona:
                                    highlight_border = "border: 2px solid #FFA000;"

                                st.markdown(
                                    f"<div class='persona-bubble tooltip' style='text-align:left; margin:5px 0;'>"
                                    f"  <div style='background-color:{bg}; color:{txtc}; padding:8px 12px; "
                                    f"border-radius:10px; {highlight_border} display:inline-block;'>"
                                    f"    {profile_html}<br>"
                                    f"    <span class='persona-bubble-text'>{ans_disp}</span>"
                                    f"    <span class='collapsed'>{icon}&nbsp;{ans_disp[:20]}…</span>"
                                    f"  </div>"
                                    f"</div>",
                                    unsafe_allow_html=True
                                )

                                liked_flag = st.session_state["likes"].get((orig_idx, persona_name), False)
                                pinned_flag = any(
                                    (orig_idx, persona_name) == ent
                                    for ent_list in st.session_state["pinned"].values()
                                    for ent in ent_list
                                )

                                col_like, col_pin, col_play = st.columns([1, 1, 1])
                                with col_like:
                                    if st.button("👍", key=f"like_{orig_idx}_{persona_name}"):
                                        st.session_state["likes"][(orig_idx, persona_name)] = True
                                with col_pin:
                                    if st.button("📌", key=f"pin_{orig_idx}_{persona_name}"):
                                        st.session_state["pinned"].setdefault(persona_name, []).append(
                                            (orig_idx, pr_dict[persona_name]))
                                        save_all_memory(
                                            st.session_state["mem"],
                                            st.session_state["pinned"],
                                            st.session_state["shared_mem"]
                                        )
                                with col_play:
                                    raw_ans_for_tts = pr_dict[persona_name].replace("'", "\\'").replace("\n", " ")
                                    st.markdown(
                                        f"<button onclick=\"playTTS('{raw_ans_for_tts}')\">🔊 Play</button>",
                                        unsafe_allow_html=True
                                    )
                                st.markdown("")  # spacer

        # ───────────────────────────────────────────────────────────────────────
        # Fixed "Newest" button
        # ───────────────────────────────────────────────────────────────────────

        st.markdown(
            """<button id="newest-button" onclick="scrollToBottom()">⬆</button>""",
            unsafe_allow_html=True
        )


# ==============================================================================#
# TAB 2: Manage Personas
# ==============================================================================#
with tab2:
    st.header("👥 Manage Personas (In-App)")
    st.markdown("View, edit, clone, or delete personas without touching the filesystem directly.")

    persons = cached_load_personas()
    persona_names = list(persons.keys())

    if not persona_names:
        st.info("No personas found. Create one below:")
        new_name = st.text_input("New Persona Name", key="new_name")
        if new_name and st.button("Create Persona"):
            template = {
                "name": new_name,
                "role": "New Role",
                "avatar": "🆕",
                "tagline": "A brand-new persona",
                "goals": [],
                "quirks": [],
                "rounds": {
                    "initial": "Enter the initial system prompt here…",
                    "reflexive": "Enter reflexive‐phase instructions here…",
                    "meta": "Enter meta‐phase instructions here…"
                }
            }
            if save_persona_to_disk(template):
                st.success(f"Created persona '{new_name}'. Refresh the page to see it.")
        st.stop()

    st.subheader("Existing Personas")
    cols = st.columns([3, 2, 1, 1, 1])  # name, role, edit, clone, delete
    cols[0].write("**Name**")
    cols[1].write("**Role**")
    cols[2].write("")  # for Edit button
    cols[3].write("")  # for Clone button
    cols[4].write("")  # for Delete button

    for pname in persona_names:
        pdata = persons[pname]
        col_name, col_role, col_edit, col_clone, col_delete = st.columns([3, 2, 1, 1, 1])
        col_name.write(f"**{pdata['name']}**")
        col_role.write(pdata.get("role", ""))

        if col_edit.button("Edit", key=f"edit_{pname}"):
            st.session_state[f"editing_{pname}"] = True

        if col_clone.button("Clone", key=f"clone_{pname}"):
            newname = clone_persona_on_disk(pname)
            if newname:
                st.success(f"Cloned '{pname}' → '{newname}'. Refresh to see it.")
            else:
                st.error("Clone failed.")

        if col_delete.button("Delete", key=f"delete_{pname}"):
            if delete_persona_from_disk(pname):
                st.warning(f"Deleted '{pname}'. Refresh to remove it.")
            else:
                st.error("Delete failed.")

        st.markdown("---")

        if st.session_state.get(f"editing_{pname}", False):
            with st.form(f"form_edit_{pname}", clear_on_submit=False):
                st.subheader(f"✏️ Editing Persona: '{pname}'")

                new_role = st.text_input("Role:", value=pdata.get("role", ""), key=f"role_{pname}")
                new_avatar = st.text_input("Avatar (emoji/text):", value=pdata.get("avatar", ""), key=f"avatar_{pname}")
                new_tagline = st.text_input("Tagline:", value=pdata.get("tagline", ""), key=f"tagline_{pname}")

                new_initial = st.text_area(
                    "Initial Prompt (system message):",
                    value=pdata["rounds"]["initial"],
                    height=150,
                    key=f"initial_{pname}"
                )

                st.markdown("**Live Preview:**")
                test_query = st.text_input("Type a test question:", key=f"test_query_{pname}")
                run_preview = st.form_submit_button("Run Preview", use_container_width=True)

                preview_answer = ""
                if run_preview and test_query.strip():
                    with st.spinner("Generating preview…"):
                        try:
                            resp = client.chat.completions.create(
                                model="gpt-3.5-turbo",
                                messages=[
                                    {"role": "system", "content": new_initial},
                                    {"role": "user",   "content": test_query}
                                ],
                                temperature=0.7
                            )
                            preview_answer = resp.choices[0].message.content.strip()
                        except Exception as e:
                            st.error(f"Preview failed: {e}")
                if preview_answer:
                    st.markdown(f"**Preview Answer →** {preview_answer}")

                new_goals = st.text_area(
                    "Goals (one per line):",
                    value="\n".join(pdata.get("goals", [])),
                    height=80,
                    key=f"goals_{pname}"
                )
                new_quirks = st.text_area(
                    "Quirks (one per line):",
                    value="\n".join(pdata.get("quirks", [])),
                    height=80,
                    key=f"quirks_{pname}"
                )

                save_button = st.form_submit_button("💾 Save Changes")
                if save_button:
                    updated = {
                        "name": pname,
                        "role": new_role.strip(),
                        "avatar": new_avatar.strip(),
                        "tagline": new_tagline.strip(),
                        "goals": [g.strip() for g in new_goals.splitlines() if g.strip()],
                        "quirks": [q.strip() for q in new_quirks.splitlines() if q.strip()],
                        "rounds": {
                            "initial": new_initial.strip(),
                            "reflexive": pdata["rounds"]["reflexive"],
                            "meta": pdata["rounds"]["meta"]
                        }
                    }

                    if save_persona_to_disk(updated):
                        st.success(f"Saved '{pname}'. Refresh to see updates.")
                        st.session_state[f"editing_{pname}"] = False
                    else:
                        st.error("Failed to save. Check logs.")

    st.markdown("## ➕ Create a New Persona")
    name_new = st.text_input("New Persona Name:", key="new_persona_name")
    if st.button("Create Persona") and name_new.strip():
        template = {
            "name": name_new.strip(),
            "role": "New Role",
            "avatar": "🆕",
            "tagline": "A newly created persona",
            "goals": [],
            "quirks": [],
            "rounds": {
                "initial": "Enter your system prompt here…",
                "reflexive": "Enter reflexive‐phase instructions here…",
                "meta": "Enter meta‐phase instructions here…"
            }
        }
        if save_persona_to_disk(template):
            st.success(f"Created persona '{name_new.strip()}'. Refresh to edit it.")
        else:
            st.error("Failed to create new persona.")


# ==============================================================================#
# TAB 3: Settings
# ==============================================================================#
with tab3:
    st.header("⚙️ UX/UI Settings")
    theme = st.selectbox(
        "Choose Theme:",
        ["Light", "Dark", "Pastel"],
        index=["Light", "Dark", "Pastel"].index(st.session_state["theme"])
    )
    if theme != st.session_state["theme"]:
        st.session_state["theme"] = theme
        inject_css_and_js()

    st.markdown("---")
    st.write("**When screen is narrow (<600px), bubbles collapse to avatar + preview.**")
    st.write("Scroll up to reveal the ⏫ button, which jumps to latest message.")
    st.write("Hover over the right-edge timeline to preview rounds; click to jump.")
    st.write("Use 👍 to 'like' a persona reply; it will highlight its dot in the timeline.")
    st.write("Use 📌 to pin a message—pinned items appear at top of sidebar under “Pinned Messages.”")

    st.markdown("---")
    st.header("🎚️ Persona Parameters & Styles")

    for pname, pdata in cached_load_personas().items():
        with st.expander(f"{pdata['name']} Controls"):
            # Parameter sliders
            for param_name, default_val in pdata.get("parameters", {}).items():
                sess_key = f"{pname}_{param_name}"
                if sess_key not in st.session_state:
                    st.session_state[sess_key] = default_val

                st.slider(
                    label=f"{pname} ▶ {param_name}",
                    min_value=0,
                    max_value=10,
                    value=st.session_state[sess_key],
                    key=sess_key
                )

            st.markdown("---")

            # Style dropdown (if any exist)
            styles_dict = pdata.get("styles", {})
            if styles_dict:
                style_key = f"{pname}_style"
                if style_key not in st.session_state:
                    st.session_state[style_key] = list(styles_dict.keys())[0]

                st.selectbox(
                    label=f"{pname} ▶ Style",
                    options=list(styles_dict.keys()),
                    index=list(styles_dict.keys()).index(st.session_state[style_key]),
                    key=style_key
                )


# ==============================================================================#
# TAB 4: Info
# ==============================================================================#
# Inside your Streamlit code where you render the Info tab, for example:
with tab4:  # or whatever your Info tab is called
    # Optionally show the Outlier logo again or a small badge:
    # (Make sure the logo_path or base64 is available here if you want to inline an image)
    st.markdown(
        """
        <div style="display:flex; align-items:center; margin-bottom:16px;">
          <!-- If you want to show a small inline logo, you can embed it via base64 as above.
               For simplicity, here we just show text; you can replace with an <img> tag. -->
          <span style="font-weight:bold; font-size:0.9rem; color:#666;">Powered by Outlier AI</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("## 🤖 Persona Fabric Chat - Info & Roadmap", unsafe_allow_html=True)

    st.markdown(
        """
        ### What We’ve Built So Far
        - **Multi‐Persona “Fabric Chat” UI**  
          Select any combination of personas; ask a question; see each persona’s response in turn.
        - **Granular Memory Controls**  
          • Forget by age or by number  
          • Pin/unpin specific memory entries  
          • Automatic pinning/pruning rules per persona
        - **Selective Fusion**  
          After all personas reply, choose which replies to include in the final fused answer.
        - **Adaptive Persona Parameters & Styles**  
          Sliders (0–10) for “creativity,” “tone,” etc., plus a dropdown to switch persona style variants.
        - **Speech‐to‐Text (STT)**  
          Click “🎤 Speak” to talk instead of typing; auto‐submit on end‐of‐speech.
        - **Text‐to‐Speech (TTS)**  
          Click “🔊 Play” next to any persona bubble to read it aloud.
        - **Multi‐Room Support**  
          On startup, choose a “Room ID” so different teams/channels maintain separate chat histories.
        - **Response‐Time Dashboard**  
          In Analytics tab, view average per‐persona latency and bar charts to spot slow/faster personas.
        - **Persona Management**  
          Create, clone, delete persona JSONs; import/export packages for sharing personas.
        - **Settings & Customization**  
          - Toggle view modes (single-feed vs. tabbed)  
          - Sidebar controls for active personas, memory settings, API key override, etc.
        - **Logging & Audit**  
          All conversation rounds logged (with timestamps) to file for debugging or audit.
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### What’s Next / Roadmap", unsafe_allow_html=True)
    st.markdown(
        """
        1. **True Tool Plugins**  
           Allow personas to invoke real tools (weather, calculator, search, custom Python functions).  
           - Parse signals like `[tool_name: "args"]` in persona-generated text.  
           - Run the corresponding Python function, inject the result back into the chat flow.  
           - Secure sandboxing / permission checks for certain tools.

        2. **Localization & Translation**  
           - Add a language dropdown (English, Spanish, French, etc.).  
           - Auto-translate user input into English, run personas in English, then translate responses back to the chosen language.  
           - Caching translations for speed; allow override if translation errors occur.

        3. **Fine‐Tuning Module**  
           - Let power users upload small local models (e.g., tiny LLaMA, GPT-2) for offline inference & fine-tuning on persona-specific examples.  
           - Provide a simple UI: “Upload dataset → train → test in local environment.”  
           - Manage resources (GPU/CPU) and fallback to OpenAI API if local models not available.

        4. **Persona Marketplace / Sharing**  
           - “Export Persona” button: package persona JSON, style GUIDELINES, few-shot examples, avatar, etc., into a ZIP.  
           - “Import Persona” button: ingest a ZIP/JSON to local `/personas/`.  
           - (Long-term) Connect to a community repository where users can browse and download public personas.

        5. **UI Polishing & Responsive Layout**  
           - Improve mobile vs. desktop breakpoints.  
           - Add subtle animations/transitions (e.g., via Framer Motion or CSS).  
           - Dark mode toggle (persist user preference).  
           - Better theming: custom fonts, spacing, clearer headers/footers.

        6. **CI/CD & Automated Tests**  
           - Write smoke tests (e.g., load 5 sample JSON personas, send a “hello” prompt, verify non-empty replies).  
           - Integrate with GitHub Actions: run tests on every push/PR; linting; security checks.

        7. **Deployment & Dockerization**  
           - Dockerfile with ENTRYPOINT checking for `OPENAI_API_KEY` environment variable.  
           - Publish a container image for easy self-hosting or team deployments.  
           - Optionally set up a simple Kubernetes/Helm chart for scalable deployments.

        8. **Analytics & Usage Metrics**  
           - Extend Analytics: track per‐person usage counts, memory growth over time, popular prompts by persona.  
           - Option to anonymize and optionally share anonymized metrics to a central dashboard for yourself or team insights.

        9. **Access Control & Collaboration Features**  
           - User login / API key per user (so you don't expose your key publicly).  
           - Shared rooms with permissions: read/write roles, “view-only” auditors.  
           - Webhook/event triggers for external integrations (e.g., send persona replies to Slack, email digests).

        10. **Advanced Persona Capabilities**  
           - Persona “chaining”: let one persona’s output feed into another automatically in multi-step flows.  
           - Dynamic persona creation: an AI assistant that helps you draft new persona JSONs from natural-language specs.  
           - Persona versioning: track changes to persona JSONs over time; revert or compare diffs.

        > This is an evolving prototype by **Doruk Dumlu**.  
        > If you have ideas or run into issues, please open an issue or submit a PR on our GitHub repo (link forthcoming). 🚀
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        ---
        <div style="font-size:0.8rem; color:#888;">
          © 2025 Persona Fabric Chat. Powered by Outlier AI.
        </div>
        """,
        unsafe_allow_html=True,
    )


# ==============================================================================#
# TAB 5: Analytics
# ==============================================================================#
with tab5:
    st.header("📊 Response Time Dashboard")

    import pandas as pd
    import matplotlib.pyplot as plt

    data = []
    for persona, times in st.session_state.get("latencies", {}).items():
        avg_time = sum(times) / len(times) if times else 0.0
        data.append({"Persona": persona, "Avg Latency (s)": avg_time})

    df = pd.DataFrame(data)

    if df.empty:
        st.info("No latency data available yet. Chat with some personas first.")
    else:
        st.subheader("Avg Latencies by Persona")
        st.dataframe(df)

        plt.figure(figsize=(8, 4))
        plt.bar(df["Persona"], df["Avg Latency (s)"])
        plt.xlabel("Persona")
        plt.ylabel("Avg Latency (seconds)")
        plt.title("Response Time per Persona")
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()

        st.pyplot(plt.gcf())