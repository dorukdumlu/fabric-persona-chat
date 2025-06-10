import os
import json
import openai
import numpy as np
import matplotlib.pyplot as plt

# Function to load persona JSONs
def load_persona_jsons(directory):
    personas = {}
    for fname in os.listdir(directory):
        if fname.endswith(".json"):
            path = os.path.join(directory, fname)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    name = data.get('name') or os.path.splitext(fname)[0]
                    personas[name] = data
            except Exception as e:
                print(f"Failed to load {path}: {e}")
    return personas

# Function to get initial replies for a given persona on a prompt
def get_initial_reply(persona_name, persona_json, user_prompt):
    system_prompt = persona_json.get('rounds', {}).get('initial', "")
    # If style_guidelines or other placeholders need interpolation, handle here.
    # For now we pass system_prompt directly.
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    resp = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages,
        temperature=0.7
    )
    # Access content
    try:
        content = resp.choices[0].message.content.strip()
    except Exception:
        # fallback if structure differs
        content = str(resp)
    return content

# Function to get embedding for a text
def get_embedding(text, model="text-embedding-ada-002"):
    resp = openai.embeddings.create(input=[text], model=model)
    try:
        emb = resp.data[0].embedding
    except Exception:
        # fallback if structure differs
        emb = resp['data'][0]['embedding']
    return np.array(emb)

# Generate divergence heatmap
def divergence_heatmap(persona_json_dir, test_prompts, api_key_env="OPENAI_API_KEY", threshold=0.4):
    # Ensure API key is set
    openai.api_key = os.getenv(api_key_env)
    if not openai.api_key:
        raise ValueError(f"{api_key_env} not set in environment")
    # Load personas
    personas = load_persona_jsons(persona_json_dir)
    if not personas:
        raise ValueError(f"No persona JSONs found in {persona_json_dir}")
    persona_names = list(personas.keys())
    print(f"Loaded {len(persona_names)} personas: {persona_names}")
    # Collect embeddings per persona per prompt
    embeddings = {p: [] for p in persona_names}

    for idx, prompt in enumerate(test_prompts, 1):
        print(f"Prompt {idx}/{len(test_prompts)}: '{prompt}'")
        for p in persona_names:
            try:
                reply = get_initial_reply(p, personas[p], prompt)
                emb = get_embedding(reply)
                embeddings[p].append(emb)
            except Exception as e:
                print(f"Error for persona '{p}' on prompt '{prompt}': {e}")

    # Average embedding per persona across prompts
    avg_embeddings = {}
    for p in persona_names:
        vecs = embeddings.get(p, [])
        if not vecs:
            raise ValueError(f"No embeddings collected for persona '{p}'. Check errors above.")
        arr = np.vstack(vecs)
        avg_embeddings[p] = arr.mean(axis=0)

    # Compute pairwise cosine similarity
    n = len(persona_names)
    sim_matrix = np.zeros((n, n))
    for i, p1 in enumerate(persona_names):
        for j, p2 in enumerate(persona_names):
            v1 = avg_embeddings[p1]
            v2 = avg_embeddings[p2]
            cos = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-10)
            sim_matrix[i, j] = cos

    # Plot heatmap
    fig, ax = plt.subplots(figsize=(8, 6))
    cax = ax.imshow(sim_matrix, vmin=0, vmax=1, cmap='viridis')
    ax.set_xticks(range(n)); ax.set_yticks(range(n))
    ax.set_xticklabels(persona_names, rotation=90, fontsize=8)
    ax.set_yticklabels(persona_names, fontsize=8)
    fig.colorbar(cax, ax=ax, label="Cosine Similarity")
    plt.tight_layout()
    outpath = os.path.join(persona_json_dir, "divergence_heatmap.png")
    try:
        fig.savefig(outpath)
        print(f"Heatmap saved to: {outpath}")
    except Exception as e:
        print(f"Failed to save heatmap: {e}")

    # Print any pairs above threshold (excluding self)
    exceed = []
    for i in range(n):
        for j in range(i+1, n):
            if sim_matrix[i, j] > threshold:
                exceed.append((persona_names[i], persona_names[j], sim_matrix[i, j]))
    if exceed:
        print("Pairs exceeding similarity threshold:")
        for a, b, val in exceed:
            print(f"  {a} <> {b}: {val:.3f}")
    else:
        print(f"No persona pairs exceed similarity threshold {threshold}.")

    return fig, persona_names, sim_matrix

if __name__ == "__main__":
    # Directory containing persona JSON files
    persona_dir = r"C:\Users\doruk\PyCharmProjects\AIs\personas"
    # Define a list of ~20 test prompts
    test_prompts = [
        "I'm feeling anxious about a work presentation tomorrow. What should I do?",
        "I want to innovate in my field but I'm afraid of failing.",
        "How can I improve my relationships when I feel disconnected?",
        "Suggest a creative writing exercise.",
        "What are potential hidden motives behind someone being overly kind?",
        "How should I handle a moral dilemma about telling a friend a hard truth?",
        "What are some practical tips to manage time effectively?",
        "Describe a speculative future scenario for renewable energy.",
        "Offer grounded techniques to cope with stress.",
        "Provide a skeptical take on trusting new technology.",
        "Imagine a surreal scene about personal transformation.",
        "How can I ensure I'm not being manipulated in negotiations?",
        "What small step can I take for self-care today?",
        "How might different perspectives tackle global challenges?",
        "What philosophical question should I ponder about existence?",
        "Give me a minimalist plan for daily productivity.",
        "What ethical trade-offs exist in pursuing career success?",
        "How can I validate someone’s feelings effectively?",
        "Offer a futuristic innovation idea for mental health.",
        "What sensory metaphor can describe resilience?"
    ]
    try:
        divergence_heatmap(persona_dir, test_prompts)
    except Exception as e:
        print(f"Error running divergence_heatmap: {e}")
