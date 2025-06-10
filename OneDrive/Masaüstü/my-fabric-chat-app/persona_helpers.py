import os
import json
import datetime

# ---------------------------------------------------------------------------
# Configuration: adjust these paths as needed (or override in your local code)
# ---------------------------------------------------------------------------
PERSONA_DIR = "personas"
BACKUP_DIR = "persona_backups"


def load_personas() -> dict[str, dict]:
    """
    Scan PERSONA_DIR for *.json files and return a dict mapping
    persona_name -> raw persona_data (as loaded from JSON).
    """
    if not os.path.isdir(PERSONA_DIR):
        os.makedirs(PERSONA_DIR, exist_ok=True)

    out: dict[str, dict] = {}
    for fname in os.listdir(PERSONA_DIR):
        if not fname.lower().endswith(".json"):
            continue
        path = os.path.join(PERSONA_DIR, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("name"):
                out[data["name"]] = data
        except Exception:
            # Ignore files that fail to parse
            pass
    return out


def save_persona_to_disk(persona_data: dict) -> bool:
    """
    Write persona_data (a dict with at least "name") to PERSONA_DIR/<name>.json.
    Before overwriting, back up the existing file (if it exists) into BACKUP_DIR.
    """
    try:
        name = persona_data["name"]
        # Ensure directories exist
        os.makedirs(PERSONA_DIR, exist_ok=True)
        os.makedirs(BACKUP_DIR, exist_ok=True)

        target_path = os.path.join(PERSONA_DIR, f"{name}.json")

        # If there's an existing file, back it up first
        if os.path.exists(target_path):
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_fname = f"{name}_{ts}.json"
            backup_path = os.path.join(BACKUP_DIR, backup_fname)
            with open(target_path, "r", encoding="utf-8") as orig_f, \
                 open(backup_path, "w", encoding="utf-8") as backup_f:
                backup_f.write(orig_f.read())

        # Now write the new JSON
        with open(target_path, "w", encoding="utf-8") as out_f:
            json.dump(persona_data, out_f, ensure_ascii=False, indent=2)

        return True
    except Exception as e:
        print(f"[personas.py] Failed to save persona '{persona_data.get('name','?')}': {e}")
        return False


def delete_persona_from_disk(persona_name: str) -> bool:
    """
    Delete the JSON file for the given persona_name from PERSONA_DIR.
    """
    try:
        path = os.path.join(PERSONA_DIR, f"{persona_name}.json")
        if os.path.exists(path):
            os.remove(path)
            return True
        return False
    except Exception as e:
        print(f"[personas.py] Failed to delete persona '{persona_name}': {e}")
        return False


def clone_persona_on_disk(persona_name: str) -> str | None:
    """
    Make a copy of an existing persona JSON under a new name <original_name>_copy,
    or <original_name>_copy1, etc., if needed. Returns the new persona_name or None.
    """
    raw = load_personas()
    original = raw.get(persona_name)
    if not original:
        return None

    base = f"{persona_name}_copy"
    newname = base
    i = 1
    while os.path.exists(os.path.join(PERSONA_DIR, f"{newname}.json")):
        newname = f"{base}{i}"
        i += 1

    new_data = dict(original)
    new_data["name"] = newname
    if save_persona_to_disk(new_data):
        return newname
    return None


def instantiate_persona_objects() -> dict[str, "Persona"]:
    """
    Read all JSON files in PERSONA_DIR, create a Persona instance for each,
    and return a dict mapping persona_name -> Persona instance.
    """
    raw = load_personas()
    persona_objs: dict[str, Persona] = {}
    for name, data in raw.items():
        persona_objs[name] = Persona(data)
    return persona_objs


class Persona:
    """
    Represents a single persona. Holds:
    - Raw persona data (name, prompt, examples, styles, parameters, memory_config, etc.)
    - Mutable state: memory (list of dicts), pinned (list of dicts), latencies (list of floats)
    """

    def __init__(self, data: dict):
        # Core persona metadata from JSON
        self.name: str = data.get("name", "")
        self.role: str = data.get("role", "")
        self.avatar: str = data.get("avatar", "")
        self.tagline: str = data.get("tagline", "")
        self.prompt: str = data.get("prompt", "")
        self.examples: list[dict] = data.get("examples", [])
        self.styles: dict[str, dict] = data.get("styles", {})
        self.parameters: dict[str, float] = data.get("parameters", {})
        self.memory_config: dict = data.get("memory_config", {})

        # Runtime state
        self.memory: list[dict] = []   # Each entry: {"role": "...", "content": "...", "ts": "..."}
        self.pinned: list[dict] = []   # Each entry: {"role": "...", "content": "...", "ts": "...", "round_idx": ...}
        self.latencies: list[float] = []  # List of API call durations in seconds

    def build_messages(
        self,
        shared_mem: list[dict],
        user_text: str,
        st_state: dict
    ) -> list[dict]:
        """
        Construct the chat-completion message list for this persona.
        - shared_mem: list of {"role": "assistant", "content": "...", "ts": "..."}
        - user_text: the new user message string
        - st_state: Streamlit session_state dict (to read selected style/param values)
        """
        messages: list[dict] = []

        # 0) Shared-Context System Message (if any shared entries exist)
        if shared_mem:
            combined = "\n\n".join(entry["content"] for entry in shared_mem)
            messages.append({
                "role": "system",
                "content": "Shared context (what all personas have said so far):\n\n" + combined
            })

        # 1) Few-shot examples
        for ex in self.examples:
            user_ex = ex.get("user", "")
            assistant_ex = ex.get("assistant", "")
            messages.append({"role": "user", "content": user_ex})
            messages.append({"role": "assistant", "content": assistant_ex})

        # 2) Persona’s dynamic system prompt (with optional style/parameter tags)
        base_prompt = self.prompt

        # 2a) If a style is selected in st_state, prepend its instruction
        style_key = f"{self.name}_style"
        if style_key in st_state:
            chosen_style = st_state[style_key]
            style_instr = self.styles.get(chosen_style, {}).get("instruction", "")
            if style_instr:
                base_prompt = style_instr + "\n\n" + base_prompt

        # 2b) Append parameter tags, e.g. "[creativity=8, …]"
        param_labels = []
        for param_name, default_val in self.parameters.items():
            sess_key = f"{self.name}_{param_name}"
            val = st_state.get(sess_key, default_val)
            param_labels.append(f"{param_name}={val}")
        if param_labels:
            base_prompt += "\n\n[" + ", ".join(param_labels) + "]"

        # 2c) Emit one system message with the persona prompt
        messages.append({"role": "system", "content": base_prompt})

        # 3) Pinned entries
        for entry in self.pinned:
            # Each pinned entry is a dict with at least "role" and "content"
            # We'll drop "round_idx" since LLM doesn't need it
            pinned_msg = {"role": entry.get("role", "assistant"), "content": entry.get("content", "")}
            messages.append(pinned_msg)

        # 4) Persona’s own memory entries
        for entry in self.memory:
            messages.append(entry.copy())

        # 5) New user turn
        messages.append({"role": "user", "content": user_text})

        return messages

    def generate_reply(
        self,
        shared_mem: list[dict],
        user_text: str,
        client: "OpenAI"
    ) -> tuple[str, float]:
        """
        Build messages, call the OpenAI chat completion, measure latency,
        and return (reply_text, latency_seconds).
        """
        msgs = self.build_messages(shared_mem=shared_mem, user_text=user_text, st_state={})
        start = datetime.datetime.now()
        try:
            resp = client.chat.completions.create(
                model="gpt-3.5-turbo-16k",
                messages=msgs,
                temperature=0.7
            )
            reply = resp.choices[0].message.content.strip()
        except Exception as e:
            reply = f"[Error: {e}]"
        end = datetime.datetime.now()
        latency = (end - start).total_seconds()
        return reply, latency

    def record_turn(self, user_text: str, reply: str) -> None:
        """
        After generating a reply, record the user message and assistant reply
        into this persona's memory, with timestamps, and enforce memory rules.
        """
        now_iso = datetime.datetime.now().isoformat()

        # Append user turn
        self.memory.append({
            "role": "user",
            "content": user_text,
            "ts": now_iso
        })
        self.enforce_memory_config()

        # Append assistant turn
        self.memory.append({
            "role": "assistant",
            "content": reply,
            "ts": now_iso
        })
        self.enforce_memory_config()

    def enforce_memory_config(self) -> None:
        """
        Prune/prune according to this persona's memory_config:
        - "retain_days": drop entries older than N days
        - "max_entries": keep only the last N entries
        - "pin_keywords": automatically pin any memory entry containing any keyword
        """
        cfg = self.memory_config or {}
        if not cfg:
            return

        now = datetime.datetime.now()

        # 1) Prune old entries if retain_days is specified
        retain_days = cfg.get("retain_days")
        if retain_days is not None:
            cutoff = now - datetime.timedelta(days=retain_days)
            new_mem = []
            for entry in self.memory:
                ts = entry.get("ts", "")
                try:
                    entry_time = datetime.datetime.fromisoformat(ts)
                    if entry_time >= cutoff:
                        new_mem.append(entry)
                except Exception:
                    # If timestamp parse fails, keep the entry
                    new_mem.append(entry)
            self.memory = new_mem

        # 2) Enforce max_entries if specified
        max_entries = cfg.get("max_entries")
        if max_entries is not None and len(self.memory) > max_entries:
            # Keep only the last max_entries items
            self.memory = self.memory[-max_entries :]

        # 3) Auto-pin any entries containing pin_keywords
        pin_keywords = cfg.get("pin_keywords", [])
        for entry in self.memory:
            content_lower = entry.get("content", "").lower()
            for kw in pin_keywords:
                if kw.lower() in content_lower:
                    # Check if already pinned
                    already = any(
                        pinned_entry.get("content") == entry.get("content")
                        for pinned_entry in self.pinned
                    )
                    if not already:
                        self.pinned.append({
                            "role": entry.get("role", "assistant"),
                            "content": entry.get("content", ""),
                            "ts": entry.get("ts", ""),
                            "round_idx": None
                        })
                    break  # no need to check other keywords for this entry


# Example usage:
#   raw = load_personas()
#   persona_objs = instantiate_persona_objects()
#   shared = []  # loaded by app via memory.py
#   client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
#
#   # To generate a reply:
#   p = persona_objs["Philosopher"]
#   reply, latency = p.generate_reply(shared, "Hello there", client)
#   p.latencies.append(latency)
#   p.record_turn("Hello there", reply)
#
#   # After modifying memory/pinned/shared, the app calls save_all_memory(...)
