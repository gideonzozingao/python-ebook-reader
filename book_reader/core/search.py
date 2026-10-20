"""Whole-book text search shared by the EPUB and Markdown readers."""

class TextSearchMixin:
    """Needs: self.spine (list) and self.chapter_text(index) -> plain text."""

    def search(self, query: str, limit: int = 1000) -> list[tuple[int, int]]:
        """All matches as (spine index, n-th match inside that chapter)."""
        q = " ".join(query.lower().split())
        hits: list[tuple[int, int]] = []
        if not q:
            return hits
        for i in range(len(self.spine)):
            text = self.chapter_text(i).lower()
            start = n = 0
            while True:
                pos = text.find(q, start)
                if pos < 0:
                    break
                hits.append((i, n))
                n += 1
                start = pos + len(q)
                if len(hits) >= limit:
                    return hits
        return hits
