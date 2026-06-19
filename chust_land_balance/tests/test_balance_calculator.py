# -*- coding: utf-8 -*-
"""Tests for the land-balance domain model and calculator.

The headline assertions reproduce the published A.Navoiy massif totals,
guaranteeing the official Uzbekistan aggregation formulas are implemented
exactly.
"""

from __future__ import unicode_literals

from src.balance_model import LandBalance, ParcelRecord
from src import balance_calculator as bc


def _navoiy_total_balance():
    b = LandBalance()
    b["irrigated"] = 1149.99
    b["rainfed"] = 7.31
    b["greenhouse"] = 0.0
    b["gardens"] = 25.01
    b["vineyards"] = 2.79
    b["mulberry"] = 25.91
    b["fruit_nursery"] = 0.54
    b["pastures"] = 56.15
    b["meliorative"] = 1.0
    b["shelterbelts"] = 1.22
    b["poplar"] = 0.48
    b["canals"] = 65.63
    b["roads"] = 21.04
    b["buildings"] = 7.16
    b["yards"] = 232.12
    b["other_land"] = 99.53
    b.recompute_totals()
    return b


def test_navoiy_aggregation_formulas():
    r = _navoiy_total_balance().rounded()
    assert r["crops_total"] == 1157.30
    assert r["perennial_total"] == 54.25
    assert r["agricultural_total"] == 1267.70
    assert r["forest_total"] == 1.70
    assert r["water_total"] == 65.63
    assert r["nonagri_total"] == 425.48
    # component total before measured override
    assert abs(r["total_area"] - 1695.88) < 0.01


def test_greenhouse_is_subset_not_added():
    b = LandBalance()
    b["irrigated"] = 100.0
    b["greenhouse"] = 5.0        # "of which" - must not inflate crops_total
    b.recompute_totals()
    assert b.rounded()["crops_total"] == 100.0


def test_set_measured_total_books_residual_to_other():
    b = LandBalance()
    b["irrigated"] = 90.0
    b.recompute_totals()
    b.set_measured_total(100.0)  # 10 ha residual -> other_land
    r = b.rounded()
    assert r["other_land"] == 10.0
    assert r["total_area"] == 100.0
    assert r["nonagri_total"] >= 10.0


def test_add_accumulates_leaves():
    a = LandBalance({"irrigated": 10.0})
    b = LandBalance({"irrigated": 5.0, "gardens": 2.0})
    a.add(b)
    assert a["irrigated"] == 15.0
    assert a["gardens"] == 2.0


def test_calculate_groups_by_category_and_reconciles():
    p_agri = ParcelRecord(contour="1", user_name="FX A",
                          main_category="agricultural")
    p_agri.balance["irrigated"] = 50.0
    p_agri.balance.set_measured_total(55.0)

    p_water = ParcelRecord(contour="2", user_name="Kanal",
                           main_category="water_fund")
    p_water.balance["canals"] = 8.0
    p_water.balance.recompute_totals()
    p_water.balance["total_area"] = 8.0

    mb = bc.calculate([p_agri, p_water], massif_name="Test")
    h = mb.headline()
    # massif total = 55 (agri parcel measured) + 8 (water) = 63
    assert abs(h["total_area"] - 63.0) < 0.01
    assert abs(h["water_fund"] - 8.0) < 0.01
    assert mb.by_category["agricultural"].rounded()["total_area"] == 55.0
    assert mb.farm_count == 2


def test_distinct_farm_count():
    parcels = []
    for i in range(3):
        p = ParcelRecord(contour=str(i), user_name="SAME FARM")
        p.balance["irrigated"] = 1.0
        p.balance.recompute_totals()
        parcels.append(p)
    mb = bc.calculate(parcels, massif_name="T")
    assert mb.farm_count == 1
    assert mb.parcel_count == 3
