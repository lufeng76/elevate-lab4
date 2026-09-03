#!/usr/bin/env python3
"""Build the OKF knowledge bundle VERBATIM from the handbook PDF (HR_policy.pdf).

Conforms to Open Knowledge Format (OKF v0.2) specification:
https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/README.md
https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/main/SPEC.md

Usage:
    python tools_build_okf.py --dry     # manifest + spot-checks, writes nothing
    python tools_build_okf.py --write   # (re)generate knowledge/ concept files
"""
import argparse
import json
import os
import re
import shutil
import sys

from pypdf import PdfReader

REPO = os.path.dirname(os.path.abspath(__file__))
PDF = os.path.join(REPO, "HR_policy.pdf")
KN = os.path.join(REPO, "knowledge")

SEC_RE = re.compile(r"SECTION\s+(\d+)\s*:\s*([A-Z][A-Z].*?)\s*$")
SUB_RE = re.compile(r"^(\d{1,2})\.(\d{1,2})\s+([A-Z].*?)\s*$")


def slug(s):
    s = re.sub(r"[’'&(),/]", "", s.lower())
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return re.sub(r"-+", "-", s)


def normalize_body(lines):
    """Join PDF-fragmented lines into faithful text; keep bullets as markdown."""
    text = "\n".join(lines)
    # bullets: ● -> top-level, ○ -> nested
    text = text.replace("●", "\n●").replace("○", "\n○")
    out_lines = []
    for chunk in text.split("\n"):
        c = re.sub(r"\s+", " ", chunk).strip()
        if not c:
            continue
        if c.startswith("●"):
            out_lines.append("- " + c.lstrip("● ").strip())
        elif c.startswith("○"):
            out_lines.append("  - " + c.lstrip("○ ").strip())
        else:
            # continuation of previous paragraph/bullet
            if out_lines and not out_lines[-1].startswith("#"):
                out_lines[-1] = (out_lines[-1] + " " + c).strip()
            else:
                out_lines.append(c)
    return "\n".join(out_lines).strip()


def parse():
    reader = PdfReader(PDF)
    raw = "\n".join((p.extract_text() or "") for p in reader.pages)
    lines = raw.split("\n")

    sections = {}          # num -> title
    concepts = []          # (sec_num, sub_num, title, [body lines])
    def norm(t):
        return re.sub(r"\s+", " ", t).strip()

    def title_of(remainder):
        toks = norm(remainder).split()
        n = len(toks)

        def low(t):
            return t[:1].islower()

        cut = min(n, 12)
        for i in range(1, n):
            tk, nxt, aft = toks[i], toks[i + 1] if i + 1 < n else "", toks[i + 2] if i + 2 < n else ""
            if re.match(r"^[A-Z][a-z]+$", tk) and low(nxt) and (aft == "" or low(aft)):
                cut = i
                break
            if tk in ("A", "I") and low(nxt):
                cut = i
                break
            if re.match(r"^[A-Z][a-z]+$", tk) and re.match(r"^[A-Z][a-z]+$", nxt) and aft[:1].isdigit():
                cut = i
                break
        return " ".join(toks[:cut]).strip(" :")

    def start_sub(sec_n, sub_n, remainder, clean):
        title = norm(remainder) if clean else title_of(remainder)
        c = {"sec": sec_n, "sub": sub_n, "title": norm(f"{sec_n}.{sub_n} {title}"),
             "body": [] if clean else [remainder]}
        concepts.append(c)
        return c

    cur = None
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        m_sec = SEC_RE.search(s)
        if m_sec:
            sec_n = int(m_sec.group(1))
            rest = m_sec.group(2)
            sections.setdefault(sec_n, norm(rest))
            m_embed = re.search(r"(\d{1,2})\.(\d{1,2})\s+([A-Z].*)$", rest)
            if m_embed and int(m_embed.group(1)) == sec_n:
                sections[sec_n] = norm(rest[: m_embed.start()])
                cur = start_sub(sec_n, int(m_embed.group(2)), m_embed.group(3), clean=False)
            else:
                cur = None
            continue
        m_sub = SUB_RE.match(s)
        if m_sub and int(m_sub.group(1)) in sections and int(m_sub.group(2)) <= 20 \
           and " Section " not in s:
            clean = len(s) <= 80 and not s.endswith(".")
            cur = start_sub(int(m_sub.group(1)), int(m_sub.group(2)), m_sub.group(3), clean=clean)
            continue
        if cur is not None:
            cur["body"].append(s)
    return sections, concepts


_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def make_description(body: str, max_len: int = 240, max_labels: int = 8) -> str:
    first_text = ""
    labels = []
    intro = ""
    for raw in body.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        is_bullet = line[:1] in "-*"
        content = line[1:].strip() if is_bullet else line
        if not first_text:
            first_text = _SENT_SPLIT.split(content, 1)[0].strip()
        if is_bullet:
            head = content.split(":", 1)[0].strip() if ":" in content else ""
            if head and len(head) <= 60 and len(head.split()) <= 8 and head not in labels:
                labels.append(head)
        elif not intro:
            intro = _SENT_SPLIT.split(content, 1)[0].strip()

    if not intro and not labels:
        intro = first_text
    labels = labels[:max_labels]
    labels_str = ("Covers: " + "; ".join(labels) + ".") if labels else ""
    intro_budget = max(0, max_len - len(labels_str) - 1)
    if len(intro) > intro_budget:
        intro = intro[:intro_budget].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"
    desc = re.sub(r"\s+", " ", (intro + " " + labels_str)).strip()
    return desc[:max_len].strip()


def derive_tags(sec_title: str, concept_title: str) -> list:
    tags = {"hr", "policy", "singapore"}
    combined = (sec_title + " " + concept_title).lower()
    mapping = {
        "leave": ["leave", "time-off"],
        "vacation": ["vacation", "pto"],
        "sick": ["sick-leave", "medical"],
        "hospitalization": ["hospitalization", "medical"],
        "maternity": ["maternity", "parental-leave"],
        "baby bonding": ["parental-leave", "bonding"],
        "childcare": ["childcare", "family"],
        "bereavement": ["bereavement", "compassionate-leave"],
        "travel": ["travel", "t&e"],
        "expense": ["expenses", "reimbursement"],
        "gift": ["gifts", "entertainment", "compliance"],
        "ethics": ["ethics", "compliance", "code-of-conduct"],
        "anti-bribery": ["anti-bribery", "anti-corruption"],
        "harassment": ["workplace-conduct", "respect"],
        "privacy": ["privacy", "data-protection", "gdpr"],
        "performance": ["performance-management", "pip"],
        "disciplinary": ["disciplinary", "misconduct"],
        "remote": ["remote-work", "telework"],
        "safety": ["workplace-safety", "wsh"],
        "health insurance": ["health-insurance", "benefits"],
        "compensation": ["compensation", "payroll"],
    }
    for keyword, kw_tags in mapping.items():
        if keyword in combined:
            tags.update(kw_tags)
    return sorted(tags)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    sections, concepts = parse()
    print(f"SECTIONS: {len(sections)} | CONCEPTS: {len(concepts)}")

    # spot-check verbatim facts survive
    allbody = "\n".join(normalize_body(c["body"]) for c in concepts)
    checks = ["14 days", "46 work days", "48 hours", "1.5 vacation days",
              "$50 per day", "gift cards", "room salons", "20 work days"]
    print("\nVERBATIM SPOT-CHECKS:")
    for ch in checks:
        print(f"  {'OK ' if ch in allbody else 'MISS'} {ch!r}")

    if args.dry:
        print("\nMANIFEST (first 8 + last 4):")
        for c in concepts[:8] + concepts[-4:]:
            b = normalize_body(c["body"])
            print(f"  sec{c['sec']:>2} {c['title'][:52]:52}  {len(b):5d} chars")
        return

    if not args.write:
        print("\n(use --dry or --write)")
        return

    os.makedirs(KN, exist_ok=True)
    ref_dir = os.path.join(KN, "references")
    os.makedirs(ref_dir, exist_ok=True)
    shutil.copy2(PDF, os.path.join(ref_dir, "HR_policy.pdf"))

    # wipe old concept files (keep check_okf.py, references)
    for dirpath, _d, files in os.walk(KN):
        if "references" in dirpath:
            continue
        for f in files:
            if f.endswith(".md"):
                os.remove(os.path.join(dirpath, f))
    for d in list(os.listdir(KN)):
        if d == "references":
            continue
        p = os.path.join(KN, d)
        if os.path.isdir(p) and not os.listdir(p):
            os.rmdir(p)

    by_sec = {}
    for c in concepts:
        by_sec.setdefault(c["sec"], []).append(c)

    root_lines = [
        "---",
        'okf_version: "0.2"',
        'title: "Altostrat Singapore Employee Policy Handbook & Conduct Guidelines"',
        'description: "Open Knowledge Format (OKF v0.2) knowledge bundle for Altostrat Singapore HR policies."',
        "---",
        "",
        "# Altostrat Singapore Employee Policy Handbook & Conduct Guidelines",
        "",
        "Open Knowledge Format (OKF v0.2) organization of the handbook. Every concept file is the handbook's own text for one subsection, verbatim.",
        "",
        "## Knowledge Organization",
        "This bundle is structured hierarchically into policy domains with YAML frontmatter containing provenance, trust, and lifecycle metadata.",
        "",
    ]

    for sec_n in sorted(by_sec):
        title = sections.get(sec_n, f"Section {sec_n}")
        d = f"{sec_n:02d}-{slug(title)}"
        os.makedirs(os.path.join(KN, d), exist_ok=True)
        idx = [f"# Section {sec_n}: {title}", ""]
        root_lines.append(f"## Section {sec_n}: {title}")
        for c in by_sec[sec_n]:
            fn = f"{c['sec']}.{c['sub']}-{slug(c['title'].split(' ',1)[1])}.md"
            cid = f"{d}/{fn[:-3]}"
            body = normalize_body(c["body"])
            tags = derive_tags(title, c["title"])
            tags_yaml = "[" + ", ".join(f'"{t}"' for t in tags) + "]"
            
            fm = [
                "---",
                "type: Policy",
                f'title: "{c["title"]}"',
                f"description: {json.dumps(make_description(body))}",
                f'resource: "references/HR_policy.pdf#section={c["sec"]}.{c["sub"]}"',
                f'source: "Altostrat Singapore Employee Policy Handbook & Conduct Guidelines, Section {c["sec"]}.{c["sub"]}"',
                f"tags: {tags_yaml}",
                "sources:",
                "  - id: altostrat-handbook",
                "    resource: references/HR_policy.pdf",
                '    title: "Altostrat Singapore Employee Policy Handbook & Conduct Guidelines"',
                "    author: team:altostrat-hr",
                "    last_modified: 2026-09-01T00:00:00Z",
                "generated: { by: agent:okf-generator/0.2, at: 2026-09-03T08:00:00Z }",
                "status: stable",
                "---",
                "",
                f"# {c['title']}",
                "",
                body,
                ""
            ]
            with open(os.path.join(KN, d, fn), "w", encoding="utf-8") as fh:
                fh.write("\n".join(fm))
            idx.append(f"- [{c['title']}](/{cid}.md)")
            root_lines.append(f"- [{c['title']}](/{cid}.md)")
        with open(os.path.join(KN, d, "index.md"), "w", encoding="utf-8") as fh:
            fh.write("\n".join(idx) + "\n")
        root_lines.append("")

    with open(os.path.join(KN, "index.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(root_lines) + "\n")

    with open(os.path.join(KN, "log.md"), "w", encoding="utf-8") as fh:
        fh.write(
            "# Change Log\n\n"
            "## 2026-09-03\n"
            "- **Upgraded to OKF v0.2** — Full v0.2 frontmatter compliance with provenance (`sources`), "
            "reference PDF storage under `references/HR_policy.pdf`, tags, generated metadata, and lifecycle status.\n"
            "## 2026-07-01\n"
            "- **Creation** — Generated verbatim from the Altostrat Singapore Employee Policy Handbook & Conduct Guidelines PDF.\n"
        )
    print(f"\nWROTE {len(concepts)} concepts across {len(by_sec)} sections to {KN}")


if __name__ == "__main__":
    main()
