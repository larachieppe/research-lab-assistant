"""Drop retracted papers before they can ever be used as evidence.

Flagging a retracted paper in the reference list isn't enough - citing one
as supporting evidence is misleading regardless of how prominently it's
labeled, so these are excluded from the candidate pool entirely, before
the filter/extract steps ever see them.
"""

from __future__ import annotations

from src.state import Paper


def exclude_retracted(papers: list[Paper]) -> tuple[list[Paper], int]:
    kept = [p for p in papers if not p.retracted]
    excluded_count = len(papers) - len(kept)
    return kept, excluded_count
