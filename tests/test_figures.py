"""Tests for figure summary substitution."""

from pathlib import Path

from latex_llm_cleaner.figures import substitute_figures

OPTS = {"verbose": False, "figure_summary_suffix": "_summary.txt", "encoding": "utf-8"}


def test_figure_env_with_summary(tmp_path):
    (tmp_path / "plot_summary.txt").write_text("A bar chart showing growth.")
    content = (
        "\\begin{figure}[htbp]\n"
        "\\centering\n"
        "\\includegraphics[width=0.8\\textwidth]{plot.png}\n"
        "\\caption{Growth over time}\n"
        "\\label{fig:growth}\n"
        "\\end{figure}"
    )
    result = substitute_figures(content, tmp_path, OPTS)
    assert "% --- Figure summary ---" in result
    assert "\\label{fig:growth}" in result
    assert "% Caption: Growth over time" in result
    assert "A bar chart showing growth." in result
    assert "\\includegraphics" not in result


def test_figure_env_no_summary(tmp_path):
    content = (
        "\\begin{figure}\n"
        "\\includegraphics{missing.png}\n"
        "\\end{figure}"
    )
    result = substitute_figures(content, tmp_path, OPTS)
    assert "\\includegraphics{missing.png}" in result


def test_standalone_includegraphics_with_summary(tmp_path):
    (tmp_path / "diagram_summary.txt").write_text("A class diagram.")
    content = "See \\includegraphics{diagram.pdf} for details."
    result = substitute_figures(content, tmp_path, OPTS)
    assert "% [Image: A class diagram.]" in result
    assert "\\includegraphics" not in result


def test_standalone_no_summary(tmp_path):
    content = "See \\includegraphics{missing.pdf} for details."
    result = substitute_figures(content, tmp_path, OPTS)
    assert "\\includegraphics{missing.pdf}" in result


def test_no_extension_tries_common(tmp_path):
    # Create a .png file and its summary
    (tmp_path / "fig.png").write_text("")
    (tmp_path / "fig_summary.txt").write_text("A figure.")
    content = "\\includegraphics{fig}"
    result = substitute_figures(content, tmp_path, OPTS)
    assert "% [Image: A figure.]" in result


def test_custom_suffix(tmp_path):
    (tmp_path / "plot.desc").write_text("Custom description.")
    content = "\\includegraphics{plot.png}"
    opts = {**OPTS, "figure_summary_suffix": ".desc"}
    result = substitute_figures(content, tmp_path, opts)
    assert "Custom description." in result


def test_subdirectory_image(tmp_path):
    fig_dir = tmp_path / "figs"
    fig_dir.mkdir()
    (fig_dir / "chart_summary.txt").write_text("Revenue chart.")
    content = "\\includegraphics{figs/chart.png}"
    result = substitute_figures(content, tmp_path, OPTS)
    assert "Revenue chart." in result


def test_graphicspath_resolves_summary(tmp_path):
    # Image summary lives in a \graphicspath directory, not next to the doc.
    proj = tmp_path / "Proj1"
    proj.mkdir()
    (proj / "diagram_summary.txt").write_text("An MDP diagram.")
    content = (
        "\\graphicspath{{Proj1/}{proj2/}}\n"
        "\\includegraphics{diagram.png}"
    )
    result = substitute_figures(content, tmp_path, OPTS)
    assert "% [Image: An MDP diagram.]" in result


def test_graphicspath_prepended_to_subdir_arg(tmp_path):
    # LaTeX prepends each graphicspath dir to the argument, so a
    # `figures/x.png` reference can live under `proj2/figures/x.png`.
    figs = tmp_path / "proj2" / "figures"
    figs.mkdir(parents=True)
    (figs / "heatmap_summary.txt").write_text("A heatmap.")
    content = (
        "\\graphicspath{{Proj1/}{proj2/}}\n"
        "\\includegraphics{figures/heatmap.png}"
    )
    result = substitute_figures(content, tmp_path, OPTS)
    assert "% [Image: A heatmap.]" in result


def test_no_graphicspath_unchanged(tmp_path):
    # Without \graphicspath, an image only in a subdir is not found.
    proj = tmp_path / "Proj1"
    proj.mkdir()
    (proj / "diagram_summary.txt").write_text("An MDP diagram.")
    content = "\\includegraphics{diagram.png}"
    result = substitute_figures(content, tmp_path, OPTS)
    assert "\\includegraphics{diagram.png}" in result
