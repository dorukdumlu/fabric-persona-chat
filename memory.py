# memory.py

import json
import os
import datetime

# ---------------------------------------------------------------------
# load_all_memory(persona_names)
#
# Signature matches what app.py expects:
#    m, p, shared = load_all_memory(persona_names)
#
# We do NOT read or write a JSON file here—this is purely in‐memory
# so that app.py will never crash on missing/extra arguments.
# ---------------------------------------------------------------------
def load_all_memory(persona_names):
    """
    Called by app.py as:
        person_list = list(persons.keys())
        m, p, shared = load_all_memory(person_list)
    We simply return empty dictionaries keyed by persona_names, and an
    empty shared list.  No file I/O is performed.
    """
    # Initialize an empty “raw” memory list for each persona
    mem = {p: [] for p in persona_names}

    # Initialize an empty “pinned” list for each persona
    pinned = {p: [] for p in persona_names}

    # Shared memory (common to all personas) is just an empty list
    shared = []

    return mem, pinned, shared


# ---------------------------------------------------------------------
# save_all_memory(mem_dict, pinned_dict, shared_list)
#
# Called by app.py after every new reply.  In this stub, it does nothing.
# ---------------------------------------------------------------------
def save_all_memory(mem_dict, pinned_dict, shared_list):
    """
    No‐op.  app.py calls this to persist memory; we ignore it here
    so that no file I/O is attempted.
    """
    return


# ---------------------------------------------------------------------
# enforce_memory_config(persona_name, mem_dict, pinned_dict)
#
# Truncates older memory entries to keep at most 50 “raw” entries per persona.
# This prevents unbounded growth of the in‐memory lists.
# ---------------------------------------------------------------------
def enforce_memory_config(persona_name, mem_dict, pinned_dict):
    """
    Called by app.py like:
        enforce_memory_config(persona_name, st.session_state['mem'], st.session_state['pinned'])
    We simply cap each persona’s mem list at 50 entries (keeping the most recent 50).
    """
    if persona_name not in mem_dict:
        return

    entries = mem_dict[persona_name]
    MAX_ENTRIES = 50

    if len(entries) > MAX_ENTRIES:
        # Keep only the most recent MAX_ENTRIES
        mem_dict[persona_name] = entries[-MAX_ENTRIES:]


# ---------------------------------------------------------------------
# add_memory_entry(persona_name, text, mem_dict, pinned_dict)
#
# app.py calls this immediately after it appends (user_text/assistant_text)
# to st.session_state['mem'][persona_name]. Here we do nothing, because
# we are _not_ indexing into any external vector store.  It simply satisfies
# the signature that app.py expects.
# ---------------------------------------------------------------------
def add_memory_entry(persona_name, text, mem_dict, pinned_dict):
    """
    Signature matches what app.py expects:
        add_memory_entry(persona_name, reply, st.session_state['mem'], st.session_state['pinned'])
    We do nothing here.  (All “raw” memory was already appended by app.py itself.)
    """
    return


# ---------------------------------------------------------------------
# get_relevant_memory(persona_name, user_text, k)
#
# app.py uses this to fetch “k” semantically relevant older memory entries.
# In this stub, we return an empty list so that no “recovered” entries are injected.
# ---------------------------------------------------------------------
def get_relevant_memory(persona_name, user_text, k=3):
    """
    Always return an empty list.  app.py will append nothing additional to messages.
    """
    return []


# ---------------------------------------------------------------------
# (Optional) If you need to read/write from disk later, you could expand
# these stubs to do JSON file I/O.  For now, everything is in RAM only.
# ---------------------------------------------------------------------
