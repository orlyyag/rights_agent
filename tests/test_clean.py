"""HTML → CleanedDoc — including the table→Markdown R1 fix."""
from __future__ import annotations

from ingest import clean


def _raw(html, **kw):
    return {"pageid": 1, "title": "T", "url": "u", "lang": "he", "lastrevid": 1,
            "html": html, **kw}


def test_strips_edit_nav_infobox_script_style():
    html = """
    <div class="mw-parser-output">
      <script>alert('x')</script>
      <style>body{color:red}</style>
      <div class="mw-editsection">[edit]</div>
      <p>real content here</p>
      <div class="navbox">nav junk</div>
      <div class="infobox">infobox junk</div>
    </div>"""
    out = clean.clean(_raw(html))
    assert any("real content here" in s.text for s in out.sections)
    full = "\n".join(s.text for s in out.sections)
    assert "nav junk" not in full and "infobox junk" not in full
    assert "alert" not in full


def test_sections_break_on_headings():
    html = """
    <div class="mw-parser-output">
      <p>lead paragraph</p>
      <h2>זכאות</h2>
      <p>about eligibility</p>
      <h2>גובה התשלום</h2>
      <p>about amount</p>
    </div>"""
    out = clean.clean(_raw(html))
    headings = [s.heading for s in out.sections]
    assert headings == ["", "זכאות", "גובה התשלום"]
    levels = [s.level for s in out.sections]
    assert levels == [0, 2, 2]
    assert "lead paragraph" in out.sections[0].text
    assert "about eligibility" in out.sections[1].text
    assert "about amount" in out.sections[2].text


def test_table_to_markdown_preserves_numbers():
    """The R1 fix: a benefit-amounts table must come through as a markdown table,
    not flattened prose. The numbers MUST appear verbatim."""
    html = """
    <div class="mw-parser-output">
      <h2>סכומי המענק</h2>
      <table>
        <tr><th>מספר ילדים</th><th>סכום</th></tr>
        <tr><td>ילד ראשון</td><td>2,103 ₪</td></tr>
        <tr><td>תאומים</td><td>10,514 ₪</td></tr>
      </table>
    </div>"""
    out = clean.clean(_raw(html))
    body = "\n".join(s.text for s in out.sections)
    assert "| מספר ילדים | סכום |" in body
    assert "|---|---|" in body
    assert "| ילד ראשון | 2,103 ₪ |" in body
    assert "| תאומים | 10,514 ₪ |" in body


def test_table_with_one_column_falls_back_to_bullets():
    html = """
    <div class="mw-parser-output">
      <table>
        <tr><td>פריט א</td></tr>
        <tr><td>פריט ב</td></tr>
      </table>
    </div>"""
    out = clean.clean(_raw(html))
    body = "\n".join(s.text for s in out.sections)
    assert "• פריט א" in body and "• פריט ב" in body
    assert "|---|" not in body


def test_lists_become_bullets():
    html = """
    <div class="mw-parser-output">
      <ul><li>פריט 1</li><li>פריט 2</li></ul>
    </div>"""
    out = clean.clean(_raw(html))
    body = "\n".join(s.text for s in out.sections)
    assert "• פריט 1" in body and "• פריט 2" in body


def test_meta_fields_round_trip():
    out = clean.clean(_raw("<p>x</p>", pageid=9, title="title", url="https://kz/x",
                            lang="ru", lastrevid=42))
    assert out.pageid == 9 and out.lang == "ru"
    assert out.title == "title" and out.lastrevid == 42


def test_empty_html_does_not_crash():
    out = clean.clean(_raw(""))
    assert out.sections == []
    assert out.total_chars == 0


def test_pipe_inside_cell_is_escaped():
    html = """
    <div class="mw-parser-output">
      <table>
        <tr><th>a</th><th>b</th></tr>
        <tr><td>x|y</td><td>z</td></tr>
      </table>
    </div>"""
    out = clean.clean(_raw(html))
    body = "\n".join(s.text for s in out.sections)
    assert "x\\|y" in body          # escaped — doesn't shatter the markdown row
