import glob
import json
import re
import os

# 1) Adjust this path to wherever your persona JSONs live:
PERSONA_DIR = os.path.join(os.path.dirname(__file__), "personas")

def remove_trailing_commas_and_comments(text: str) -> str:
    """
    Remove trailing commas before } or ] and strip out // comments.
    """
    # A) Strip out any //… single‐line comments
    #    (this will remove everything from "//" to end of that line)
    no_comments = re.sub(r"//.*$", "", text, flags=re.MULTILINE)

    # B) Remove trailing commas before a closing } or ]
    #    e.g. change `  "foo": "bar",\n}`  →  `  "foo": "bar"\n}`
    no_trailing_obj = re.sub(r",\s*}", "}", no_comments)
    #    similarly remove `…, ]` → ` ... ]`
    no_trailing_arr = re.sub(r",\s*]", "]", no_trailing_obj)

    return no_trailing_arr

def attempt_fix_and_load(filepath: str) -> bool:
    """
    Try to load the JSON after cleaning. If it succeeds, overwrite file.
    If it fails, leave it alone and return False.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        raw = f.read()

    cleaned = remove_trailing_commas_and_comments(raw)

    try:
        _ = json.loads(cleaned)  # if this succeeds, JSON is now valid
    except Exception as e:
        print(f"❌ Failed to parse even after cleanup: {os.path.basename(filepath)} → {e}")
        return False

    # If we reach here, `cleaned` is valid JSON. Overwrite the file:
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(cleaned)
    print(f"✅ Fixed {os.path.basename(filepath)}")
    return True

if __name__ == "__main__":
    print(f"Looking for JSONs in: {PERSONA_DIR}\n")
    pattern = os.path.join(PERSONA_DIR, "*.json")
    all_files = glob.glob(pattern)
    if not all_files:
        print("⚠️  No .json files found. Check your PERSONA_DIR path.")
    else:
        for path in all_files:
            attempt_fix_and_load(path)
    print("\nDONE. Now re‐run your Streamlit app to see if `load_personas()` works.")
