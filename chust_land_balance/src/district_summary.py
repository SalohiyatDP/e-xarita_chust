# -*- coding: utf-8 -*-
"""
District-level summary.

Aggregates a collection of per-massif :class:`MassifBalance` objects into:

* a district grand total (all 18 massifs combined), and
* a per-massif overview table (one row per massif with headline figures), and
* a district SVOD table (the eight statutory categories summed across massifs).

Pure Python - no arcpy.
"""

from __future__ import unicode_literals

from config import land_categories as lc
from config import settings
from src.balance_calculator import MassifBalance, _recompute_keep_measured
from src.balance_model import LandBalance
from src.table_builder import Table, _balance_columns


def aggregate_district(massif_balances, logger=None):
    """Combine several :class:`MassifBalance` into one district MassifBalance."""
    district = MassifBalance(
        massif_name=settings.DISTRICT_NAME,
        massif_name_cyr=settings.DISTRICT_NAME_CYR,
        massif_code="ALL")

    for mb in massif_balances:
        district.total.add(mb.total)
        for key in district.by_category:
            district.by_category[key].add(mb.by_category[key])
        district.parcel_count += mb.parcel_count
        district.farm_count += mb.farm_count
        district.parcels.extend(mb.parcels)

    for cat_balance in district.by_category.values():
        _recompute_keep_measured(cat_balance)
    _recompute_keep_measured(district.total)

    if logger:
        h = district.headline()
        logger.info("District total: %.2f ha across %d massif(s), "
                    "%d parcels, %d farms.",
                    h["total_area"], len(massif_balances),
                    district.parcel_count, district.farm_count)
    return district


def build_overview_table(massif_balances):
    """One row per massif with the headline figures (district overview)."""
    columns = [
        {"key": "code", "label": u"Код", "group": "", "kind": "txt"},
        {"key": "name", "label": u"Массив", "group": "", "kind": "txt"},
        {"key": "total_area", "label": u"Умумий майдон", "group": "", "kind": "num"},
        {"key": "agricultural_total", "label": u"Қ/х ерлари", "group": "", "kind": "num"},
        {"key": "irrigated", "label": u"Суғориладиган", "group": "", "kind": "num"},
        {"key": "gardens", "label": u"Боғлар", "group": "", "kind": "num"},
        {"key": "vineyards", "label": u"Токзорлар", "group": "", "kind": "num"},
        {"key": "mulberry", "label": u"Тутзорлар", "group": "", "kind": "num"},
        {"key": "pastures", "label": u"Яйловлар", "group": "", "kind": "num"},
        {"key": "nonagri_total", "label": u"Қ/х да фойдаланилмайдиган", "group": "", "kind": "num"},
        {"key": "farms", "label": u"Хўжаликлар", "group": "", "kind": "txt"},
    ]
    rows = []
    for mb in massif_balances:
        h = mb.headline()
        rows.append({
            "code": mb.massif_code or "",
            "name": mb.massif_name_cyr or mb.massif_name,
            "total_area": h["total_area"],
            "agricultural_total": h["agricultural_total"],
            "irrigated": h["irrigated"],
            "gardens": h["gardens"],
            "vineyards": h["vineyards"],
            "mulberry": h["mulberry"],
            "pastures": h["pastures"],
            "nonagri_total": h["nonagri_total"],
            "farms": mb.farm_count,
        })
    # district total row
    district = aggregate_district(massif_balances)
    h = district.headline()
    rows.append({
        "code": "",
        "name": u"ТУМАН ЖАМИ",
        "total_area": h["total_area"],
        "agricultural_total": h["agricultural_total"],
        "irrigated": h["irrigated"],
        "gardens": h["gardens"],
        "vineyards": h["vineyards"],
        "mulberry": h["mulberry"],
        "pastures": h["pastures"],
        "nonagri_total": h["nonagri_total"],
        "farms": district.farm_count,
    })

    return Table(title=u"%s бўйича ер балансининг умумий жадвали"
                 % settings.DISTRICT_NAME_CYR,
                 subtitle=u"Массивлар кесимида",
                 columns=columns, rows=rows)


def build_district_svod(district_balance):
    """District-level SVOD (eight categories summed across all massifs)."""
    columns = [
        {"key": "no", "label": u"№", "group": "", "kind": "txt"},
        {"key": "category", "label": u"Ер фондининг кичик тоифалари", "group": "", "kind": "txt"},
    ] + _balance_columns()

    rows = []
    grand = district_balance.total.rounded()
    grow = {"no": u"", "category": u"Туман жами"}
    grow.update(grand)
    rows.append(grow)
    for roman, key, _latin, cyr in lc.MAIN_CATEGORIES:
        bal = district_balance.by_category[key].rounded()
        row = {"no": roman, "category": cyr}
        row.update(bal)
        rows.append(row)

    return Table(title=u"%s %s ер баланси (свод)"
                 % (settings.REGION_NAME_CYR, settings.DISTRICT_NAME_CYR),
                 subtitle=u"Барча массивлар бўйича жами",
                 columns=columns, rows=rows)
