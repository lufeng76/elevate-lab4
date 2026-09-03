"""Track B — OKF retrieval tools.

The agent uses these to *navigate* the Open Knowledge Format bundle in knowledge/:
first list what concepts exist, then read the most relevant one. No vector DB.

You implement two functions. Keep the return shapes exactly as documented — the
prompt and the agent rely on them.
"""
import os
import re
import yaml

from .. import config  # config.KNOWLEDGE_DIR points at the knowledge/ bundle

RESERVED = {"index.md", "log.md"}
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)


def _parse_frontmatter_and_body(text: str):
    """Split text into (frontmatter_dict, body_text)."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    try:
        data = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        data = {}
    body = text[m.end():]
    return data, body


def list_concepts() -> dict:
    """List the policy concepts available in the OKF bundle.

    Returns:
        {"concepts": [{"id": str, "title": str, "description": str}, ...]}
        where `id` is the concept path without the .md suffix,
        e.g. "leave/bereavement-leave".
    """
    concepts = []
    knowledge_dir = os.path.abspath(config.KNOWLEDGE_DIR)
    for dirpath, _dirs, files in os.walk(knowledge_dir):
        for name in sorted(files):
            if not name.endswith(".md") or name in RESERVED:
                continue
            path = os.path.join(dirpath, name)
            rel_path = os.path.relpath(path, knowledge_dir).replace("\\", "/")
            if rel_path.endswith(".md"):
                concept_id = rel_path[:-3]
            else:
                concept_id = rel_path

            try:
                with open(path, "r", encoding="utf-8") as f:
                    text = f.read()
                data, _ = _parse_frontmatter_and_body(text)
                title = data.get("title") or ""
                description = data.get("description") or ""
                concepts.append({
                    "id": concept_id,
                    "title": title,
                    "description": description,
                })
            except Exception:
                continue

    concepts.sort(key=lambda c: c["id"])
    return {"concepts": concepts}


def read_concept(concept_id: str) -> dict:
    """Read one OKF concept's content and citation.

    Args:
        concept_id: e.g. "03-other-compassionate-unpaid-leaves/3.1-bereavement-leave-global" (no .md).

    Returns:
        {"content": str, "title": str, "resource": str | None}
        where `content` is the markdown body (after the frontmatter) and
        `resource` is the frontmatter `source` (or `resource`) reference if present.
    """
    clean_id = concept_id.strip().lstrip("/")
    if clean_id.endswith(".md"):
        clean_id = clean_id[:-3]

    knowledge_dir = os.path.abspath(config.KNOWLEDGE_DIR)
    target_path = os.path.normpath(os.path.join(knowledge_dir, clean_id + ".md"))

    # Path traversal protection
    if not target_path.startswith(knowledge_dir + os.sep) and target_path != knowledge_dir:
        return {
            "error": f"Invalid concept path '{concept_id}'. Access outside knowledge directory is prohibited.",
            "content": "",
            "title": "",
            "resource": None,
        }

    if not os.path.isfile(target_path):
        return {
            "error": f"Concept '{concept_id}' not found.",
            "content": "",
            "title": "",
            "resource": None,
        }

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            text = f.read()
        data, body = _parse_frontmatter_and_body(text)
        title = data.get("title") or ""
        resource = data.get("source") or data.get("resource")
        return {
            "content": body.strip(),
            "title": title,
            "resource": resource,
        }
    except Exception as e:
        return {
            "error": f"Error reading concept '{concept_id}': {e}",
            "content": "",
            "title": "",
            "resource": None,
        }

