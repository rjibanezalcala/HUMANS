import re
import os
from docx import Document  

def extract_text_from_docx(filepath):

    doc = Document(filepath)
    lines = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return "\n".join(lines)

def clean_text(text):

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)

def reformat_list_numbers(text):

    text = text.replace("\u00A0", " ").replace("\t", " ")
    text = clean_text(text)

    lines = []
    counter = 0
    for line in text.splitlines():
        counter += 1
        lines.append(f"{counter}) {line.strip()}")
    return "\n".join(lines)

def reformat_questions(text):

    text = clean_text(text)
    return re.sub(
        r'(?m)^R(\d+)C(\d+):\s*(.*)',
        lambda m: f"{m.group(3).strip()} (R{m.group(1)},C{m.group(2)})",
        text
    )

def parse_stories(input_file, output_dir):

    if input_file.lower().endswith(".docx"):
        print("Extracting text...")
        text = extract_text_from_docx(input_file)
    else:
        print("Reading plain text file...")
        with open(input_file, "r", encoding="utf-8") as f:
            text = f.read()

    text = text.strip()

    # Pattern to capture Story, Context, Costs, Rewards, Questions
    story_pattern = re.compile(
        r"Story No\.\s*(\d+)\s*"
        r"Context:\s*(.*?)\s*"
        r"Costs\s*(.*?)\s*"
        r"Rewards\s*(.*?)\s*"
        r"QUESTIONS:\s*(.*?)(?=Story No\.|\Z)",
        re.DOTALL | re.IGNORECASE
    )

    matches = story_pattern.findall(text)
    if not matches:
        print("No stories found. Please check your formatting.")
        return

    for story_num, context, costs, rewards, questions in matches:
        story_folder = os.path.join(output_dir, f"story_{story_num}")
        os.makedirs(story_folder, exist_ok=True)

        # Clean and reformat
        context_clean = clean_text(context)
        costs_clean = reformat_list_numbers(costs)
        rewards_clean = reformat_list_numbers(rewards)
        questions_clean = reformat_questions(questions)

        # Save each section
        sections = {
            "context.txt": context_clean,
            "pref_cost.txt": costs_clean,
            "pref_reward.txt": rewards_clean,
            "questions.txt": questions_clean,
        }

        for filename, content in sections.items():
            filepath = os.path.join(story_folder, filename)
            with open(filepath, "w", encoding="utf-8") as f_out:
                f_out.write(content + "\n")
            print(f"Saved: {filepath}")

    print("\n All stories parsed and saved successfully!")

if __name__ == "__main__":
    input_file = "Definitive version.docx"     
    output_dir = "ki_approach_avoid"    
    os.makedirs(output_dir, exist_ok=True)
    parse_stories(input_file, output_dir)
