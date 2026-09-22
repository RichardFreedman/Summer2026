"""Print the HTML transcription to PDF with Playwright's Chromium."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

src, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    pg.goto(src.as_uri())
    pg.wait_for_load_state("networkidle")
    pg.evaluate("document.fonts.ready")
    pg.pdf(path=str(out), prefer_css_page_size=True, print_background=True, margin={"top": "0", "right": "0", "bottom": "0", "left": "0"})
    b.close()
print("wrote", out)
