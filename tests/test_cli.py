"""CLI routing tests."""

import pytest

from latex_llm_cleaner.cli import main


@pytest.mark.parametrize("suffix,hint", [(".pdf", "Marker"), (".docx", "pandoc")])
def test_removed_formats_point_elsewhere(tmp_path, capsys, suffix, hint):
    f = tmp_path / f"doc{suffix}"
    f.write_bytes(b"not really")
    with pytest.raises(SystemExit) as exc:
        main([str(f)])
    assert exc.value.code == 2
    assert hint in capsys.readouterr().err


def test_tex_to_stdout(tmp_path, capsys):
    f = tmp_path / "main.tex"
    f.write_text("\\newcommand{\\train}{\\mathcal{D}}\nUse $\\train$. % note\n")
    main([str(f)])
    out = capsys.readouterr().out
    assert "\\mathcal{D}" in out
    assert "% note" not in out
