# Installation Guide

This application runs **inside the Python 2.7 interpreter that ships with
ArcGIS Desktop 10.8.2**, because it depends on ArcPy and on a Microsoft Access
personal geodatabase (`.mdb`) driver that only exists on Windows.

---

## 1. Prerequisites

| Component                | Requirement                                          |
|--------------------------|------------------------------------------------------|
| Operating system         | Windows 10 or 11 (64-bit)                            |
| ArcGIS Desktop           | **10.8.2** with the ArcPy site-package               |
| Python                   | **2.7** (installed by ArcGIS, e.g. `C:\Python27\ArcGIS10.8`) |
| MS Access driver         | Microsoft Access Database Engine (for `.mdb`)        |
| Fonts                    | A Cyrillic TrueType font (Arial is present by default)|

> Find your ArcGIS Python with: open *Python (ArcGIS)* from the Start menu, or
> check `C:\Python27\ArcGIS10.8\python.exe`. All commands below assume that
> path - adjust if yours differs.

## 2. Get the application

Copy the `chust_land_balance` folder anywhere on disk, e.g.
`D:\Tools\chust_land_balance`. No build step is required.

## 3. Install the optional Python libraries

All third-party libraries are **optional** - the program still runs without
them, just with fewer output formats (see the table in USER_MANUAL.md). To get
every format (recommended):

```bat
"C:\Python27\ArcGIS10.8\Scripts\pip.exe" install -r requirements.txt
```

If `pip` is missing from the ArcGIS Python:

```bat
"C:\Python27\ArcGIS10.8\python.exe" -m ensurepip
"C:\Python27\ArcGIS10.8\python.exe" -m pip install --upgrade "pip<21"
```

What each library adds:

| Library     | Adds                                                      | If absent |
|-------------|-----------------------------------------------------------|-----------|
| `xlrd`      | Read `.xls` contour statements directly                   | Falls back to ArcPy `ExcelToTable` |
| `openpyxl`  | Read `.xlsx`; write styled `.xlsx` reports                | Falls back to `xlwt` `.xls` |
| `xlwt`      | Write legacy `.xls` reports                               | Excel report skipped |
| `reportlab` | Write the **PDF** balance report with Cyrillic fonts      | Use the HTML report (print to PDF) |
| `py7zr`     | Extract `.7z` massif archives in-process                  | Install 7-Zip; app shells out to `7z.exe` |

For `.7z` archives without `py7zr`, install **7-Zip** from
<https://www.7-zip.org/> (the app looks for `7z.exe` on `PATH` and in
`C:\Program Files\7-Zip\`).

## 4. (Optional) Provide the layout template

To produce maps for massifs that have **no** own `.mxd`, place a template named
`templates\land_balance_layout.mxd` (see `templates/README.md`). Massifs that
ship their own `.mxd` use it directly and need no template.

## 5. Verify the installation

```bat
cd /d D:\Tools\chust_land_balance

:: should print the Python 2.7 / ArcGIS banner without errors
"C:\Python27\ArcGIS10.8\python.exe" -c "import arcpy, sys; print(sys.version)"

:: scan a data folder without processing - lists the massifs found
"C:\Python27\ArcGIS10.8\python.exe" run_cli.py --root "D:\Chust\Massivlar" --scan-only
```

If the scan lists your massifs with `mdb=yes`, you are ready. Launch the GUI:

```bat
"C:\Python27\ArcGIS10.8\python.exe" run_gui.py
```

## 6. (Optional) Desktop shortcut

Create a shortcut whose *Target* is:

```
"C:\Python27\ArcGIS10.8\python.exe" "D:\Tools\chust_land_balance\run_gui.py"
```

and whose *Start in* is `D:\Tools\chust_land_balance`. Name it
“Chust Land Balance”.

## Troubleshooting

| Symptom                                             | Cause / fix |
|-----------------------------------------------------|-------------|
| `arcpy is not available`                            | You launched the app with a non-ArcGIS Python. Use `C:\Python27\ArcGIS10.8\python.exe`. |
| `Geodatabase (.mdb) not found`                      | The massif folder has only a `.7z`/`.zip`; install py7zr/7-Zip or extract it manually. |
| PDF report text shows boxes instead of Cyrillic     | No Cyrillic TTF found; install/keep Arial, or use the HTML report. |
| `Layer not found: HISOBLASH_QAYDNOMASI`             | The `.mdb` lacks the calculation statement; add the candidate name in `config/settings.py → LAYERS`. |
| Map export skipped                                  | No massif `.mxd` and no template; add `templates\land_balance_layout.mxd`. |
| Excel report skipped                                | Install `openpyxl` (or `xlwt`). |
