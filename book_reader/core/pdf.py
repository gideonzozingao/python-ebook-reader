"""PDF support (optional PyMuPDF import) and PDF metadata extraction."""
from book_reader.utils import clean_subjects


try:  # PDF support is optional: pip install pymupdf
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None


def pdf_info(path) -> dict:
    """Title, author, page count and a rendered first-page cover (PNG bytes)."""
    if fitz is None:
        raise RuntimeError("PDF support needs PyMuPDF:  pip install pymupdf")
    doc = fitz.open(str(path))
    try:
        if doc.needs_pass:
            raise ValueError("password-protected PDFs are not supported")
        if doc.page_count == 0:
            raise ValueError("no pages")
        meta = doc.metadata or {}
        cover = None
        try:
            page = doc[0]
            scale = 320 / max(1.0, page.rect.width)
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            cover = pix.tobytes("png")
        except Exception:
            pass
        return dict(title=(meta.get("title") or "").strip(),
                    author=(meta.get("author") or "").strip(),
                    pages=doc.page_count, cover=cover,
                    subjects=clean_subjects([meta.get("subject") or "",
                                             meta.get("keywords") or ""]))
    finally:
        doc.close()
