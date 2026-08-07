import argparse
import os
import re
import sys

try:
    import openai
except ImportError:
    openai = None

TEMPLATE = """# Question {num}

{question}

## Summary

## Key Concepts

## Example

## Trade-offs

## References
"""

PROMPT_TEMPLATE = """
You are an expert database architect and teacher. Given the question below, generate an easy-to-understand study note in Markdown.

Use simple language and break the answer into the following sections:
- Summary
- Problem
- Solution
- Key Concepts
- Example
- Trade-offs
- References

Explain the idea clearly, keep sentences short, and avoid unnecessary jargon. The goal is a study note that an experienced engineer can read and learn from quickly.

Question:
{question}
"""


def load_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_file(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


from collections import OrderedDict


def extract_question(text):
    lines = text.strip().splitlines()
    title = None
    question = None

    for line in lines:
        if line.startswith("# Question"):
            title = line.strip()
        elif title and line.strip():
            question = line.strip()
            break

    return title, question


def extract_sections(text):
    lines = text.splitlines()
    sections = OrderedDict()
    current = None

    for line in lines:
        if line.startswith("## "):
            current = line.strip()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)

    return sections


def section_has_content(lines):
    return any(bool(line.strip()) for line in lines)


def merge_sections(existing_sections, generated_text):
    generated_sections = extract_sections(generated_text)
    merged = []

    for heading, gen_lines in generated_sections.items():
        merged.append(heading)
        existing_lines = existing_sections.get(heading)
        if existing_lines is not None and section_has_content(existing_lines):
            merged.append("\n".join(existing_lines).rstrip())
        else:
            merged.append("\n".join(gen_lines).rstrip())

    # Preserve any extra existing sections not present in generated output
    for heading, existing_lines in existing_sections.items():
        if heading not in generated_sections and section_has_content(existing_lines):
            merged.append(heading)
            merged.append("\n".join(existing_lines).rstrip())

    return "\n\n".join(merged).strip()


def build_prompt(question_text):
    return PROMPT_TEMPLATE.format(question=question_text)


def generate_content(question_text, model="gpt-4o-mini"):
    if openai is None:
        raise RuntimeError("The openai package is not installed. Install it with `pip install openai`.")

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set. Please export your OpenAI API key.")

    openai.api_key = api_key
    prompt = build_prompt(question_text)

    response = openai.ChatCompletion.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a technical database expert."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=1200,
        temperature=0.3,
    )

    return response.choices[0].message.content.strip()


def ensure_markdown(filename):
    if not filename.endswith(".md"):
        filename += ".md"
    return filename


def main():
    parser = argparse.ArgumentParser(description="Generate detailed concept notes for a question file.")
    parser.add_argument("file", help="The question file name or number, e.g. q1 or q1.md")
    parser.add_argument("--model", default="gpt-4o-mini", help="OpenAI model to use")
    parser.add_argument("--force", action="store_true", help="Overwrite existing sections")
    args = parser.parse_args()

    concepts_dir = os.path.dirname(os.path.abspath(__file__))
    file_name = ensure_markdown(args.file)
    file_path = os.path.join(concepts_dir, file_name)

    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        sys.exit(1)

    content = load_file(file_path)
    title, question = extract_question(content)

    if not question:
        print("Could not extract the question from the file. Make sure the file contains a question line after the title.")
        sys.exit(1)

    existing_sections = extract_sections(content)
    if not args.force and existing_sections and any(section_has_content(lines) for lines in existing_sections.values()):
        print("Existing content detected. Merging missing sections from generated output.")
    else:
        print(f"Generating concept note for: {file_name}")

    generated_note = generate_content(question, model=args.model)
    merged_note = merge_sections(existing_sections, generated_note) if existing_sections and not args.force else generated_note

    output = f"{title}\n\n{question}\n\n{merged_note}\n"
    write_file(file_path, output)
    print(f"Updated {file_name} with generated content.")


if __name__ == "__main__":
    main()
