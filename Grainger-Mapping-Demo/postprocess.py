"""
Deterministic postprocessor that translates between the intermediary JSON and the final EMu export (to be imported into an EMu system).

Unverified column names are noted here with <brackets> and False in the DEFAULT_CONFIG. They need to be replaced manually. EMu outputs are blocked while unverified columns exist.
To push through EMu while unverified columns exist, pass --allow-unverified. This also appends "DRAFT_" to the start of the file names of the EMu outputs (DO NOT import these, they won't work)

All flagged portions of records are written into a curator_review.csv to be manually reviewed in a spreadsheet. The CSV:
- can only correct single-value fields, not fields with multiple nested subfields in them (those subfields must be corrected indvidually)
- cannot correct untranslatable structural errors (e.g. missing creator attribution)
- has three options for each flagged portion: ACCEPT, REJECT (deleted from the EMu output), and CORRECT (manually replace value in the spreadsheet)

All flagged portions of eParties records are also written into a parties_review.csv that functions the same way as curator_review.csv.

Completed reviews can be passed back into this postprocessor with --corrections PATH --parties-decisions PATH. MAKE SURE to rename the CSVs to something different from their original names(!!!)
"""


from __future__ import annotations

import argparse
import csv
import difflib
import json
import re
import sys
import unicodedata
from collections import OrderedDict, defaultdict
from hashlib import sha256
from pathlib import Path

HERE = Path(__file__).parent
SCHEMA_PATH = HERE / "bundle" / "output_schema.json"
MAPPING_PATH = HERE / "bundle" / "field_mapping.json"


# False=unverified field name, placeholder name in <> brackets
DEFAULT_CONFIG = {
    "ecatalogue": {
        "object_number":  ["<primary object/registration number field>", False],
        "title_proper":   ["TitMainTitle", True],
        "uniform_title":  ["TitObjectTitle", False],
        "object_type":    ["<object name/category field>", False],
        "edition":        ["<edition field>", False],
        "place":          ["<publication place field>", False],
        "publisher_text": ["<publisher field>", False],
        "date_text":      ["ProDateProduced", False],
        "date_from":      ["ProDateProducedFrom", False],
        "date_to":        ["ProDateProducedTo", False],
        "extent":         ["PhyDescription", False],
        "dim_category":   ["DimCategory_tab", False],
        "dim_value":      ["DimValue_tab", False],
        "dim_unit":       ["DimUnit_tab", False],
        "series_title":   ["<series title field>", False],
        "series_number":  ["<series number field>", False],
        "num_kind":       ["NumOtherKind_tab", True],
        "num_number":     ["NumOtherNumber_tab", True],
        "note_type":      ["NteType_tab", True],
        "note_text":      ["NotNotes", True],
        "language":       ["LanLanguage_tab", False],
        "creator_ref":    ["<creator party link column>", False],
        "creator_role":   ["<creator role column>", False],
        "parent_ref":     ["<parent record link column>", False],
        "related_ref":    ["<related records link column>", False],
        "related_kind":   ["<related relation kind column>", False],
    },
    "eparties": {
        "party_type":   ["NamPartyType", True],
        "last_name":    ["NamLast", False],
        "first_name":   ["NamFirst", False],
        "organisation": ["NamOrganisation", False],
        "birth":        ["BioBirthDate", False],
        "death":        ["BioDeathDate", False],
    },
}


# write the above config as a JSON


def init_config(path: Path) -> None:
    """
    Creates emu_columns.json for mapping intermediary records to EMu based on DEFAULT_CONFIG
    """
    cfg = {"_comment": ("Confirm every column with confirmed=false against the museum's EMu data dictionary (client '?' field-help -> Field Information -> Column), then set confirmed=true. "
                        "Import files won't generate while any USED field is unconfirmed (see field_mapping.json)."),
           "modules": {m: {k: {"column": c, "confirmed": conf}
                           for k, (c, conf) in fields.items()}
                       for m, fields in DEFAULT_CONFIG.items()}}
    path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote config template: {path}")


def load_config(path: Path) -> dict:
    """
    loads the config JSON
    """
    if not path.exists():
        sys.exit(f"Config {path} not found. Please run 'python postprocess.py --init-config'")
    return json.loads(path.read_text(encoding="utf-8"))["modules"]


# validate against output_schema.json and dedupe again, just in case (mostly to make sure that this file works in every situation)


def load_records(path: Path) -> tuple[list[dict], list[str]]:
    """
    loads a set of intermediary records and validates them against output_schema.json
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        sys.exit("Input must be a JSON array of intermediate records.")
    problems: list[str] = []
    try:
        import jsonschema
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        validator = jsonschema.validators.validator_for(schema)(schema)
        for err in validator.iter_errors(data):
            loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
            problems.append(f"schema: {loc}: {err.message[:200]}")
    except ImportError:
        problems.append("jsonschema not installed---schema validation SKIPPED")
    return data, problems


def dedupe(records: list[dict]) -> tuple[list[dict], list[str]]:
    """
    Dedupes a set of records, taking the largest (fullest) entry as the one all are deduped to
    """
    best: "OrderedDict[str, dict]" = OrderedDict()
    dropped = []
    for r in records:
        n = r.get("object_number", "")
        if n in best:
            dropped.append(n)
            if len(json.dumps(r)) > len(json.dumps(best[n])):
                best[n] = r
        else:
            best[n] = r
    return list(best.values()), dropped


# Manual review process


def _resolve_path(rec: dict, path: str):
    """translates between the path shown in the manual review CSV and directions for navigating through the JSON"""
    tokens = [t for t in re.split(r"[/.\[\]]+", path.strip()) if t]
    obj = rec
    for i, tok in enumerate(tokens):
        key = int(tok) if tok.isdigit() else tok
        last = i == len(tokens) - 1
        try:
            if last:
                _ = obj[key]          # must exist to be correctable
                return obj, key
            obj = obj[key]
        except (KeyError, IndexError, TypeError):
            return None
    return None


def apply_corrections(records: list[dict], path: Path):
    """applies a completed curator_review.csv (curator_review_done.csv). Returns resolved fields, rejected (deleted) fields, and errors."""
    resolved: set[tuple[str, int]] = set()
    rejects: set[str] = set()
    errors: list[str] = []
    by_num = {r["object_number"]: r for r in records}
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            num = row.get("object_number", "").strip()
            res = (row.get("resolution") or "").strip().lower()
            idx = int(row.get("flag_index") or -1)
            if not num or num not in by_num or not res:
                continue
            if res == "reject":
                rejects.add(num)
            elif res == "accept":
                resolved.add((num, idx))
            elif res == "correct":
                rec = by_num[num]
                hit = _resolve_path(rec, row.get("field_path", ""))
                if hit is None:
                    errors.append(f"{num}: cannot resolve path '{row.get('field_path')}'")
                    continue
                obj, key = hit
                old, new = obj[key], row.get("corrected_value", "")
                if isinstance(old, (list, dict)):
                    errors.append(f"{num}: '{row.get('field_path')}' is a structured "
                                  "field; CSV corrections can only correct single-value fields. "
                                  "Try to correct the nested subfield instead (e.g. related/0/object_number) "
                                  "or reject the record (deleting it from the generated TSV) if there's a genuine structural error, e.g. a missing creator attribution (which can't be expressed in CSV, unfortunately)")
                    continue
                if isinstance(old, bool):
                    new = new.strip().lower() in ("true", "yes", "1")
                elif isinstance(old, int) and new.strip().lstrip("-").isdigit():
                    new = int(new)
                elif isinstance(old, float):
                    try:
                        new = float(new)
                    except ValueError:
                        pass
                obj[key] = new
                resolved.add((num, idx))
            else:
                errors.append(f"{num}: unknown resolution '{res}'")
    return resolved, rejects, errors


# linking sibling entries + parent/child entries (+ orphaned entries)


RE_SIBLING = re.compile(r"^(.*?/.+-\d+)-(\d+)$")


def build_graph(records: list[dict]):
    """
    Analyzes which and how many records in a list are parent/child entries, siblings (entries with the same parent), and orphans (entries without a parent);
    also makes sure each parent/child/sibling link refers to an actual entry
    """
    nums = {r["object_number"] for r in records}
    report = {"sibling_groups": [], "sibling_links": 0, "parents": 0,
              "children": 0, "orphans": [], "xrefs_ok": 0, "xrefs_dangling": []}

    stems = defaultdict(list)
    for r in records:
        if r.get("record_role") == "child" or ":" in r["object_number"]:
            continue
        m = RE_SIBLING.match(r["object_number"])
        if m:
            stems[m.group(1)].append(r)
    for stem in sorted(stems):
        group = stems[stem]
        if len(group) < 2:
            continue
        report["sibling_groups"].append([g["object_number"] for g in group])
        for r in group:
            existing = {(x["relation"], x["object_number"]) for x in r.setdefault("related", [])}
            for other in group:
                if other is r:
                    continue
                link = ("Another edition of", other["object_number"])
                if link not in existing:
                    r["related"].append({"relation": link[0], "object_number": link[1]})
                    report["sibling_links"] += 1

    # Parent/child integrity
    for r in records:
        if r.get("record_role") == "parent":
            report["parents"] += 1
        elif r.get("record_role") == "child":
            report["children"] += 1
            p = r.get("parent_object_number")
            if not p or p not in nums:
                report["orphans"].append(r["object_number"])

    # Cross-references must point at records we actually have
    for r in records:
        for link in r.get("related", []):
            if link["object_number"] in nums:
                report["xrefs_ok"] += 1
            else:
                report["xrefs_dangling"].append(
                    f'{r["object_number"]} -[{link["relation"]}]-> {link["object_number"]}')
    return report


# resolving eParties


def _norm_name(name: str) -> str:
    """
    Normalizes names by lowercasing + removing diacritics and punctuation (e.g. "Bäch, J.S." to "bach js")
    """
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]+", "", s.casefold()).strip()


def _initials(forenames: str) -> str:
    """
    Self-explanatory; doesn't change case
    """
    return "".join(w[0] for w in re.split(r"[ .]+", forenames) if w)


def resolve_parties(records: list[dict], decisions: dict[frozenset, bool]):
    """
    Dedupes creators/publishers into party records. Only creators that are exactly the same are merged (normalized name + party_type). Fuzzy similarities become
    curator candidates in parties_review.csv; a completed decisions file (parties_review_done.csv) merges them on the next run.
    """
    parties: "OrderedDict[tuple, dict]" = OrderedDict()
    for r in records:
        for c in r.get("creators", []):
            key = (_norm_name(c["name"]), c["party_type"])
            p = parties.setdefault(key, {"name": c["name"], "party_type": c["party_type"],
                                         "birth": None, "death": None, "conflicts": []})
            if len(c["name"]) > len(p["name"]):
                p["name"] = c["name"]      # keep fullest spelling
            for k in ("birth", "death"):
                v = c.get(k)
                if v and not p[k]:
                    p[k] = v
                elif v and p[k] and v != p[k]:
                    p["conflicts"].append(f"{k}: {p[k]!r} vs {v!r}")

    # Do creator merges that were approved by parties_review.csv
    if decisions:
        canon: dict[tuple, tuple] = {}
        for key in parties:
            for other in parties:
                if key < other and key[1] == other[1] and \
                        decisions.get(frozenset((key[0], other[0]))):
                    canon[max(key, other, key=lambda k: len(parties[k]["name"]) * -1)] = \
                        min(key, other, key=lambda k: -len(parties[k]["name"]))
        for src, dst in canon.items():
            if src in parties and dst in parties and src != dst:
                s, d = parties.pop(src), parties[dst]
                for k in ("birth", "death"):
                    d[k] = d[k] or s[k]
                d["conflicts"].extend(s["conflicts"])

    # Fuzzy candidates get sent for curator review (same type; similar name or surname match + initials match, e.g. 'Bach, J.S.' vs 'Johann Sebastian Bach').
    keys = sorted(parties)
    candidates = []
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            if a[1] != b[1]:
                continue
            if decisions and frozenset((a[0], b[0])) in decisions:
                continue        # already adjudicated
            na, nb = parties[a]["name"], parties[b]["name"]
            ratio = difflib.SequenceMatcher(None, a[0], b[0]).ratio()
            initials_match = False
            if a[1] == "Person" and "," in na and "," in nb:
                sa, fa = (x.strip() for x in na.split(",", 1))
                sb, fb = (x.strip() for x in nb.split(",", 1))
                initials_match = (_norm_name(sa) == _norm_name(sb)
                                  and (_initials(fa).lower() == _initials(fb).lower()
                                       or _initials(fa).lower().startswith(_initials(fb).lower())
                                       or _initials(fb).lower().startswith(_initials(fa).lower())))
            if ratio >= 0.87 or initials_match:
                candidates.append((na, nb, f"{ratio:.2f}",
                                   "initials" if initials_match else "similarity"))
    return parties, candidates


# column mapping


def _clean(v) -> str:
    """
    does TSV hygiene (everything is a string, tabs and newlines become spaces)
    """
    if v is None:
        return ""
    return re.sub(r"[\t\r\n]+", " ", str(v)).strip()


def map_record(r: dict, col) -> "OrderedDict[str, str]":
    """
    Turns a single record into a row of {EMu column: value} based on emu_columns.json for the TSV; creates grouped tables and etc.
    """
    row: "OrderedDict[str, str]" = OrderedDict()
    row[col("object_number")] = _clean(r["object_number"])
    row[col("title_proper")] = _clean(r["title_proper"])
    ut = r.get("uniform_title")
    row[col("uniform_title")] = _clean(ut and ut.get("text"))
    row[col("object_type")] = _clean(r.get("object_type"))
    row[col("edition")] = _clean(r.get("edition"))
    pub = r.get("publication") or {}
    row[col("place")] = _clean(pub.get("place"))
    row[col("publisher_text")] = _clean(pub.get("publisher"))
    row[col("date_text")] = _clean(pub.get("date_text"))
    row[col("date_from")] = _clean(pub.get("date_from"))
    row[col("date_to")] = _clean(pub.get("date_to"))
    phy = r.get("physical") or {}
    row[col("extent")] = _clean(phy.get("extent"))
    for i, d in enumerate(phy.get("dimensions") or [], 1):
        row[f"{col('dim_category')}({i})"] = _clean(d["DimCategory"])
        row[f"{col('dim_value')}({i})"] = _clean(d["DimValue"])
        row[f"{col('dim_unit')}({i})"] = _clean(d["DimUnit"])
    for i, s in enumerate(r.get("series") or [], 1):
        row[f"{col('series_title')}({i})"] = _clean(s["title"])
        row[f"{col('series_number')}({i})"] = _clean(s.get("number"))
    nums = list(r.get("other_numbers") or [])
    if not any(n["NumOtherKind_tab"] == "Grainger classification" for n in nums):
        nums.insert(0, {"NumOtherKind_tab": "Grainger classification",
                        "NumOtherNumber_tab": r["object_number"]})
    for i, n in enumerate(nums, 1):
        row[f"{col('num_kind')}({i})"] = _clean(n["NumOtherKind_tab"])
        row[f"{col('num_number')}({i})"] = _clean(n["NumOtherNumber_tab"])
    for i, n in enumerate(r.get("notes") or [], 1):
        row[f"{col('note_type')}({i})"] = _clean(n["NteType_tab"])
        row[f"{col('note_text')}({i})"] = _clean(n["NotNotes"])
    for i, lang in enumerate(r.get("languages") or [], 1):
        row[f"{col('language')}({i})"] = _clean(lang)
    for i, c in enumerate(r.get("creators") or [], 1):
        row[f"{col('creator_ref')}({i})"] = _clean(c["name"])
        row[f"{col('creator_role')}({i})"] = _clean(c["role"])
    row[col("parent_ref")] = _clean(r.get("parent_object_number"))
    for i, link in enumerate(r.get("related") or [], 1):
        row[f"{col('related_ref')}({i})"] = _clean(link["object_number"])
        row[f"{col('related_kind')}({i})"] = _clean(link["relation"])
    return row


def write_tsv(path: Path, rows: list["OrderedDict[str, str]"]):
    """
    Writes the TSV based on the union of all records-turned-rows
    """
    headers: list[str] = []
    for row in rows:
        for h in row:
            if h not in headers:
                headers.append(h)
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write("\t".join(headers) + "\n")
        for row in rows:
            f.write("\t".join(row.get(h, "") for h in headers) + "\n")


def main(argv=None):
    """
    Works with CLI by default when argv is None, but can also be called programmatically with main(argv=[CLI args]). 
    Args:
    python postprocess.py 
    records: JSON 
    --config: PATH(default emu_columns.json) 
    --corrections PATH
    --parties-decisions PATH 
    --out PATH(default emu_out) 
    --allow-unverified 
    --init-config
    
    Runflow:
    Parse args > load config > load records > validate & dedupe records > apply corrections > build inter-record relationships > apply parties decisions > build curator_review.csv
    > blocks output if there are unverified columns > outputs ecatalogue_import.tsv & eparties_import.tsv > outputs curator_review.csv & parties_review.csv & run_report.md

    Exit:
    0=all good
    1=records failed validation against output_schema.json
    2=unverified columns present, output TSVs blocked
    """
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("records", nargs="?", help="intermediate records JSON")
    ap.add_argument("--config", default="emu_columns.json", type=Path)
    ap.add_argument("--corrections", type=Path)
    ap.add_argument("--parties-decisions", type=Path)
    ap.add_argument("--out", default="emu_out", type=Path)
    ap.add_argument("--allow-unverified", action="store_true")
    ap.add_argument("--init-config", action="store_true")
    args = ap.parse_args(argv)

    if args.init_config:
        init_config(args.config)
        return 0
    if not args.records:
        ap.error("records JSON required (or --init-config)")

    cfg = load_config(args.config if args.config.is_absolute()
                      else HERE / args.config if (HERE / args.config).exists()
                      else args.config)
    records, problems = load_records(Path(args.records))
    schema_errors = [p for p in problems if p.startswith("schema:")]
    if schema_errors:
        print(f"FATAL: {len(schema_errors)} schema violation(s):", file=sys.stderr)
        for p in schema_errors[:20]:
            print("  " + p, file=sys.stderr)
        return 1
    for p in problems:
        print("WARNING:", p, file=sys.stderr)

    records, dropped_dupes = dedupe(records)

    # Corrections round-trip
    resolved, rejects, corr_errors = (set(), set(), [])
    if args.corrections:
        resolved, rejects, corr_errors = apply_corrections(records, args.corrections)
    records = [r for r in records if r["object_number"] not in rejects]

    graph = build_graph(records)

    decisions: dict[frozenset, bool] = {}
    if args.parties_decisions:
        with args.parties_decisions.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                d = (row.get("merge") or "").strip().lower()
                if d in ("yes", "no"):
                    decisions[frozenset((_norm_name(row["name_a"]),
                                         _norm_name(row["name_b"])))] = (d == "yes")
    parties, party_candidates = resolve_parties(records, decisions)

    # records still carrying unresolved flags are excluded from the TSV
    flagged_rows, blocked_nums = [], set()
    for r in records:
        for i, fl in enumerate(r.get("review_flags") or []):
            if (r["object_number"], i) in resolved:
                continue
            hit = _resolve_path(r, fl.get("field", ""))
            current = "" if hit is None else _clean(hit[0][hit[1]])
            flagged_rows.append({
                "object_number": r["object_number"], "flag_index": i,
                "reason": fl.get("reason", ""), "field_path": fl.get("field", ""),
                "current_value": current, "detail": _clean(fl.get("detail")),
                "source_text": _clean(r.get("source_text"))[:500],
                "resolution": "", "corrected_value": "",
            })
            blocked_nums.add(r["object_number"])
    # Orphaned children (parent number absent from input) are blocked
    by_num = {r["object_number"]: r for r in records}
    for num in graph["orphans"]:
        r = by_num[num]
        flagged_rows.append({
            "object_number": num, "flag_index": -1,
            "reason": "orphaned_child",
            "field_path": "parent_object_number",
            "current_value": _clean(r.get("parent_object_number")),
            "detail": "parent record not present in this input; "
                      "correct the parent number or reject",
            "source_text": _clean(r.get("source_text"))[:500],
            "resolution": "", "corrected_value": "",
        })
        blocked_nums.add(num)
    # A blocked parent blocks its children
    for r in records:
        if r.get("parent_object_number") in blocked_nums:
            blocked_nums.add(r["object_number"])
    importable = [r for r in records if r["object_number"] not in blocked_nums]

    # columns with unverified names are blocked
    def col(module, key):
        return cfg[module][key]["column"]
    used_unconfirmed = sorted(
        f"{m}.{k} -> {v['column']}" for m, fields in cfg.items()
        for k, v in fields.items() if not v["confirmed"])
    gate_blocked = bool(used_unconfirmed) and not args.allow_unverified

    # write the EMu TSV, curator_review.csv, and parties_review.csv
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    prefix = "DRAFT_" if (used_unconfirmed and args.allow_unverified) else ""

    ccol = lambda k: col("ecatalogue", k)
    pcol = lambda k: col("eparties", k)
    if not gate_blocked:
        # parents before children so the loader can attach by number
        ordered = ([r for r in importable if r.get("record_role") != "child"] + [r for r in importable if r.get("record_role") == "child"])
        write_tsv(out / f"{prefix}ecatalogue_import.tsv", [map_record(r, ccol) for r in ordered])
        prow = []
        for key in sorted(parties):
            p = parties[key]
            row = OrderedDict()
            row[pcol("party_type")] = p["party_type"]
            if p["party_type"] == "Person" and "," in p["name"]:
                last, first = (x.strip() for x in p["name"].split(",", 1))
                row[pcol("last_name")], row[pcol("first_name")] = last, first
                row[pcol("organisation")] = ""
            else:
                row[pcol("last_name")] = row[pcol("first_name")] = ""
                row[pcol("organisation")] = p["name"]
            row[pcol("birth")], row[pcol("death")] = _clean(p["birth"]), _clean(p["death"])
            prow.append(row)
        write_tsv(out / f"{prefix}eparties_import.tsv", prow)

    with (out / "curator_review.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["object_number", "flag_index", "reason", "field_path", "current_value", "detail",
                                          "source_text", "resolution", "corrected_value"])
        w.writeheader()
        w.writerows(flagged_rows)

    with (out / "parties_review.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["name_a", "name_b", "similarity", "basis", "merge"])
        for c in party_candidates:
            w.writerow(list(c) + [""])

    conflicts = [f"{parties[k]['name']}: {'; '.join(p['conflicts'])}" for k, p in ((k, parties[k]) for k in sorted(parties)) if p["conflicts"]]
    digest = sha256(Path(args.records).read_bytes()).hexdigest()[:12]
    report = f"""# Post-processor run report

Input: `{args.records}` (sha256 {digest})

| Stage | Result |
|---|---|
| Records loaded | {len(records) + len(rejects)} ({len(dropped_dupes)} duplicate number(s) deduped) |
| Rejected by curator | {len(rejects)} |
| Sibling groups / links added | {len(graph['sibling_groups'])} / {graph['sibling_links']} |
| Parents / children / orphaned children | {graph['parents']} / {graph['children']} / {len(graph['orphans'])} |
| Cross-references ok / dangling | {graph['xrefs_ok']} / {len(graph['xrefs_dangling'])} |
| Distinct parties | {len(parties)} |
| Fuzzy party candidates (curator) | {len(party_candidates)} |
| Party date conflicts | {len(conflicts)} |
| Records blocked by review_flags | {len(blocked_nums)} |
| Records importable | {len(importable)} |
| Unconfirmed 'Verify' columns | {len(used_unconfirmed)} |
| Correction errors | {len(corr_errors)} |

## Blocked / attention
- Orphaned children: {', '.join(graph['orphans']) or 'none'}
- Dangling cross-references: {'; '.join(graph['xrefs_dangling']) or 'none'}
- Party date conflicts: {'; '.join(conflicts) or 'none'}
- Correction errors: {'; '.join(corr_errors) or 'none'}
- Unconfirmed columns: {'; '.join(used_unconfirmed) or 'none'}
"""
    (out / "run_report.md").write_text(report, encoding="utf-8")

    print(f"Records: {len(records)} loaded, {len(importable)} importable, "
          f"{len(blocked_nums)} blocked -> curator_review.csv")
    print(f"Parties: {len(parties)} distinct, {len(party_candidates)} fuzzy candidate(s)")
    print(f"Graph: {len(graph['sibling_groups'])} sibling group(s), "
          f"{graph['parents']} parent(s), {graph['children']} child(ren)")
    if gate_blocked:
        print(f"BLOCKED: {len(used_unconfirmed)} unconfirmed 'Verify' column(s) in config. Confirm them (or use --allow-unverified for DRAFT files).")
        print(f"Reports written to {out}/")
        return 2
    print(f"Output written to {out}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
