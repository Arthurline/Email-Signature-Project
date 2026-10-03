"""Signature templates, per-user personalisation and HTML sanitising."""

import html
import re

import nh3

PLACEHOLDER_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")

ALLOWED_TAGS = {
    "a", "b", "br", "div", "em", "font", "hr", "i", "img", "p", "span",
    "strong", "table", "tbody", "td", "th", "thead", "tr", "u",
}
ALLOWED_ATTRIBUTES = {
    "*": {"style", "align", "class"},
    "a": {"href", "title"},
    "font": {"color", "face", "size"},
    "img": {"src", "alt", "width", "height"},
    "table": {"border", "cellpadding", "cellspacing", "width"},
    "td": {"colspan", "rowspan", "width", "valign"},
    "th": {"colspan", "rowspan", "width", "valign"},
}

SIGNATURE_TEMPLATES = {
    "standard": """\
<div style="font-family: Arial, sans-serif; font-size: 10pt; color: #333;">
  <p><strong>{{displayName}}</strong><br>
  {{jobTitle}} | {{department}}<br>
  {{officeLocation}}</p>
  <p>Phone: {{businessPhones}}<br>
  Email: {{mail}}</p>
</div>""",
    "minimal": """\
<div style="font-family: Arial, sans-serif; font-size: 10pt;">
  <strong>{{displayName}}</strong> &middot; {{jobTitle}}<br>
  {{mail}}
</div>""",
}


def sanitize_html(markup: str) -> str:
    """Strip scripts, event handlers and unsafe URLs from signature HTML."""
    return nh3.clean(
        markup,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes={"http", "https", "mailto", "tel"},
    )


def _field(user: dict, name: str) -> str:
    # Graph returns null for unset fields, so .get(name, "") is not enough.
    value = user.get(name)
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(v) for v in value if v)
    return str(value)


def personalize(template: str, user: dict) -> str:
    """Fill ``{{field}}`` placeholders with escaped values from a Graph user.

    Unknown placeholders become empty strings. The result is sanitised.
    """
    filled = PLACEHOLDER_RE.sub(lambda m: html.escape(_field(user, m.group(1))), template)
    return sanitize_html(filled)
