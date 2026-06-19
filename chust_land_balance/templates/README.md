# Layout template

Place an ArcMap document named **`land_balance_layout.mxd`** in this folder to
act as the shared cartographic template for massifs that do **not** ship their
own `.mxd`.

The application opens this template (via `arcpy.mapping`), refreshes its layers,
extent and text, and exports the PDF/JPG. The easiest way to create it is to
**Save A Copy** of the supplied *A.Navoiy* sample map document and clear its
data, keeping the layout intact.

## What the template must contain

* One **data frame** (the first one is used).
* A **graticule or measured-grid** on that data frame (Data Frame Properties ▸
  Grids). The app keeps an existing grid; it cannot create one.
* A **legend**, **north arrow** and **scale bar** element.
* **Text elements** whose *Element Name* (Properties ▸ Size and Position ▸
  Element Name) contains one of these tokens, so the app can fill them in:

  | Token in element name | Filled with                                  |
  |-----------------------|----------------------------------------------|
  | `TITLE`               | `<Region> <District> <Massif> ... харитаси`  |
  | `SUBTITLE`            | Project name                                 |
  | `SCALE_TEXT`          | `М 1:NNNNN`                                   |
  | `STATS`               | Land-balance summary block (ha)              |
  | `DATE_TEXT`           | Generation date `dd.mm.yyyy`                 |
  | `AUTHOR_TEXT`         | Project name                                 |

If no template is present **and** a massif has no own `.mxd`, the map step is
skipped with a warning and the balance reports are still produced.

> Tip: set the symbology of the agricultural layer from `ВАРЗИК МАССИВИ.lyr`
> (or the per-massif `.lyr`) so land-category colours match the official sheet.
