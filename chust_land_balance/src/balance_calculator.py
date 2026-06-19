# -*- coding: utf-8 -*-
"""
Land balance calculator.

Consumes a list of :class:`~src.balance_model.ParcelRecord` (produced by the
data joiner) and rolls them up into:

* a per-statutory-category subtotal (I .. VIII), and
* a grand massif total ("Массив жами").

It also derives the explicitly requested headline figures (total area,
irrigated, rainfed, gardens, vineyards, mulberry, pastures, hayfields,
agricultural, non-agricultural, water fund, historical-cultural, industrial,
state reserve) and performs reconciliation checks.

Pure Python - no arcpy.
"""

from __future__ import unicode_literals

from config import land_categories as lc
from config import settings
from src.balance_model import LandBalance


class MassifBalance(object):
    """Aggregated balance result for a single massif."""

    def __init__(self, massif_name="", massif_name_cyr="", massif_code=None):
        self.massif_name = massif_name
        self.massif_name_cyr = massif_name_cyr
        self.massif_code = massif_code
        self.parcels = []                       # list[ParcelRecord]
        self.total = LandBalance()              # "Массив жами"
        # category key -> LandBalance subtotal
        self.by_category = dict(
            (key, LandBalance()) for (_r, key, _l, _c) in lc.MAIN_CATEGORIES)
        self.farm_count = 0                     # distinct farmer enterprises
        self.parcel_count = 0
        self.warnings = []

    # -- requested headline figures (all hectares, rounded) -------------
    def headline(self):
        t = self.total.rounded()
        return {
            "total_area": t["total_area"],
            "irrigated": t["irrigated"],
            "rainfed": t["rainfed"],
            "gardens": t["gardens"],
            "vineyards": t["vineyards"],
            "mulberry": t["mulberry"],
            "pastures": t["pastures"],
            "hayfields": t["hayfields"],
            "agricultural_total": t["agricultural_total"],
            "nonagri_total": t["nonagri_total"],
            "water_fund": self.by_category["water_fund"].rounded()["total_area"],
            "historical": self.by_category["historical"].rounded()["total_area"],
            "industrial": self.by_category["industrial"].rounded()["total_area"],
            "state_reserve": self.by_category["state_reserve"].rounded()["total_area"],
            "forest_fund": self.by_category["forest_fund"].rounded()["total_area"],
            "settlement": self.by_category["settlement"].rounded()["total_area"],
            "nature_protection": self.by_category["nature_protection"].rounded()["total_area"],
            "agricultural_category": self.by_category["agricultural"].rounded()["total_area"],
        }


def calculate(parcels, massif_name="", massif_name_cyr="", massif_code=None,
              logger=None):
    """Aggregate ``parcels`` into a :class:`MassifBalance`.

    Each parcel's balance is first made internally consistent
    (``recompute_totals`` is *not* re-run here because the joiner already set
    measured totals; we accumulate the stored values as-is, then recompute the
    category and massif aggregates from the accumulated leaves).
    """
    result = MassifBalance(massif_name, massif_name_cyr, massif_code)
    result.parcels = list(parcels)
    result.parcel_count = len(parcels)

    distinct_users = set()
    for p in parcels:
        cat = p.main_category if p.main_category in result.by_category else "agricultural"
        result.by_category[cat].add(p.balance)
        result.total.add(p.balance)
        if p.user_name:
            distinct_users.add(p.user_name.strip().lower())

    result.farm_count = len(distinct_users)

    # Recompute every aggregate from the accumulated leaf values so the printed
    # totals are guaranteed self-consistent.
    for cat_balance in result.by_category.values():
        _recompute_keep_measured(cat_balance)
    _recompute_keep_measured(result.total)

    # Reconciliation: sum of category totals should equal the massif total.
    cat_sum = sum(result.by_category[k]["total_area"]
                  for k in result.by_category)
    grand = result.total["total_area"]
    if abs(cat_sum - grand) > 0.5:   # > 0.5 ha is worth a warning
        msg = ("Category totals (%.2f ha) do not match massif total (%.2f ha) "
               "- difference %.2f ha." % (cat_sum, grand, cat_sum - grand))
        result.warnings.append(msg)
        if logger:
            logger.warning(msg)

    if logger:
        h = result.headline()
        logger.info("Balance for %s: total=%.2f ha, agri=%.2f ha, "
                    "irrigated=%.2f ha, parcels=%d, farms=%d",
                    massif_name or massif_code, h["total_area"],
                    h["agricultural_total"], h["irrigated"],
                    result.parcel_count, result.farm_count)
    return result


def _recompute_keep_measured(balance):
    """Recompute aggregate columns but preserve a measured total_area.

    When the accumulated ``total_area`` (sum of measured parcel totals) is
    larger than the computed component total, keep the measured one - it is the
    surveyed truth.  Otherwise use the computed sum.
    """
    measured_total = balance["total_area"]
    # Recompute the chain except the final total override.
    for total_key, parts in lc.AGG_FORMULAS:
        if total_key == "total_area":
            computed = sum(balance.get(p, 0.0) for p in parts)
            # Prefer the larger of measured vs computed (measured includes
            # residual "other" already accounted in parcel balances).
            balance["total_area"] = max(measured_total, computed) \
                if measured_total else computed
        else:
            balance[total_key] = sum(balance.get(p, 0.0) for p in parts)
    return balance
