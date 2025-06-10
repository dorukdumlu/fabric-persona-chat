import os
import json
import datetime
from openai import OpenAI

# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------
PERSONA_DIR = r"C:\Users\doruk\PycharmProjects\AIs"  # Assumes chat.py and JSON files are in the same folder
LOG_FILE = "chat_log.txt"

# ------------------------------------------------------------
# 1) Load all persona JSON files into a dictionary
# ------------------------------------------------------------
personas = {}
for fname in os.listdir(PERSONA_DIR):
    if fname.endswith(".json"):
        with open(os.path.join(PERSONA_DIR, fname), encoding="utf-8") as f:
            data = json.load(f)
            personas[data["name"]] = data

# ------------------------------------------------------------
# 2) Initialize OpenAI client (ensure OPENAI_API_KEY is set)
# ------------------------------------------------------------
client = OpenAI(api_key=os.getenv(""))

# ------------------------------------------------------------
# 3) In-memory memory per persona
# ------------------------------------------------------------
memory = {name: [] for name in personas.keys()}


# ------------------------------------------------------------
# 4) Function to chat with one persona, updating its memory
# ------------------------------------------------------------
def chat_with_persona(persona, user_input):
    """
    Builds the message list: system prompt + that persona's memory + current user_input.
    Calls the OpenAI API, appends the new pair (user→assistant) to memory, and returns the assistant's reply.
    """
    # Start with the system prompt (persona["prompt"])
    messages = [{"role": "system", "content": persona["prompt"]}]

    # Append this persona's previous memory entries (alternating user/assistant)
    for entry in memory[persona["name"]]:
        messages.append(entry)

    # Append the current user input
    messages.append({"role": "user", "content": user_input})

    # Call the API
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages,
        temperature=0.7
    )
    reply = response.choices[0].message.content.strip()

    # Update memory: add the current exchange
    memory[persona["name"]].append({"role": "user", "content": user_input})
    memory[persona["name"]].append({"role": "assistant", "content": reply})

    return reply


# ------------------------------------------------------------
# 5) Function to log each round of conversation to a file
# ------------------------------------------------------------
def log_conversation(user_input, persona_replies, fused_reply=None):
    """
    Appends to LOG_FILE:
      - A timestamped line for the user input
      - Timestamped lines for each persona's reply
      - Optionally a timestamped 'Fusion' line containing the concatenated replies
    """
    timestamp = datetime.datetime.now().isoformat()
    with open(LOG_FILE, "a", encoding="utf-8") as logf:
        logf.write(f"[{timestamp}] You: {user_input}\n")
        for name, reply in persona_replies.items():
            logf.write(f"[{timestamp}] [{name}]: {reply}\n")
        if fused_reply:
            logf.write(f"[{timestamp}] [Fusion]: {fused_reply}\n")
        logf.write("\n")


# ------------------------------------------------------------
# 6) Main chat loop (terminal-based)
# ------------------------------------------------------------
def main():
    # Show which personas are available
    print("Available personas:", ", ".join(personas.keys()))
    sel = input("Enter persona names (comma-separated): ").split(",")
    sel = [s.strip() for s in sel if s.strip() in personas]
    if not sel:
        print("No valid personas selected. Exiting.")
        return

    print(f"\nChatting as: {', '.join(sel)}. Type 'exit' or 'quit' to stop.\n")
    while True:
        user_input = input("You: ")
        if user_input.lower() in ("exit", "quit"):
            break

        # 1) Turn-based debate: each persona responds in sequence, chaining prompts
        persona_replies = {}
        current_input = user_input
        for name in sel:
            persona = personas[name]
            reply = chat_with_persona(persona, current_input)
            persona_replies[name] = reply
            # The next persona uses this persona's reply as its "user_input"
            current_input = reply

        # 2) Fusion: simply concatenate all persona replies into one multi-line string
        fused_lines = [f"[{name}]: {reply}" for name, reply in persona_replies.items()]
        fused_reply = "\n".join(fused_lines)

        # 3) Display each persona's reply
        for name, reply in persona_replies.items():
            print(f"\n[{name}]: {reply}")

        # 4) Display the combined fusion block
        print(f"\n[Fusion]:\n{fused_reply}\n")

        # 5) Log this entire round to chat_log.txt
        log_conversation(user_input, persona_replies, fused_reply)


if __name__ == "__main__":
    main()
