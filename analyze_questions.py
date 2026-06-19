import os
import re
import json

def main():
    # Define paths
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_js_path = os.path.join(base_dir, "data.js")

    if not os.path.exists(data_js_path):
        print(f"Error: Could not find data.js at {data_js_path}")
        return

    # Read data.js
    with open(data_js_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract JSON object assigned to SEC_AI_DATA
    # It starts with 'const SEC_AI_DATA = {' and ends with '};'
    match = re.search(r"const\s+SEC_AI_DATA\s*=\s*(\{[\s\S]*\});\s*$", content)
    if not match:
        # Try a simpler bracket matching approach if the above regex fails
        start_idx = content.find("{")
        end_idx = content.rfind("}")
        if start_idx == -1 or end_idx == -1:
            print("Error: Could not find JSON boundaries in data.js")
            return
        json_str = content[start_idx:end_idx+1]
    else:
        json_str = match.group(1)

    # Clean up JS object to valid JSON by quoting the specific top-level keys
    json_str = re.sub(r'\bglossary\s*:', '"glossary":', json_str)
    json_str = re.sub(r'\bai_questions\s*:', '"ai_questions":', json_str)
    json_str = re.sub(r'\bquestions\s*:', '"questions":', json_str)
    
    # Remove trailing commas
    json_str = re.sub(r',\s*([\]\}])', r'\1', json_str)

    try:
        data = json.loads(json_str)
    except Exception as e:
        print(f"Error parsing JSON from data.js: {e}")
        # Debug: print first 200 chars of json_str to see where it failed
        print("Starts with:", json_str[:200])
        return

    # Extract standard and AI questions
    questions = data.get("questions", [])
    ai_questions = data.get("ai_questions", [])

    print("=" * 60)
    print(f"Analyzing {len(questions)} standard questions and {len(ai_questions)} AI questions.")
    print("=" * 60)

    analyze_pool(questions, "Standard Questions")
    if ai_questions:
        print("\n" + "=" * 60)
        analyze_pool(ai_questions, "AI-Generated Questions")
        
        print("\n" + "=" * 60)
        analyze_pool(questions + ai_questions, "All Questions Combined")

def analyze_pool(q_list, label):
    if not q_list:
        print(f"No questions found for: {label}")
        return

    total = len(q_list)
    longest_is_correct_char = 0
    longest_is_correct_word = 0
    letter_counts = {}
    
    correct_char_lens = []
    incorrect_char_lens = []
    correct_word_lens = []
    incorrect_word_lens = []
    
    for q in q_list:
        options = q.get("options", [])
        correct_idx = q.get("correctIndex")
        
        if correct_idx is None and "correctLetter" in q:
            correct_idx = ord(q["correctLetter"].upper()) - 65

        if correct_idx is None or not options:
            continue

        correct_letter = chr(65 + correct_idx)
        letter_counts[correct_letter] = letter_counts.get(correct_letter, 0) + 1

        char_lengths = [len(opt) for opt in options]
        word_lengths = [len(opt.split()) for opt in options]

        # Track lengths of correct vs incorrect options
        for idx, opt in enumerate(options):
            c_len = len(opt)
            w_len = len(opt.split())
            if idx == correct_idx:
                correct_char_lens.append(c_len)
                correct_word_lens.append(w_len)
            else:
                incorrect_char_lens.append(c_len)
                incorrect_word_lens.append(w_len)

        max_char_len = max(char_lengths)
        longest_char_indices = [i for i, l in enumerate(char_lengths) if l == max_char_len]
        
        max_word_len = max(word_lengths)
        longest_word_indices = [i for i, l in enumerate(word_lengths) if l == max_word_len]

        if correct_idx in longest_char_indices:
            longest_is_correct_char += 1
        if correct_idx in longest_word_indices:
            longest_is_correct_word += 1

    print(f"Results for: {label}")
    print(f"Total questions analyzed: {total}")
    
    # 1. Longest answer checks
    pct_char = (longest_is_correct_char / total) * 100
    pct_word = (longest_is_correct_word / total) * 100
    print(f"\nIs the longest option (by character count) correct?")
    print(f"  Yes: {longest_is_correct_char} times ({pct_char:.2f}%)")
    print(f"Is the longest option (by word count) correct?")
    print(f"  Yes: {longest_is_correct_word} times ({pct_word:.2f}%)")

    # 2. Average lengths
    avg_correct_char = sum(correct_char_lens) / len(correct_char_lens) if correct_char_lens else 0
    avg_incorrect_char = sum(incorrect_char_lens) / len(incorrect_char_lens) if incorrect_char_lens else 0
    avg_correct_word = sum(correct_word_lens) / len(correct_word_lens) if correct_word_lens else 0
    avg_incorrect_word = sum(incorrect_word_lens) / len(incorrect_word_lens) if incorrect_word_lens else 0
    
    print(f"\nAverage option lengths:")
    print(f"  Correct options character length:   {avg_correct_char:.2f}")
    print(f"  Incorrect options character length: {avg_incorrect_char:.2f}")
    print(f"  Correct options word length:        {avg_correct_word:.2f}")
    print(f"  Incorrect options word length:      {avg_incorrect_word:.2f}")

    # 3. Letter distributions
    print(f"\nAnswer letter distribution:")
    sorted_letters = sorted(letter_counts.keys())
    for letter in sorted_letters:
        count = letter_counts[letter]
        pct = (count / total) * 100
        print(f"  Option {letter}: {count} times ({pct:.2f}%)")

if __name__ == "__main__":
    main()
