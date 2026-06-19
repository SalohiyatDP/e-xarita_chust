# User Manual

Chust District Electronic Land Balance Mapping System — day-to-day usage.

---

## 1. Prepare the data folder

Put one folder per massif under a single **root folder**. The folder name may be
anything that contains the massif's name or its ordinal code; the scanner
matches it to the registry automatically.

```
D:\Chust\Massivlar\
├─ 001 Varzik\
│  ├─ VARZIK MASSIVI.mdb        (personal geodatabase - required)
│  ├─ VARZIK MASSIVI.mxd        (map document - optional but recommended)
│  ├─ VARZIK MASSIVI.lyr        (symbology - optional)
│  └─ Varzik.xls                (contour statement - optional)
├─ 002 Damobod\
│  └─ …
├─ 011 Navoiy\
│  └─ Navoiy.7z                 (archive - auto-extracted)
└─ …
```

Recognised massifs and their codes:

| Code | Massif | Code | Massif | Code | Massif |
|------|--------|------|--------|------|--------|
| 001 | Varzik | 007 | Baymok | 013 | Axcha |
| 002 | Damobod | 008 | Sabzazor | 014 | Olmos |
| 003 | Karkidon | 009 | Chustiy | 015 | Galaba |
| 004 | Mashal | 010 | Norxojaev | 016 | Zarafshon |
| 005 | Uzbekistan | 011 | Navoiy | 017 | Nurafshon |
| 006 | Govasoy | 012 | Chust Ijara | 018 | Anorchilik |

Only the **`.mdb`** is strictly required to compute a balance. Everything else
is optional and improves the output (the `.mxd`/`.lyr` give the official map
styling; the `.xls` adds legal-document and cadastre details).

## 2. Using the GUI

Launch with `run_gui.py` (see INSTALL.md). Then:

1. **Browse** to the root folder. The list fills with every detected massif and
   a *Status* column: `ready`, `archive will be extracted` or `no .mdb`.
2. Choose options:
   * **Xarita (PDF/JPG)** — build the cartographic map + preview.
   * **Hisobot (PDF/Excel/HTML)** — build the balance report.
   * **Faqat tanlanganlar / Selected only** — process just the rows you
     highlighted (otherwise all massifs are processed).
3. Click **Ishga tushirish / Run**. The progress bar and log update live; the
   UI stays responsive (processing runs on a background thread).
4. When finished, use **Ko'rish / Preview** to open the latest JPG/HTML, or
   **Natija papkasi / Open output** to open the output folder.

## 3. Using the command line

```bat
:: whole district
run_cli.py --root "D:\Chust\Massivlar"

:: just list what was found
run_cli.py --root "D:\Chust\Massivlar" --scan-only

:: one massif by key or code
run_cli.py --root "D:\Chust\Massivlar" --massif varzik
run_cli.py --root "D:\Chust\Massivlar" --massif 001

:: reports only, no map (faster)
run_cli.py --root "D:\Chust\Massivlar" --no-map
```

(Prefix each with `"C:\Python27\ArcGIS10.8\python.exe"`.)

## 4. Where the output goes

For each massif, a `BALANCE_OUTPUT` folder is created inside the massif folder:

```
001 Varzik\BALANCE_OUTPUT\
├─ 001_varzik_MAP.pdf         electronic land-balance map (300 dpi)
├─ 001_varzik_PREVIEW.jpg     JPG preview of the map
├─ 001_varzik_REPORT.pdf      balance report (SVOD + detail)
├─ 001_varzik_REPORT.xlsx     same report as Excel
└─ 001_varzik_REPORT.html     same report as HTML (always produced)
```

The **district summary** is written under the root folder:

```
DISTRICT_SUMMARY\
├─ DISTRICT_SUMMARY.html / .xlsx / .pdf   per-massif overview + district SVOD
```

Logs are written to `<root>\logs\` with a timestamp.

### Output formats matrix

| Output | Always | Needs |
|--------|:------:|-------|
| HTML report / summary | ✓ | — |
| Excel report (`.xlsx`) | | `openpyxl` (or `xlwt` → `.xls`) |
| PDF report | | `reportlab` + a Cyrillic TTF |
| PDF map + JPG preview | | ArcPy + a massif `.mxd` or the template |

## 5. The land balance — what is computed

The report has two tables, exactly like the A.Navoiy reference:

* **SVOD (summary)** — one `Массив жами` row plus the eight statutory
  categories (I Agricultural, II Settlement, III Industry/Transport, IV
  Nature-protection, V Historical-cultural, VI Forest fund, VII Water fund,
  VIII State reserve).
* **Detail** — one row per contour with the land user, cadastre number, legal
  document and the full balance breakdown.

Balance columns and how totals are derived (in hectares):

```
crops_total        = irrigated + rainfed            (greenhouse is "of which")
perennial_total    = gardens + vineyards + mulberry + fruit_nursery
agricultural_total = crops_total + perennial_total + virgin + hayfields + pastures
forest_total       = shelterbelts + poplar
water_total        = rivers + natural_lakes + artificial_lakes + canals
nonagri_total      = water_total + roads + buildings + yards + other_land
total_area         = agricultural_total + meliorative + forest_total + shrubs + nonagri_total
```

These formulas reproduce the published A.Navoiy massif totals exactly and are
covered by automated tests.

## 6. How GIS land use maps to balance columns

Agricultural figures come from the **calculation statement**
(`HISOBLASH_QAYDNOMASI`) per contour. Land that is not in a farm contour (water,
roads, settlements, unused land) is taken from dedicated polygon layers and
classified by its `semantika` label, e.g.:

| `semantika` (GIS)                       | Balance column |
|-----------------------------------------|----------------|
| SUG'ORILADIGAN XAYDALADIGAN YERLAR      | irrigated |
| MEVALI VA SITRUSLI BOG'LAR              | gardens |
| UZUMZORLAR                              | vineyards |
| TUTZOR (MAYDONLI)                       | mulberry |
| YAYLOV                                  | pastures |
| BETONLANGAN KANALLAR                    | canals |
| BASSEYNLAR                              | artificial lakes |
| QURILISHLAR                             | buildings |

The full mapping lives in `config/land_categories.py → SEMANTIKA_TO_BALANCE`.
Add or change a row there if a massif uses a label that is not yet recognised —
no other code changes are needed.

### Tuning the statutory category

A parcel's category (I…VIII) is inferred from the land-user name / semantika
keywords (`config/.../data_joiner.py → _CATEGORY_KEYWORDS`). The non-agricultural
layers' default categories are set in `config/settings.py → NONAGRI_LAYERS`.
Adjust these to match local cadastre practice.

## 7. Tips & good practice

* Keep each massif's `.mxd` next to its `.mdb` — the map then comes out already
  styled to the official sheet and the app only refreshes text and extent.
* Re-running a massif overwrites its previous output files.
* If a massif fails, the batch continues; check `logs\` and the *Status* column
  for the reason (missing `.mdb`, missing primary layer, etc.).
* Always reconcile the generated totals against the authoritative cadastre
  before official submission — the footnote on the SVOD reports the
  agricultural-category "unused land" figure to help cross-check.

## 8. Frequently seen messages

| Message | Meaning |
|---------|---------|
| `Qatlam topilmadi / layer missing: …` | An optional layer is absent; processing continues. |
| `Asosiy qatlam yo'q / primary layer missing` | `HISOBLASH_QAYDNOMASI` is absent — cannot balance this massif. |
| `Xarita yaratilmadi / map export skipped` | No `.mxd`/template; reports are still produced. |
| `Category totals do not match massif total` | A reconciliation warning > 0.5 ha; inspect the data. |
