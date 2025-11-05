from inteleria.scraper import download_pages


def test_download_pages_creates_files_and_reports_progress(tmp_path):
    slugs = ["abbess", "galek"]
    html_map = {
        "abbess": "<html>abbess</html>",
        "galek": "<html>galek</html>",
    }

    calls: list[tuple[str, bool, str | None]] = []

    def loader(slug: str) -> str:
        return html_map[slug]

    def progress(slug: str, success: bool, error: str | None) -> None:
        calls.append((slug, success, error))

    output_dir = tmp_path / "pages"

    written = download_pages(slugs, loader, output_dir, progress=progress)

    expected_files = {f"{slug}.html" for slug in slugs}
    assert {path.name for path in written} == expected_files

    for slug in slugs:
        saved = (output_dir / f"{slug}.html").read_text(encoding="utf-8")
        assert saved == html_map[slug]

    assert calls == [("abbess", True, None), ("galek", True, None)]
