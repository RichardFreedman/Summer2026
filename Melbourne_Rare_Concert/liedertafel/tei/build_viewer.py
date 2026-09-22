"""Assemble the self-contained viewer: TEI file and facsimile images embedded."""
import base64, json, re
from pathlib import Path

here = Path(__file__).parent
tei = (here / "UDC20260028-21.xml").read_text(encoding="utf-8")
facs = {}
for m in re.finditer(r'<surface xml:id="f(\d+)" n="(\d+)"[^>]*>(.*?)</surface>', tei, re.S):
    n = m.group(2)
    facs[n] = {}
    for g in re.finditer(r'<graphic n="(\w+)" url="([^"]+)"/>', m.group(3)):
        data = base64.b64encode((here / g.group(2)).read_bytes()).decode()
        facs[n][g.group(1)] = f"data:image/jpeg;base64,{data}"
template = (here / "viewer_template.html").read_text(encoding="utf-8")
html = template.replace("{{TEI}}", tei.replace("</script", "&lt;/script")).replace("{{FACS_JSON}}", json.dumps(facs))
out = here / "viewer.html"
out.write_text(html, encoding="utf-8")
print("wrote", out, out.stat().st_size // 1024, "KB")
