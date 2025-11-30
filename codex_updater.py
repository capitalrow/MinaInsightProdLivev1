import os
import shutil
from datetime import datetime
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def codex_update(file_path: str, instruction: str, model="gpt-4o-mini"):
    """
    Uses Codex-style model to read a file, apply an update, and overwrite it.
    """

    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return

    # Read current file
    with open(file_path, "r") as f:
        original_code = f.read()

    # Backup before changing
    backup_path = f"{file_path}.bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copyfile(file_path, backup_path)
    print(f"🗂️ Backup created at {backup_path}")

    # Build Codex prompt
    full_prompt = (
        f"You are an expert full-stack engineer working on the Mina app "
        f"(Flask + React + Tailwind + Whisper integration). "
        f"Apply the following change to the file below while preserving imports, style, and functionality.\n\n"
        f"### Instruction:\n{instruction}\n\n"
        f"### Original file:\n{original_code}\n\n"
        f"### Updated file:"
    )

    response = client.responses.create(
        model=model,
        input=full_prompt,
        temperature=0.2,
        max_output_tokens=4000
    )

    new_code = response.output_text.strip()

    # Write updated code
    with open(file_path, "w") as f:
        f.write(new_code)

    print(f"✅ File '{file_path}' successfully updated via Codex.")
    return new_code


if __name__ == "__main__":
    print("=== Mina Codex File Updater ===")
    while True:
        target = input("\nEnter file path to update (or 'exit'): ").strip()
        if target.lower() == "exit":
            break
        instruction = input("Describe the change you want:\n> ")
        codex_update(target, instruction)
