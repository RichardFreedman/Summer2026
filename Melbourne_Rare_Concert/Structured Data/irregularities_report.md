# Irregularities Report — Concert Program Extraction

Covering source files `UDC20260028-1` through `UDC20260028-91`.
**388 events extracted from 89 files.** Two files produced no events (see §1).

---

## 1. Files producing no event records

| File | Reason |
|---|---|
| **29** | OCR output is almost entirely garbled Japanese character noise. Appears to be material relating to a Museum of Musical Instruments, but no recoverable event, date, venue, or programme. |
| **26** | Not a concert programme. It is a Musashino Academia Musicae 50th-anniversary institutional history/prospectus (1929–1979): campus descriptions, degree structures, faculty lists, concert-hall and pipe-organ specifications. It describes the *types* of concerts the Academia runs but gives no specific dated programmes. |

---

## 2. Duplicate scans — same printed programme appearing twice

In each case both copies were retained as separate records (flagged in `additional_information`) so that the source-file provenance is not lost.

| Files | Event | Note |
|---|---|---|
| **13 / 15** | Metropolitan Liedertafel, 6 November 1889 | The concert number OCR'd differently in each copy: "195th" in file 13, "135th" in file 15. Same date, same programme, same personnel. |
| **35 / 36** | Royal Metropolitan Liedertafel, 178th Concert, 20 April 1896 | Identical programme, identical personnel. |
| **39 / 40** | Metropolitan Liedertafel, 190th Concert, 25 March 1889 | Identical programme; both copies badly garble the Administrator's name on the title page. |
| **75 / 76** | Musical Society of Victoria, 48th Programme, 26 September 1896 | Same date and performers, but the Haydn quartet opus number differs between copies: "Op. 76 No. 3" vs "No. 5". |

Note: **files 62 and 63** share several madrigals with **file 55**, but these are genuinely distinct concerts (different dates, different halls/programmes) drawing on the Society's standing repertoire — not duplicates.

---

## 3. Date problems

| File | Issue |
|---|---|
| **25** | Title page reads "29th February, 1899"; the closing page reads "29th February, 1892". **1899 was not a leap year**, so 1892 is almost certainly correct. Recorded with both readings noted. |
| **1, 2, 3, 4** | Wednesday concert dated "January 10, 1967" in the printed brochure, but contextually falls in the 1967–68 season and should almost certainly read 1968. |
| **30** | Così fan tutte cast list is organised by performance date (26th/27th/28th), but the **month is not legible** in the OCR. Only the day-of-month survives. |
| **63** | Title page year is partly illegible: "Anno Domini 190_". A Friday in December of an unspecified year in the 1900s. |
| **90** | A. M. Henderson lecture-recital brochure is **entirely undated** — promotional material listing available programmes rather than a specific engagement. |

---

## 4. Composer / work attribution errors in the printed source

| File | Issue |
|---|---|
| **2** | Brahms Cello Sonata printed as **Op. 88**; the correct opus is **Op. 99**. |
| **44** | The song "Nirvana" is printed under **Verdi** in the programme list, but is by **S. Adams**. |
| **83** | The string quartet's composer is not legible / not stated. |
| **39 / 40** | "Ukrainischer Kosakentanz" attributed to "S. Noshowski" — likely a corruption of **Moniuszko** or **Noskowski**; not resolvable from the scan. |

---

## 5. Names badly corrupted by OCR (recorded with `[uncertain]` markers)

Recurring across the 19th-century Melbourne programmes: composer surnames set in decorative type consistently mis-OCR'd. Examples flagged in the data include:

- File 25: "Roschat" (→ Koschat), "Gand-Clüsser", "ceterner" (→ possibly Kreutzer)
- File 34: "S. Kenhall", "Ganz", "J. C. Grimshaw", "Stockley", "Kuntze"
- File 35/36: "Mohring" (Hymn to the Night)
- File 43: "Bigar" → **Elgar** (The Pipes of Pan)
- File 50: "Fower" → **Cowen** (What Might Have Been)
- File 59/60: "Bechsnitt", "Eiler Jensen"
- File 39/40: The Administrator of the Government's name renders as "Sir Elm. C. Robinson" — unrecoverable.

Member/chorus rosters throughout the Liedertafel programmes are heavily corrupted (names, initials, and admission years run together). These were **not transcribed into the data**, since they are personnel lists rather than programme content, and the corruption rate is too high for reliable extraction.

---

## 6. Content the sources explicitly omit

These are gaps in the *original printed programmes*, not extraction failures:

- **"Group Concerts"** — nearly every Musashino Academia Musicae seasonal brochure carries the note that these programmes are *"not included in this booklet"* for reasons of space.
- **"Graduate Students' Recitals"** — likewise omitted with the same explicit note (files 19, 22, and others).
- **File 72** — Musical Society of Victoria programme, October 1899: one page has substantial garbled/missing content; the programme is only partially recoverable.
- **File 52** (Asian Youth Music Camp, Hong Kong 1979) — the booklet gives programme *notes* on individual works and a *schedule* of concerts, but does not map works to specific concert dates. Works are therefore listed at the festival level rather than per concert.
- **File 51** (Pacific Contemporary Music Festival II) and **files 61 / 68** (Michigan May Festivals) — extensive composer biographies and analytical notes were condensed rather than transcribed.

---

## 7. Treatment decisions worth flagging

- **All repertoire is itemised.** Every identifiable piece is now its own `Performance` object — **2,494 in total** across 458 sections. Only **22 sections** remain without performances: these are cases where the printed source itself gives no titles (e.g. "Works by Brown, Cage, Ichiyanagi, Penderecki… (specific titles not given)", "Music of the shakuhachi from the classical to the modern repertoire"). Their descriptive text is retained in the section's `additional_information`.
- **Composers live in event `credits`, keyed by piece.** Composer attributions are recorded at event level as `"Composer (<piece title>)": "<composer>"` — **2,425 entries**. Where two composers share one programme item (e.g. a paired "(a)/(b)" song group), each gets its own keyed credit. Arrangers and orchestrators are preserved inside the credit value (e.g. `"F. Schubert, arr. Plumpton"`, `"M. Mussorgsky (orch. Ravel)"`), as are life-dates and OCR-uncertainty markers.
- **Parsing hazards encountered.** Three classes of title caused mis-splitting during restructuring and were specifically guarded against: titles containing apostrophes ("Er ist's"), titles containing an internal dash (Debussy's prelude *General Lavine – eccentric*), and segments where a performer rather than a composer preceded the dash. Composer candidates are rejected if they carry opus/catalogue markers, a title of address (Mr./Miss/Herr…), or exceed 60 characters.
- **Multi-date tours as single events.** Where a brochure lists one programme performed across many cities on many dates (e.g. the 1977 Musashino West Germany tour, the 1976 Wind Ensemble tour), these are recorded as a **single tour event** with the date range and venue list in the relevant fields, rather than as a dozen near-identical records.
- **`lyrics_transcript`** holds a *summary of the narrative or sense* of a text, not verbatim transcription, wherever the source printed song words.
- **`_source_file`** is retained on every record for provenance tracing back to the OCR files.

---

## 8. Corpus composition (for context)

| Location | Events |
|---|---:|
| Tokyo, Japan (Musashino Academia Musicae, Cross Talk) | 277 |
| Melbourne, Australia (Liedertafel societies, Musical Society of Victoria) | 71 |
| Ann Arbor, Michigan, USA (University of Michigan May Festivals) | 12 |
| Hong Kong (Asian Youth Music Camp 1979) | 6 |
| London, England (RCM, Queen's Hall, Albert Hall, Covent Garden) | 8 |
| Seoul & Daegu, South Korea | 4 |
| Manila, Philippines | 3 |
| Oberammergau, Germany | 2 |
| Los Angeles / Lausanne / Paris / Madang / Glasgow | 1 each |

Date range: **1889 – 1990**.
