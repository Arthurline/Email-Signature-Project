from src.signatures import SIGNATURE_TEMPLATES, personalize, sanitize_html


def test_personalize_handles_null_and_list_fields():
    user = {
        "displayName": "Ada Lovelace",
        "jobTitle": None,
        "businessPhones": ["+1 555 0100", "+1 555 0101"],
        "mail": "ada@contoso.com",
    }
    out = personalize(SIGNATURE_TEMPLATES["standard"], user)
    assert "Ada Lovelace" in out
    assert "+1 555 0100, +1 555 0101" in out
    assert "{{" not in out


def test_personalize_escapes_user_data():
    out = personalize("<p>{{displayName}}</p>", {"displayName": "<img src=x onerror=alert(1)>"})
    assert "<img" not in out
    assert "&lt;img" in out


def test_personalize_tolerates_spaces_and_unknown_placeholders():
    assert personalize("<p>{{ mail }}{{nope}}</p>", {"mail": "a@b.com"}) == "<p>a@b.com</p>"


def test_sanitize_strips_scripts_handlers_and_js_urls():
    dirty = (
        '<p style="color:red" onclick="x()">Hi</p><script>alert(1)</script>'
        '<a href="javascript:alert(1)">x</a><img src="https://example.com/l.png" alt="logo">'
    )
    clean = sanitize_html(dirty)
    assert "script" not in clean
    assert "onclick" not in clean
    assert "javascript:" not in clean
    assert 'style="color:red"' in clean
    assert 'src="https://example.com/l.png"' in clean
