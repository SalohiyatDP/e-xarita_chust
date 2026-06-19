# -*- coding: utf-8 -*-
"""
Build the official Uzbekistan land-balance tables as render-ready structures.

Two tables are produced, mirroring the A.Navoiy reference workbook:

* **SVOD** (summary) - one row for the whole massif ("Массив жами") followed by
  the eight statutory categories (I..VIII), columns = the balance breakdown.
* **DETAIL** - one row per parcel/contour with full identity columns plus the
  same balance breakdown.

The output ``Table`` object is a plain data container (title, column
descriptors, list of row dicts) consumed by both the PDF/Excel/HTML report
generator and the ArcPy map-layout table frame.  No arcpy import here.
"""

from __future__ import unicode_literals

from config import land_categories as lc
from config import settings


class Table(object):
    def __init__(self, title="", subtitle="", columns=None, rows=None, footnote=""):
        self.title = title
        self.subtitle = subtitle
        # columns: list of dicts {key, label, group, kind}
        self.columns = columns or []
        # rows: list of dicts keyed by column key
        self.rows = rows or []
        self.footnote = footnote

    def column_keys(self):
        return [c["key"] for c in self.columns]

    def as_matrix(self):
        """Return [[header...], [row...], ...] of plain strings for export."""
        header = [c["label"] for c in self.columns]
        body = []
        for r in self.rows:
            body.append([_fmt(r.get(c["key"], "")) for c in self.columns])
        return [header] + body


def _fmt(value):
    if value is None:
        return ""
    if isinstance(value, float):
        return ("%0.*f" % (settings.AREA_DECIMALS, value)).rstrip()
    return u"%s" % value


def _balance_columns():
    """Column descriptors for every balance column, with header grouping."""
    cols = []
    for c in lc.BALANCE_COLUMNS:
        group = ""
        if c["parent"]:
            parent = lc.BALANCE_COLUMN_BY_KEY[c["parent"]]
            group = parent["cyr"]
        cols.append({
            "key": c["key"],
            "label": c["cyr"],
            "group": group,
            "kind": "num",
        })
    return cols


def _title(massif_balance):
    name = massif_balance.massif_name_cyr or massif_balance.massif_name
    return (u"%s %s %s массивида ердан фойдаланувчиларнинг "
            u"ер майдонлари тўғрисида МАЪЛУМОТ"
            % (settings.REGION_NAME_CYR, settings.DISTRICT_NAME_CYR, name))


def build_svod_table(massif_balance):
    """Build the summary (SVOD) table from a :class:`MassifBalance`."""
    columns = [
        {"key": "no", "label": u"№", "group": "", "kind": "txt"},
        {"key": "category", "label": u"Ер фондининг кичик тоифалари",
         "group": "", "kind": "txt"},
    ] + _balance_columns()

    rows = []

    # 1) massif grand total
    grand = massif_balance.total.rounded()
    grand_row = {"no": u"", "category": u"Массив жами"}
    grand_row.update(grand)
    rows.append(grand_row)

    # 2) the eight statutory categories
    for roman, key, _latin, cyr in lc.MAIN_CATEGORIES:
        bal = massif_balance.by_category[key].rounded()
        row = {"no": roman, "category": cyr}
        row.update(bal)
        rows.append(row)

    footnote = _svod_footnote(massif_balance)
    return Table(title=_title(massif_balance),
                 subtitle=u"Свод (ер баланси) жадвали",
                 columns=columns, rows=rows, footnote=footnote)


def _svod_footnote(massif_balance):
    # Mirror the style of the reference sheet footnote about unused agricultural
    # land inside the agricultural category.
    agri = massif_balance.by_category["agricultural"].rounded()
    unused = agri.get("nonagri_total", 0.0)
    if unused:
        name = massif_balance.massif_name_cyr or massif_balance.massif_name
        return (u"* %s массиви Қишлоқ хўжалигига мўлжалланган ерлар тоифасида "
                u"%.1f гектар қишлоқ хўжалигида фойдаланилмайдиган ерлар мавжуд."
                % (name, unused))
    return u""


def build_detail_table(massif_balance):
    """Build the detailed per-parcel table."""
    id_cols = [
        {"key": "no", "label": u"№", "group": "", "kind": "txt"},
        {"key": "subtype", "label": u"Ер фондининг кичик тоифалари", "group": "", "kind": "txt"},
        {"key": "address", "label": u"Ер участкаси жойлашган манзили", "group": "", "kind": "txt"},
        {"key": "user", "label": u"Ердан фойдаланувчилар номи", "group": "", "kind": "txt"},
        {"key": "tax_id", "label": u"СТИР (ПИНФЛ)", "group": "", "kind": "txt"},
        {"key": "cadastre", "label": u"Кадастр рақами", "group": "", "kind": "txt"},
        {"key": "specialization", "label": u"Фойдаланиш ихтисослашуви", "group": "", "kind": "txt"},
    ]
    legal_cols = [
        {"key": "legal_doc", "label": u"Ҳуқуқий ҳужжат номи", "group": u"Ҳуқуқий ҳужжат", "kind": "txt"},
        {"key": "legal_date", "label": u"Санаси", "group": u"Ҳуқуқий ҳужжат", "kind": "txt"},
        {"key": "legal_number", "label": u"Рақами", "group": u"Ҳуқуқий ҳужжат", "kind": "txt"},
        {"key": "contour", "label": u"Контур рақами", "group": "", "kind": "txt"},
    ]
    columns = id_cols + _balance_columns() + legal_cols

    rows = []
    # leading grand-total row
    grand = massif_balance.total.rounded()
    grow = {"no": u"", "subtype": u"Массив жами"}
    grow.update(grand)
    rows.append(grow)

    for idx, p in enumerate(massif_balance.parcels, start=1):
        row = {
            "no": idx,
            "subtype": p.land_subtype or _category_label(p.main_category),
            "address": p.address,
            "user": p.user_name,
            "tax_id": p.tax_id,
            "cadastre": p.cadastre,
            "specialization": p.specialization,
            "legal_doc": p.legal_doc,
            "legal_date": p.legal_date,
            "legal_number": p.legal_number,
            "contour": p.contour,
        }
        row.update(p.balance.rounded())
        rows.append(row)

    return Table(title=_title(massif_balance),
                 subtitle=u"Батафсил (контурлар бўйича) жадвал",
                 columns=columns, rows=rows)


def _category_label(key):
    info = lc.MAIN_CATEGORY_BY_KEY.get(key)
    return info[2] if info else u""
