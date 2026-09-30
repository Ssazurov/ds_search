from src.gar_ingest.paths import resolve_content_path


def test_exact_path(tmp_path):
    md = tmp_path / "a.md"; md.write_text("x")
    assert resolve_content_path(tmp_path / "a.json", md) == md


def test_fallback_sibling_md(tmp_path):
    md = tmp_path / "a.md"; md.write_text("x")
    assert resolve_content_path(tmp_path / "a.json", "/app/data/raw/x/a.md") == md


def test_fallback_sibling_pdf(tmp_path):
    pdf = tmp_path / "a.pdf"; pdf.write_bytes(b"x")
    assert resolve_content_path(tmp_path / "a.json", "/nope/a.pdf") == pdf
