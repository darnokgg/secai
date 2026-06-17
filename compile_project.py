import os
import re
import json
import sys

BASE = r"C:\Users\darnokg\Desktop\SecAI"
NOTES_PATH = os.path.join(BASE, "notes.md")
BACKUP_PATH = os.path.join(BASE, "notes.bak.md")
DATA_JS_PATH = os.path.join(BASE, "data.js")
LESSON_NOTES_JS_PATH = os.path.join(BASE, "lesson_notes.js")
GLOSSARY_FILE = os.path.join(BASE, "sources", "glossary.txt")

# Ensure output encoding is UTF-8
if sys.stdout:
    sys.stdout.reconfigure(encoding='utf-8')

# Smart Domain categorization keywords
DOMAIN_KEYWORDS = {
    "Domain 4": ["risk", "policy", "governance", "regulation", "law", "nist", "gdpr", "compliance", "bias", "audit", "accountability", "ethics", "responsible", "agreement", "sla"],
    "Domain 3": ["detect", "anomaly", "monitor", "alert", "siem", "soar", "ids", "incident", "log", "threat hunt", "edr", "operations", "analysis", "analyst"],
    "Domain 2": ["threat", "attack", "jailbreak", "poisoning", "adversarial", "injection", "guardrail", "defense", "security control", "restrict", "access control", "rbac", "abac", "sandbox", "securing", "encryption"]
}

def guess_domain(term, definition):
    combined = (term + " " + definition).lower()
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if any(kw in combined for kw in keywords):
            return domain
    return "Domain 1"

def read_file(path):
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()

def parse_existing_glossary(md_content):
    glossary = {}
    lines = md_content.split("\n")
    in_table = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('|') and 'Term' in stripped and 'Domain' in stripped:
            in_table = True
            continue
        if in_table:
            if not stripped.startswith('|'):
                in_table = False
            else:
                if re.match(r'^\|?\s*:?-+:?\s*\|', stripped):
                    continue
                parts = [p.strip() for p in stripped.split('|')]
                if len(parts) >= 5:
                    term = parts[1]
                    domain = parts[2]
                    definition = parts[3]
                    context = parts[4] if len(parts) > 4 else ""
                    term_clean = re.sub(r'\*\*(.*?)\*\*', r'\1', term).strip()
                    if term_clean and term_clean != "Term" and not term_clean.startswith("---"):
                        glossary[term_clean.lower()] = {
                            "term": term_clean,
                            "domain": domain.strip(),
                            "definition": definition.strip(),
                            "context": context.strip()
                        }
    return glossary

def parse_glossary_txt(txt_content):
    lines = [l.replace("\r", "") for l in txt_content.split("\n")]
    terms = {}
    i = 0
    skip_re = re.compile(r"^[A-Z0-9#]$")
    while i < len(lines):
        l = lines[i].strip()
        if not l or skip_re.match(l) or l.lower() == "glossary":
            i += 1
            continue
        term = l.rstrip("\t").strip()
        definition_lines = []
        i += 1
        while i < len(lines):
            dl = lines[i].strip()
            if not dl:
                i += 1
                break
            if skip_re.match(dl):
                break
            definition_lines.append(dl)
            i += 1
        definition = " ".join(definition_lines).strip()
        if term and definition:
            terms[term.lower()] = (term, definition)
    return terms

def parse_options_block(options_block):
    raw_options = []
    buf = []
    pending_correct_hdr = False
    pending_incorrect_hdr = False

    def flush(correct=False, incorrect=False):
        text = " ".join(buf).strip()
        buf.clear()
        if text:
            raw_options.append([text, correct, incorrect])

    for line in options_block:
        ls = line.strip()
        lsl = ls.lower()

        if lsl == "correct answer:":
            pending_correct_hdr = True
        elif lsl == "incorrect answer:":
            pending_incorrect_hdr = True
        elif lsl == "correct" and pending_correct_hdr:
            flush()
            if raw_options:
                raw_options[-1][1] = True
            pending_correct_hdr = False
        elif lsl == "incorrect" and pending_incorrect_hdr:
            flush()
            if raw_options:
                raw_options[-1][2] = True
            pending_incorrect_hdr = False
        elif ls == "":
            flush()
        else:
            pending_correct_hdr = False
            pending_incorrect_hdr = False
            buf.append(ls)
    flush()
    return raw_options

def parse_questions(raw_text, module_num):
    lines = [l.replace("\r", "") for l in raw_text.split("\n")]
    q_header_re = re.compile(r"^Question\s+\d+\s*$")
    q_starts = [i for i, l in enumerate(lines) if q_header_re.match(l.strip())]
    questions = []

    for idx, start in enumerate(q_starts):
        end = q_starts[idx + 1] if idx + 1 < len(q_starts) else len(lines)
        block = lines[start:end]

        answer_idx = None
        for i, l in enumerate(block):
            if l.strip().lower() == "answer":
                answer_idx = i
                break
        if answer_idx is None:
            continue

        skip_re = re.compile(r"^(Question\s+\d+|Flag for Review|Check Answer)\s*$", re.I)
        stem_lines = []
        for l in block[1:answer_idx]:
            if not skip_re.match(l.strip()):
                stem_lines.append(l)
        stem = "\n".join(stem_lines).strip()
        if not stem:
            continue

        expl_idx = None
        for i, l in enumerate(block):
            if l.strip().lower() == "explanation":
                expl_idx = i
                break

        options_end = expl_idx if expl_idx is not None else len(block)
        options_block = block[answer_idx + 1: options_end]

        raw_options = parse_options_block(options_block)

        # Deduplicate options
        seen = set()
        deduped = []
        for opt in raw_options:
            key = opt[0].lower()[:80]
            if key not in seen:
                seen.add(key)
                deduped.append(opt)
        raw_options = deduped

        correct_idx = next((i for i, o in enumerate(raw_options) if o[1]), None)
        if correct_idx is None:
            continue

        letters = "ABCDEFGHIJ"
        options_with_letters = []
        correct_letter = None
        for i_opt, opt in enumerate(raw_options):
            letter = letters[i_opt] if i_opt < len(letters) else f"OPT{i_opt}"
            options_with_letters.append((letter, opt[0]))
            if opt[1]:
                correct_letter = letter

        if expl_idx is not None:
            expl_lines = []
            prev_blank = False
            for l in block[expl_idx + 1:]:
                if q_header_re.match(l.strip()):
                    break
                stripped = l.strip()
                if not stripped:
                    prev_blank = True
                    continue
                if prev_blank and looks_like_section_header(stripped):
                    break
                expl_lines.append(stripped)
                prev_blank = False
            explanation = " ".join(expl_lines)
        else:
            explanation = ""

        questions.append({
            "stem": stem,
            "options": options_with_letters,
            "correct_letter": correct_letter,
            "correct_index": correct_idx,
            "explanation": explanation,
            "module": module_num
        })

    return questions

# Lesson Notes extraction state machine logic
Q_HEADER   = re.compile(r"^Question\s+\d+\s*$")
BOILERPLATE = re.compile(r"^(Flag for Review|Check Answer|answer)\s*$", re.I)
CORRECT_MK = re.compile(r"^(Correct Answer:|Correct|Incorrect answer:|Incorrect)\s*$", re.I)
EXPL_HDR   = re.compile(r"^Explanation\s*$", re.I)
NOISE_LINE = re.compile(
    r"^(Images \(c\)|A circular|An arrow|An illustration|Description|"
    r"Keyboard Instructions|Review Lab|Before completing|The following questions|"
    r"A flowchart|A diagram|A table|A screenshot|"
    r"reinforce|ensure you.re ready|apply them in practice)\s*",
    re.I
)

def looks_like_section_header(stripped):
    if not stripped or len(stripped) > 75 or len(stripped) < 4:
        return False
    if stripped.endswith(".") or stripped.endswith(",") or stripped.endswith(":"):
        return False
    if not (stripped[0].isupper() or stripped[0].isdigit()):
        return False
    skip_prefixes = {
        "images", "a circular", "an arrow", "an illustration", "a flowchart",
        "description", "the ai lifecycle", "generative adversarial",
        "a mid-sized", "a security", "an ai-based", "a law", "a company",
        "which", "how", "what", "when", "why", "select", "the",
    }
    lower = stripped.lower()
    if any(lower.startswith(p) for p in skip_prefixes):
        return False
    words = stripped.split()
    if len(words) > 12:
        return False
    return True

def extract_lesson_text(raw_text):
    lines = [l.replace("\r", "") for l in raw_text.split("\n")]
    state = "LESSON"
    in_options = False
    lesson_lines = []
    prev_blank = True

    for i, line in enumerate(lines):
        stripped = line.strip()
        if Q_HEADER.match(stripped):
            state = "IN_Q"
            in_options = False
            prev_blank = False
            continue

        if state == "LESSON":
            if NOISE_LINE.match(stripped):
                prev_blank = bool(not stripped)
                continue
            lesson_lines.append(line)
            prev_blank = not stripped
            continue

        if state == "IN_Q":
            if BOILERPLATE.match(stripped):
                continue
            if stripped.lower() == "answer":
                in_options = True
                continue
            if in_options and CORRECT_MK.match(stripped):
                continue
            if EXPL_HDR.match(stripped):
                state = "IN_EXPL"
                in_options = False
                prev_blank = False
                continue
            continue

        if state == "IN_EXPL":
            if not stripped:
                prev_blank = True
                continue
            if prev_blank and looks_like_section_header(stripped):
                state = "LESSON"
                lesson_lines.append("")
                lesson_lines.append(line)
                prev_blank = False
                continue
            prev_blank = False
            continue

    return "\n".join(lesson_lines)

def format_lesson_text(raw):
    lines = raw.split("\n")
    output = []
    prev_blank = True

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if output and output[-1] != "":
                output.append("")
            prev_blank = True
            continue

        if NOISE_LINE.match(stripped):
            continue

        if prev_blank and looks_like_section_header(stripped):
            output.append(f"\n### {stripped}")
            prev_blank = False
            continue

        if stripped.lower().startswith("note:"):
            output.append(f"\n> **Note:** {stripped[5:].strip()}")
            prev_blank = False
            continue

        num = re.match(r"^(\d+)\.\s+(.+)$", stripped)
        if num:
            output.append(f"{num.group(1)}. {num.group(2)}")
            prev_blank = False
            continue

        output.append(stripped)
        prev_blank = False

    result, blanks = [], 0
    for l in output:
        if l == "":
            blanks += 1
            if blanks <= 1:
                result.append(l)
        else:
            blanks = 0
            result.append(l)

    return "\n".join(result).strip()

def parse_lesson_notes_from_formatted(formatted_text, module_num, title, color, icon, tag):
    blocks = []
    paragraphs = re.split(r"\n{2,}", formatted_text.strip())
    sections = []
    curr_section = {"heading": None, "slug": "intro", "blocks": []}

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if para.startswith("### "):
            if curr_section["blocks"]:
                sections.append(curr_section)
            heading = para[4:].strip()
            slug = re.sub(r'[^a-z0-9]+', '-', heading.lower()).strip('-')
            curr_section = {"heading": heading, "slug": slug, "blocks": []}
            continue

        # Process paragraph into blocks (note, list, or regular paragraph)
        if para.startswith("> **Note:**"):
            content = para[11:].strip()
            content = re.sub(r"\*\*(.+?)\*\*", r"\1", content)
            curr_section["blocks"].append({"type": "note", "content": content})
            continue

        # Check for list
        lines = para.split("\n")
        list_items = []
        for line in lines:
            m = re.match(r"^(\d+)\.\s+(.+)$", line.strip())
            if m:
                list_items.append(m.group(2).strip())

        if list_items and len(list_items) >= len(lines) * 0.6:
            curr_section["blocks"].append({"type": "list", "items": [re.sub(r"\*\*(.+?)\*\*", r"\1", i) for i in list_items]})
            continue

        # Regular paragraph
        clean = re.sub(r"\*\*(.+?)\*\*", r"\1", para)
        clean = re.sub(r"\*(.+?)\*", r"\1", clean)
        clean = re.sub(r"^>\s*", "", clean, flags=re.MULTILINE)
        clean = " ".join(clean.split())
        if clean:
            curr_section["blocks"].append({"type": "paragraph", "content": clean})

    if curr_section["blocks"]:
        sections.append(curr_section)

    return {
        "id": module_num,
        "fullTitle": f"Module {module_num}: {title}",
        "title": title,
        "color": color,
        "icon": icon,
        "tag": tag,
        "sections": sections
    }

def main():
    print("=== SecAI Unified Re-Compiler ===")
    
    # 1. Back up existing notes.md
    if os.path.exists(NOTES_PATH):
        print("[BACKUP] Backing up notes.md to notes.bak.md...")
        with open(NOTES_PATH, "r", encoding="utf-8") as f_in:
            with open(BACKUP_PATH, "w", encoding="utf-8") as f_out:
                f_out.write(f_in.read())

    # 2. Load and parse existing glossary from notes.md to preserve domain/context
    notes_md_content = read_file(NOTES_PATH)
    existing_glossary = parse_existing_glossary(notes_md_content)
    print(f"[GLOSSARY] Loaded {len(existing_glossary)} existing terms from notes.md")

    # 3. Read glossary.txt and merge terms
    glossary_txt_content = read_file(GLOSSARY_FILE)
    txt_glossary = parse_glossary_txt(glossary_txt_content)
    print(f"[GLOSSARY] Parsed {len(txt_glossary)} terms from glossary.txt")

    merged_glossary = {}
    for term_lower, (term, definition) in txt_glossary.items():
        if term_lower in existing_glossary:
            # Keep existing, but update definition if it exists
            item = existing_glossary[term_lower]
            item["definition"] = definition
            merged_glossary[term_lower] = item
        else:
            domain = guess_domain(term, definition)
            merged_glossary[term_lower] = {
                "term": term,
                "domain": domain,
                "definition": definition,
                "context": "Extracted from CompTIA Glossary."
            }

    # Re-integrate any existing glossary terms that weren't in glossary.txt
    for term_lower, item in existing_glossary.items():
        if term_lower not in merged_glossary:
            merged_glossary[term_lower] = item

    sorted_glossary = [merged_glossary[k] for k in sorted(merged_glossary.keys())]
    print(f"[GLOSSARY] Merged glossary has {len(sorted_glossary)} terms")

    # 4. Parse Modules 1-6
    module_metadata = {
        1: {"title": "Explain AI Concepts for Cybersecurity", "color": "#fbbf24", "icon": "🧠", "tag": "Basic AI Concepts Related to Cybersecurity", "domain": "Domain 1"},
        2: {"title": "Implementing Threat Modeling and Securing AI Systems", "color": "#f87171", "icon": "🎯", "tag": "Implementing Threat Modeling & Securing AI", "domain": "Domain 2"},
        3: {"title": "Installing Access Controls for AI", "color": "#60a5fa", "icon": "🔑", "tag": "Access Controls & Data Security", "domain": "Domain 2"},
        4: {"title": "Security in the AI Life Cycle & Compensating Controls", "color": "#a78bfa", "icon": "🔒", "tag": "AI Lifecycle & Security Controls", "domain": "Domain 2"},
        5: {"title": "AI Tools in Security Operations & AI-Enabled Attacks", "color": "#38bdf8", "icon": "🛡️", "tag": "AI Tools & AI-Enabled Attacks", "domain": "Domain 3"},
        6: {"title": "AI Governance, Risk & Compliance", "color": "#34d399", "icon": "📋", "tag": "AI Governance, Risk & Compliance", "domain": "Domain 4"}
    }

    parsed_questions = []
    question_seen_stems = set()
    lesson_notes_js_list = []
    all_lessons_formatted = {}

    for mod_num in range(1, 7):
        filepath = os.path.join(BASE, "sources", f"module {mod_num}.txt")
        if not os.path.exists(filepath):
            print(f"[WARN] Module {mod_num} txt file not found at {filepath}")
            continue
        
        print(f"[PARSING] Module {mod_num}...")
        raw_content = read_file(filepath)
        
        # Parse Questions
        mod_questions = parse_questions(raw_content, mod_num)
        print(f"  -> Found {len(mod_questions)} raw questions")
        
        mod_unique_qs = []
        for q in mod_questions:
            # Normalize stem to check for duplicates
            normalized_stem = re.sub(r'[^a-z0-9]+', '', q["stem"].lower())
            if normalized_stem not in question_seen_stems:
                question_seen_stems.add(normalized_stem)
                mod_unique_qs.append(q)
            else:
                pass # Skip duplicate

        print(f"  -> {len(mod_unique_qs)} unique questions")
        parsed_questions.extend(mod_unique_qs)

        # Parse Lesson Notes
        lesson_raw = extract_lesson_text(raw_content)
        lesson_formatted = format_lesson_text(lesson_raw)
        all_lessons_formatted[mod_num] = lesson_formatted
        
        meta = module_metadata[mod_num]
        lesson_obj = parse_lesson_notes_from_formatted(lesson_formatted, mod_num, meta["title"], meta["color"], meta["icon"], meta["tag"])
        lesson_notes_js_list.append(lesson_obj)
        print(f"  -> Lesson notes extracted: {len(lesson_formatted)} chars, {len(lesson_obj['sections'])} sections")

    # Re-index questions so their IDs are consecutive
    print(f"[QUESTIONS] Re-indexing {len(parsed_questions)} questions...")
    final_questions = []
    for idx, q in enumerate(parsed_questions):
        q_id = idx + 1
        
        # Extract title slug
        slug_words = q["stem"].replace("\n", " ").split()[:10]
        slug = " ".join(slug_words)
        if len(slug) > 90:
            slug = slug[:87] + "..."
            
        domain_name = module_metadata[q["module"]]["domain"]
        
        final_questions.append({
            "id": q_id,
            "module": q["module"],
            "domain": domain_name,
            "title": slug,
            "question": q["stem"],
            "options": [opt[1] for opt in q["options"]],
            "correctIndex": q["correct_index"],
            "correctLetter": q["correct_letter"],
            "explanation": q["explanation"]
        })

    # 5. Re-write notes.md
    print("[WRITE] Rebuilding notes.md...")
    notes_lines = []
    notes_lines.append("# SecAI+ Study Portal Markdown Log\n")
    
    # Navigation / Quick Stats
    notes_lines.append("## 📋 Quick Navigation")
    notes_lines.append("- [Study Progress Tracker](#-study-progress-tracker)")
    notes_lines.append("- [Glossary & Key Terms Log](#-glossary--key-terms-log)")
    for mod_num in range(1, 7):
        notes_lines.append(f"- [Module {mod_num} Lesson Notes](#module-{mod_num}-lesson-notes)")
        notes_lines.append(f"- [Module {mod_num} Practice Questions](#module-{mod_num}-practice-questions)")
    notes_lines.append("")

    notes_lines.append("## 📈 Study Progress Tracker")
    notes_lines.append("| Activity | Progress | Percentage |")
    notes_lines.append("| --- | --- | --- |")
    notes_lines.append(f"| Practice Questions | 0 / {len(final_questions)} | 0% |")
    notes_lines.append(f"| Glossary Terms | 0 / {len(sorted_glossary)} | 0% |")
    notes_lines.append("")

    # Glossary Section
    notes_lines.append("## 📖 Glossary & Key Terms Log")
    notes_lines.append("| Term | Domain | Definition | Context |")
    notes_lines.append("| --- | --- | --- | --- |")
    for item in sorted_glossary:
        term_bold = f"**{item['term']}**"
        notes_lines.append(f"| {term_bold} | {item['domain']} | {item['definition']} | {item['context']} |")
    notes_lines.append("")

    # Lesson Notes and Practice Questions Modules 1-6
    for mod_num in range(1, 7):
        meta = module_metadata[mod_num]
        
        # Lesson Notes
        notes_lines.append(f"## Module {mod_num} Lesson Notes\n")
        notes_lines.append(f"# Module {mod_num}: {meta['title']}\n")
        notes_lines.append(all_lessons_formatted.get(mod_num, "No lesson notes available."))
        notes_lines.append("")
        
        # Practice Questions
        notes_lines.append(f"## Module {mod_num} Practice Questions\n")
        mod_qs = [q for q in final_questions if q["module"] == mod_num]
        for q in mod_qs:
            notes_lines.append(f"### 📝 Question {q['id']}: {q['title']}")
            q_clean = q["question"].replace("\n", " ")
            notes_lines.append(f"*   **Question:** {q_clean}")
            for opt_idx, opt_text in enumerate(q["options"]):
                letter = chr(65 + opt_idx)
                marker = "x" if opt_idx == q["correctIndex"] else " "
                notes_lines.append(f"    - [{marker}] **{letter}.** {opt_text}")
            notes_lines.append(f"*   **Correct Answer: {q['correctLetter']}**")
            notes_lines.append(f"*   **Explanation:** {q['explanation']}")
            notes_lines.append("")
        
    with open(NOTES_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(notes_lines))
    print(f"  -> Successfully wrote notes.md ({os.path.getsize(NOTES_PATH)//1024} KB)")

    # 6. Re-write data.js
    print("[WRITE] Rebuilding data.js...")
    # Map glossary terms list
    glossary_data = []
    for item in sorted_glossary:
        glossary_data.append({
            "term": item["term"],
            "domain": item["domain"],
            "definition": item["definition"],
            "context": item["context"]
        })
        
    # Load AI-generated questions if they exist
    ai_questions = []
    ai_questions_path = os.path.join(BASE, "sources", "ai_generated_questions.json")
    if os.path.exists(ai_questions_path):
        try:
            with open(ai_questions_path, "r", encoding="utf-8") as f:
                ai_questions = json.load(f)
            print(f"  -> Loaded {len(ai_questions)} AI-generated questions from ai_generated_questions.json")
        except Exception as e:
            print(f"  -> [WARN] Failed to load AI-generated questions: {e}")

    js_content = f"""// Auto-generated data file. Do not edit directly.
const SEC_AI_DATA = {{
  glossary: {json.dumps(glossary_data, indent=2)},
  questions: {json.dumps(final_questions, indent=2)},
  ai_questions: {json.dumps(ai_questions, indent=2)}
}};
"""
    with open(DATA_JS_PATH, "w", encoding="utf-8") as f:
        f.write(js_content)
    print(f"  -> Successfully wrote data.js ({os.path.getsize(DATA_JS_PATH)//1024} KB)")

    # 7. Re-write lesson_notes.js
    print("[WRITE] Rebuilding lesson_notes.js...")
    lesson_js_content = f"""// Auto-generated from notes.md by compile_lesson_notes.py
// Do not edit manually — re-run the script to update.
const LESSON_NOTES = {json.dumps(lesson_notes_js_list, indent=2)};
"""
    with open(LESSON_NOTES_JS_PATH, "w", encoding="utf-8") as f:
        f.write(lesson_js_content)
    print(f"  -> Successfully wrote lesson_notes.js ({os.path.getsize(LESSON_NOTES_JS_PATH)//1024} KB)")
    
    print("\n=== Compilation complete! ===")
    print(f"Total Questions: {len(final_questions)}")
    print(f"Total Glossary Terms: {len(sorted_glossary)}")

if __name__ == "__main__":
    main()
