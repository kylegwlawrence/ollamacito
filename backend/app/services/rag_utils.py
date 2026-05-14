"""
Shared helpers for handling RAG retrieval payloads.

These functions are used by both the pre-stream auto-RAG flow in
`messages.py` and the agentic `search_wikipedia` tool in
`agent_service.py`. Pure / stateless.
"""
from typing import Dict, List


def dedupe_hits_by_page(hits: List[Dict], keep_per_page: int = 2) -> List[Dict]:
    """
    Deduplicate retrieved hits by `page_id`, keeping at most `keep_per_page` per page.
    Pattern from LOCAL_WIKIPEDIA_API.md § "Deduplication and reranking".
    """
    seen: Dict[int, int] = {}
    out: List[Dict] = []
    for hit in hits:
        page_id = hit.get("page_id")
        if page_id is None:
            out.append(hit)
            continue
        count = seen.get(page_id, 0)
        if count < keep_per_page:
            out.append(hit)
            seen[page_id] = count + 1
    return out


def format_rag_context(rag_response: Dict) -> str:
    """
    Build the system-prompt block (or tool-result block) for RAG-retrieved chunks.

    Header format `[Title]` or `[Title § Section]` is required (the embedder
    saw these headers during indexing). See LOCAL_WIKIPEDIA_API.md §
    "Prompt assembly pattern that works".
    """
    corpus = rag_response.get("corpus", "")
    hits = rag_response.get("hits", [])
    if not hits:
        return ""

    blocks: List[str] = []
    for hit in hits:
        header = hit.get("title", "(untitled)")
        section = hit.get("section")
        if section:
            header = f"{header} § {section}"
        text = hit.get("text", "")
        blocks.append(f"[{header}]\n{text}")

    body = "\n\n---\n\n".join(blocks)
    return (
        f"RETRIEVED CONTEXT (from {corpus}):\n\n"
        f"{body}\n\n"
        "Use only this context to answer the user's question. "
        "Cite sources by their bracketed title. If the answer isn't in the context, say so."
    )
