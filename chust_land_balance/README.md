# Chust District Electronic Land Balance Mapping System

Production-ready desktop GIS application that automatically generates **official
electronic land-balance maps and reports** for every massif of **Chust District,
Namangan Region, Uzbekistan**, in the exact form of the *A.Navoiy* reference
sheet.

It reads each massif's ESRI **personal geodatabase (`.mdb`)**, joins it with the
**contour-statement Excel (`.xls`)**, computes the statutory Uzbekistan land
balance, and produces a **PDF map**, a **PDF/Excel/HTML balance report** and a
**JPG preview** per massif, plus a **district-wide summary**.

---

## Capabilities

* **Automatic massif discovery** - scans a root folder, recognises all 18
  Chust massifs (Varzik … Anorchilik) by folder name and locates their
  `.mdb` / `.mxd` / `.lyr` / `.xls` files; auto-extracts `.7z` / `.zip`.
* **Tolerant geodatabase reader** - resolves the required layers
  (`HUDUD_CHEGARASI_MAYDONLI`, `KONTURLAR_RAQAMI_MAYDONLI`,
  `QISHLOQ_XOJALIGI_YERLARI_MAYDONLI`, `HISOBLASH_QAYDNOMASI`,
  `FERMER_CHEGARA_XATLOV`, `XATLOV_ER_TURI`) even when their physical names
  drift between Latin / Cyrillic spellings.
* **GIS + Excel join** by contour number and cadastre code.
* **Official land balance** - total area, irrigated, rainfed, gardens,
  vineyards, mulberry, pastures, hayfields, agricultural land, non-agricultural
  land, water fund, historical-cultural, industrial, state-reserve land, etc.,
  rolled up into the eight statutory categories (I…VIII).
* **Cartographic layout** identical to the A.Navoiy sample: title, legend,
  north arrow, scale, coordinate grid, contour labels, land-category colours,
  summary-statistics panel.
* **Exports**: PDF map · PDF/Excel/HTML report · JPG preview · district summary.
* **Desktop GUI** (Tkinter) and a **command-line** batch runner.
* **Logging**, graceful handling of missing files, and per-massif isolation so
  one bad data set never aborts the batch.

## Quick start

```bat
:: 1. Install optional libraries into the ArcGIS Python (one time)
"C:\Python27\ArcGIS10.8\Scripts\pip.exe" install -r requirements.txt

:: 2a. Launch the GUI
"C:\Python27\ArcGIS10.8\python.exe" run_gui.py

:: 2b. …or run the whole district from the command line
"C:\Python27\ArcGIS10.8\python.exe" run_cli.py --root "D:\Chust\Massivlar"
```

See **INSTALL.md** for setup and **USER_MANUAL.md** for day-to-day use, the
expected folder layout, output formats and how to tune the land-use mapping.

## Architecture

```
chust_land_balance/
├─ run_gui.py                 # GUI launcher
├─ run_cli.py                 # command-line batch runner
├─ requirements.txt
├─ config/
│  ├─ settings.py             # paths, layer/field names, 18-massif registry
│  └─ land_categories.py      # 8 statutory categories, balance columns,
│                             #   aggregation formulas, semantika→category map,
│                             #   cartographic colours
├─ src/
│  ├─ logger.py               # console + file logging
│  ├─ massif_scanner.py       # discover massif data sets
│  ├─ geodatabase_reader.py   # ArcPy .mdb reader (layer/field resolution)
│  ├─ excel_reader.py         # xls/xlsx reader (xlrd/openpyxl/ArcPy)
│  ├─ data_joiner.py          # GIS + Excel → ParcelRecord list
│  ├─ balance_model.py        # LandBalance, ParcelRecord
│  ├─ balance_calculator.py   # MassifBalance aggregation
│  ├─ table_builder.py        # official SVOD + detailed tables
│  ├─ district_summary.py     # district overview + SVOD
│  ├─ map_layout.py           # ArcPy layout build + PDF/JPG export
│  ├─ report_generator.py     # PDF/Excel/HTML report writer
│  ├─ processor.py            # orchestration (massif + district)
│  └─ gui/app.py              # Tkinter application
├─ templates/                 # shared layout .mxd (see templates/README.md)
└─ tests/                     # unit tests (pytest)
```

## Requirements

* Windows 10 / 11
* ArcGIS Desktop **10.8.2** with ArcPy (Python **2.7**)
* Optional Python libraries in `requirements.txt` (all degrade gracefully)

## Tests

```bat
"C:\Python27\ArcGIS10.8\Scripts\pip.exe" install pytest
"C:\Python27\ArcGIS10.8\python.exe" -m pytest tests -q
```

The pure-logic modules (model, calculator, scanner, tables, classification)
are interpreter-agnostic and also run under Python 3 for CI.

## License / attribution

Internal tool for the Chust district cadastre office. The balance arithmetic
reproduces the official A.Navoiy reference workbook; verify outputs against the
authoritative cadastre before submission.
