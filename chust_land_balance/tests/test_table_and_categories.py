# -*- coding: utf-8 -*-
"""Tests for category classification, table building and district summary."""

from __future__ import unicode_literals

from config import land_categories as lc
from src.balance_model import LandBalance, ParcelRecord
from src import balance_calculator as bc
from src import table_builder as tb
from src import district_summary as ds
from src import data_joiner as dj


def test_normalize_semantika_handles_apostrophes_and_controls():
    assert lc.normalize_semantika("MEVALI VA SITRUSLI BOG\x18 LAR") == "MEVALI VA SITRUSLI BOGLAR"
    assert lc.normalize_semantika("SUG\u2018ORILADIGAN XAYDALADIGAN YERLAR") == "SUGORILADIGAN XAYDALADIGAN YERLAR"


def test_classify_semantika_maps_to_balance_leaves():
    assert lc.classify_semantika("SUG\u2018ORILADIGAN XAYDALADIGAN YERLAR") == "irrigated"
    assert lc.classify_semantika("MEVALI VA SITRUSLI BOG\x18 LAR") == "gardens"
    assert lc.classify_semantika("UZUMZORLAR") == "vineyards"
    assert lc.classify_semantika("TUTZOR (MAYDONLI)") == "mulberry"
    assert lc.classify_semantika("YAYLOV") == "pastures"
    assert lc.classify_semantika("nonsense xyz") is None


def test_classify_main_category_keywords():
    assert dj.classify_main_category("Истиқлол МФЙ") == "settlement"
    assert dj.classify_main_category("Канал коллектор") == "water_fund"
    assert dj.classify_main_category('"YULDUZ" FX') == "agricultural"
    assert dj.classify_main_category("Темир йўл") == "industrial"


def _sample_massif_balance():
    p = ParcelRecord(contour="100", user_name="FX TEST",
                     specialization="Пахта-ғалла", main_category="agricultural",
                     cadastre="11:13:000000313", legal_doc="Ижара шартномаси",
                     legal_date="17.05.2024", legal_number="281")
    p.balance["irrigated"] = 96.54
    p.balance.set_measured_total(105.0)
    return bc.calculate([p], massif_name="Test", massif_name_cyr="Тест",
                        massif_code="001")


def test_build_svod_table_structure():
    mb = _sample_massif_balance()
    table = tb.build_svod_table(mb)
    # first two columns are number + category, then all balance columns
    assert table.columns[0]["key"] == "no"
    assert table.columns[1]["key"] == "category"
    assert "total_area" in table.column_keys()
    # rows: grand total + 8 categories
    assert len(table.rows) == 1 + len(lc.MAIN_CATEGORIES)
    assert table.rows[0]["category"] == u"Массив жами"
    # grand total area equals the measured 105 ha
    assert abs(table.rows[0]["total_area"] - 105.0) < 0.01


def test_build_detail_table_has_identity_and_balance_columns():
    mb = _sample_massif_balance()
    table = tb.build_detail_table(mb)
    keys = table.column_keys()
    for k in ("no", "user", "cadastre", "contour", "legal_doc", "total_area"):
        assert k in keys
    # leading grand-total row + one parcel row
    assert len(table.rows) == 2
    assert table.rows[1]["user"] == "FX TEST"


def test_district_aggregation_sums_massifs():
    mb1 = _sample_massif_balance()
    mb2 = _sample_massif_balance()
    mb2.massif_code = "002"
    district = ds.aggregate_district([mb1, mb2])
    assert abs(district.headline()["total_area"] - 210.0) < 0.02
    overview = ds.build_overview_table([mb1, mb2])
    # one row per massif + a district total row
    assert len(overview.rows) == 3
    assert overview.rows[-1]["name"] == u"ТУМАН ЖАМИ"


def test_matrix_export_is_string_grid():
    mb = _sample_massif_balance()
    matrix = tb.build_svod_table(mb).as_matrix()
    assert isinstance(matrix, list)
    assert all(isinstance(cell, type(u"")) for cell in matrix[0])
