from collections import defaultdict
from typing import Dict, List, Tuple

from detectors import DetectedEntity, detect_all
from document import get_full_text, write_redacted_docx
from replacements import ReplacementMap


def redact(input_path: str, output_path: str) -> Tuple[Dict[str, int], List[DetectedEntity]]:
    """main pipeline: detect → map → write.

    returns (counts_by_type, all_entities)
    """
    text = get_full_text(input_path)
    entities = detect_all(text)

    rmap = ReplacementMap()
    text_replacements: List[Tuple[str, str]] = []
    for entity in entities:
        fake_val = rmap.get_or_create(entity)
        text_replacements.append((entity.text, fake_val))

    # deduplicate replacement pairs (same original can appear many times)
    seen = set()
    unique_repls = []
    for orig, repl in text_replacements:
        if orig not in seen:
            seen.add(orig)
            unique_repls.append((orig, repl))

    write_redacted_docx(input_path, unique_repls, output_path)

    counts: Dict[str, int] = defaultdict(int)
    for e in entities:
        counts[e.type] += 1

    return dict(counts), entities


if __name__ == "__main__":
    import sys
    inp = sys.argv[1] if len(sys.argv) > 1 else "input/Scalar.docx"
    out = sys.argv[2] if len(sys.argv) > 2 else "output/redacted_output.docx"
    counts, entities = redact(inp, out)
    print("Redaction complete.")
    for ptype, cnt in sorted(counts.items()):
        print(f"  {ptype}: {cnt}")
    print(f"Output: {out}")
