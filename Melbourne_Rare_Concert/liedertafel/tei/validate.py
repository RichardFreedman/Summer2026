"""Validate a TEI file against the tei_all RelaxNG schema and report every error."""
import sys
from pathlib import Path
from lxml import etree

here = Path(__file__).parent
schema = etree.RelaxNG(etree.parse(str(here / "schema" / "tei_all.rng")))
target = Path(sys.argv[1]) if len(sys.argv) > 1 else here / "UDC20260028-21.xml"
doc = etree.parse(str(target))
ok = schema.validate(doc)
for e in schema.error_log:
    print(f"{target.name}:{e.line}: {e.message}")
print("VALID" if ok else f"INVALID ({len(schema.error_log)} errors)")
sys.exit(0 if ok else 1)
