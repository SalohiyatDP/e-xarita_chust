# -*- coding: utf-8 -*-
"""
Join GIS and Excel data into a list of :class:`ParcelRecord`.

The joiner is the bridge between the raw geodatabase / Excel readers and the
balance calculator.  Its job, per massif:

1. Read the per-contour calculation statement (HISOBLASH_QAYDNOMASI) and turn
   every contour into an *agricultural* parcel, mapping the statement's columns
   onto the balance leaves (irrigated, gardens, vineyards, mulberry, ...).
2. Use the polygon geometry area (SHAPE@AREA) as the surveyed total area; the
   residual (area minus agricultural components) is booked under "other_land"
   so the parcel reconciles - exactly as the official sheet keeps a
   "foydalanilmaydigan yerlar" figure inside the agricultural category.
3. Pull the dedicated non-agricultural polygon layers (water fund, roads,
   settlements, unused lands) and turn them into parcels in their statutory
   categories, classifying each polygon by its ``semantika`` label.
4. Enrich every parcel with legal-document / cadastre / address attributes
   looked up from the contour-statement Excel workbook by contour number.

The algorithm is intentionally transparent and config-driven (see
``settings.NONAGRI_LAYERS`` and ``settings.BOOK_AGRI_RESIDUAL``); assumptions are
documented in USER_MANUAL.md so a cadastre specialist can tune them.

This module orchestrates the arcpy-backed readers but contains no arcpy import
itself, so its control flow can be reviewed without ArcGIS.
"""

from __future__ import unicode_literals

from config import settings
from config import land_categories as lc
from src.balance_model import LandBalance, ParcelRecord


# Keywords used to assign a statutory main category from the land-user name /
# the inventory "semantika".  First match wins; default is agricultural.
_CATEGORY_KEYWORDS = [
    ("settlement",     ["маҳалла", "мфй", "аҳоли", "qishloq", "kocha", "aholi"]),
    ("industrial",     ["завод", "корхона", "саноат", "йўл", "электр", "станция",
                        "темир йўл", "mchj", "ао", "аж"]),
    ("water_fund",     ["сув", "канал", "зовур", "дарё", "кўл", "ҳовуз", "сой"]),
    ("historical",     ["тарихий", "ёдгорлик", "маданий", "қабристон", "мозор"]),
    ("forest_fund",    ["ўрмон", "ўрмонзор", "лесхоз"]),
    ("state_reserve",  ["захира", "заҳира", "тарқатилмаган", "резерв"]),
]


def _to_float(value):
    if value in (None, ""):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        try:
            return float(("%s" % value).replace(",", ".").strip())
        except ValueError:
            return 0.0


def classify_main_category(text):
    """Best-effort statutory category from a free-text user/semantika string."""
    if not text:
        return "agricultural"
    low = ("%s" % text).lower()
    for category, words in _CATEGORY_KEYWORDS:
        for w in words:
            if w in low:
                return category
    return "agricultural"


# ---------------------------------------------------------------------------
# Excel enrichment index
# ---------------------------------------------------------------------------
def build_excel_index(excel_sheet):
    """Return {contour_or_cadastre -> {legal_doc/date/number/address/...}}.

    Tolerant to the various A.Navoiy-style column headers.  Indexed by both the
    contour number and the cadastre code where available.
    """
    index = {}
    if not excel_sheet or len(excel_sheet) == 0:
        return index

    col_contour = excel_sheet.find_column("контир рақами", "контур рақами",
                                          "kontur", "контур")
    col_cad = excel_sheet.find_column("кадастр рақами", "кадастр", "kadastr")
    col_addr = excel_sheet.find_column("манзил", "жойлашган манзил")
    col_user = excel_sheet.find_column("фойдаланувчилар номи",
                                       "ердан фойдаланувчилар", "номи")
    col_spec = excel_sheet.find_column("ихтисослашуви", "йўналиши",
                                       "фойдаланиш ихтисослашуви")
    col_doc = excel_sheet.find_column("ҳужжат номи", "ҳуқуқий ҳужжат", "номи")
    col_date = excel_sheet.find_column("санаси", "сана")
    col_num = excel_sheet.find_column("рақами", "ҳужжат рақами")

    for row in excel_sheet.rows:
        info = {
            "address": row.get(col_addr) if col_addr else None,
            "user_name": row.get(col_user) if col_user else None,
            "specialization": row.get(col_spec) if col_spec else None,
            "cadastre": row.get(col_cad) if col_cad else None,
            "legal_doc": row.get(col_doc) if col_doc else None,
            "legal_date": row.get(col_date) if col_date else None,
            "legal_number": row.get(col_num) if col_num else None,
        }
        for key_col in (col_contour, col_cad):
            if key_col:
                kv = row.get(key_col)
                if kv not in (None, ""):
                    index[_norm_key(kv)] = info
    return index


def _norm_key(value):
    return " ".join(("%s" % value).split()).strip().lower()


# ---------------------------------------------------------------------------
# Agricultural parcels from the calculation statement
# ---------------------------------------------------------------------------
def _balance_from_qaydnoma(record):
    """Map one HISOBLASH_QAYDNOMASI row dict onto a LandBalance (leaves only)."""
    b = LandBalance()
    # arable
    irrigated = _to_float(record.get("irrigated_arable"))
    if not irrigated:
        irrigated = _to_float(record.get("sowable_area"))
    b["irrigated"] = irrigated
    # greenhouses (subset of irrigated, reported separately)
    b["greenhouse"] = _to_float(record.get("greenhouse_total"))
    # perennials
    b["gardens"] = _to_float(record.get("gardens_total"))
    b["vineyards"] = _to_float(record.get("vineyards_total"))
    b["mulberry"] = _to_float(record.get("mulberry"))
    b["fruit_nursery"] = (_to_float(record.get("fruit_nursery"))
                          + _to_float(record.get("other_perennial")))
    # forests / shrubs inside the contour
    b["poplar"] = _to_float(record.get("poplar"))
    # virgin
    b["virgin"] = _to_float(record.get("virgin_irrigated"))
    # melioration condition
    b["meliorative"] = _to_float(record.get("meliorative_bad"))
    b.recompute_totals()
    return b


_QAYDNOMA_FIELD_MAP = dict(settings.QAYDNOMA_FIELDS)
_QAYDNOMA_FIELD_MAP["area_ha"] = []   # request geometry area too


def build_agricultural_parcels(reader, excel_index=None, logger=None):
    parcels = []
    excel_index = excel_index or {}
    for rec in reader.read_rows("HISOBLASH_QAYDNOMASI", _QAYDNOMA_FIELD_MAP):
        contour = rec.get("contour")
        user = rec.get("user_name") or ""
        spec = lc.normalize_specialization(rec.get("direction"))
        balance = _balance_from_qaydnoma(rec)

        area_ha = _to_float(rec.get("area_ha"))
        if settings.BOOK_AGRI_RESIDUAL and area_ha:
            balance.set_measured_total(area_ha)
        else:
            balance.recompute_totals()

        info = excel_index.get(_norm_key(contour), {}) if contour is not None else {}
        cat = classify_main_category(user)

        parcels.append(ParcelRecord(
            contour=contour,
            user_name=user,
            specialization=spec or (info.get("specialization") or ""),
            address=info.get("address") or "",
            cadastre=info.get("cadastre") or "",
            main_category=cat,
            land_subtype=_subtype_label(cat),
            legal_doc=info.get("legal_doc") or "",
            legal_date=_fmt_date(info.get("legal_date")),
            legal_number=info.get("legal_number") or "",
            balance=balance,
        ))
    if logger:
        logger.info("Built %d agricultural parcel(s) from the calculation "
                    "statement.", len(parcels))
    return parcels


# ---------------------------------------------------------------------------
# Non-agricultural parcels from dedicated polygon layers
# ---------------------------------------------------------------------------
_NONAGRI_FIELD_MAP = {
    "semantika": ["semantika", "Семантика", "SEMANTIKA"],
    "nomi": ["nomi", "Номи", "name"],
    "area_ha": [],
}


def build_nonagri_parcels(reader, logger=None):
    parcels = []
    for logical, default_cat, fallback_leaf in settings.NONAGRI_LAYERS:
        if not reader.has_layer(logical):
            continue
        count = 0
        for rec in reader.read_rows(logical, _NONAGRI_FIELD_MAP):
            area_ha = _to_float(rec.get("area_ha"))
            if area_ha <= 0:
                continue
            leaf = lc.classify_semantika(rec.get("semantika")) or fallback_leaf
            cat = default_cat
            # refine category from the semantika keyword when possible
            kw_cat = classify_main_category(rec.get("semantika"))
            if kw_cat != "agricultural":
                cat = kw_cat
            balance = LandBalance()
            balance[leaf] = area_ha
            balance.recompute_totals()
            balance["total_area"] = area_ha
            parcels.append(ParcelRecord(
                contour=rec.get("nomi") or "",
                user_name=rec.get("nomi") or "",
                main_category=cat,
                land_subtype=_subtype_label(cat),
                balance=balance,
            ))
            count += 1
        if logger and count:
            logger.info("  layer %s -> %d non-agricultural parcel(s).",
                        logical, count)
    return parcels


def _subtype_label(category_key):
    info = lc.MAIN_CATEGORY_BY_KEY.get(category_key)
    return info[2] if info else u""


def _fmt_date(value):
    if value in (None, ""):
        return ""
    # xlrd may return a float serial or a string; pass strings through.
    if isinstance(value, (int, float)):
        return "%s" % value
    return "%s" % value


# ---------------------------------------------------------------------------
# top-level join
# ---------------------------------------------------------------------------
def join_massif(reader, excel_sheet=None, logger=None):
    """Return the full list of :class:`ParcelRecord` for one massif."""
    excel_index = build_excel_index(excel_sheet) if excel_sheet else {}
    parcels = build_agricultural_parcels(reader, excel_index, logger)
    parcels += build_nonagri_parcels(reader, logger)
    if logger:
        logger.info("Joined massif: %d parcel(s) total.", len(parcels))
    return parcels
