"""수집 어댑터."""

from .rss import MAX_LEAD_CHARS, IngestReport, canonical_url, parse_feed, strip_html

__all__ = ["MAX_LEAD_CHARS", "IngestReport", "canonical_url", "parse_feed", "strip_html"]
