"""
HTML link candidate parser for extracting download hyperlinks from landing pages.
"""
import re
from html.parser import HTMLParser
from typing import List


class _HtmlLinkCandidateParser(HTMLParser):
    """Parses HTML document to collect candidate download hyperlinks and refresh targets."""
    def __init__(self):
        super().__init__()
        self.raw_candidates: List[str] = []

    def handle_starttag(self, tag, attrs):
        attr_dict = {k.lower(): (v or "") for k, v in attrs}
        tag_lower = tag.lower()

        if tag_lower == "a" and "href" in attr_dict:
            self.raw_candidates.append(attr_dict["href"])

        if tag_lower == "meta" and attr_dict.get("http-equiv", "").lower() == "refresh":
            content = attr_dict.get("content", "")
            m = re.search(r"url\s*=\s*(?:['\"]([^'\"]+)['\"]|([^;\s'\"]+))", content, re.IGNORECASE)
            if m:
                u = m.group(1) or m.group(2)
                if u:
                    self.raw_candidates.append(u.strip())

        for k, v in attr_dict.items():
            if k.startswith("data-download") or k in ("data-href", "data-url", "data-src", "data-link"):
                if v:
                    self.raw_candidates.append(v.strip())
