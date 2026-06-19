# -*- coding: utf-8 -*-
"""
Global configuration for the Chust District Electronic Land Balance system.

This module is intentionally free of any ``arcpy`` import so that it can be
loaded both inside the ArcGIS Desktop 10.8.2 (Python 2.7) runtime and inside a
plain CPython interpreter used for unit testing.

All user tunable values live here.  Nothing in the rest of the code base should
hard-code a path, a layer name or a colour - it should read it from this file.
"""

from __future__ import unicode_literals

import os


# ---------------------------------------------------------------------------
# Project / administrative identity
# ---------------------------------------------------------------------------

PROJECT_NAME = "Chust District Electronic Land Balance"
REGION_NAME = "Namangan viloyati"          # Namangan Region
DISTRICT_NAME = "Chust tumani"             # Chust District
# Cyrillic forms used on the official cartographic output.
REGION_NAME_CYR = "Наманган вилояти"
DISTRICT_NAME_CYR = "Чуст тумани"

# Cadastre block prefix used in this district (see sample cadastre numbers
# 11:13:xxxxxxxxx).  Kept configurable because neighbouring districts differ.
CADASTRE_PREFIX = "11:13"


# ---------------------------------------------------------------------------
# Geodatabase layer (feature class / table) names
#
# The ``LAYERS`` dictionary maps a *logical* name (used everywhere in the code)
# to a list of *candidate* physical names.  Different massif geodatabases were
# produced by different operators over several years, so the same logical layer
# may appear under a Latin or a Cyrillic name, with or without a trailing
# ``_1``.  ``geodatabase_reader.resolve_layer`` walks this candidate list and
# returns the first feature class that actually exists in the .mdb.
# ---------------------------------------------------------------------------

LAYERS = {
    # Outer district / massif boundary (polygon)
    "HUDUD_CHEGARASI_MAYDONLI": [
        "HUDUD_CHEGARASI_MAYDONLI",
        "HUDUD_CHEGARASI_MAYDONLI_1",
        "Худуд_чегараси_майдонли",
    ],
    # Contour numbers - polygon / point / line variants
    "KONTURLAR_RAQAMI_MAYDONLI": [
        "KONTURLAR_RAQAMI_MAYDONLI_1",
        "KONTURLAR_RAQAMI_MAYDONLI",
    ],
    "KONTURLAR_RAQAMI_NUQTALI": [
        "KONTURLAR_RAQAMLI_NUQTALI",
        "KONTURLAR_RAQAMI_NUQTALI_1",
        "KONTURLAR_RAQAMI_NUQTALI",
    ],
    "KONTURLAR_RAQAMI_CHIZIQLI": [
        "KONTURLAR_RAQAMI_CHIZIQLI_1",
        "KONTURLAR_RAQAMI_CHIZIQLI",
    ],
    # Agricultural land use polygons
    "QISHLOQ_XOJALIGI_YERLARI_MAYDONLI": [
        "QISHLOQ_XO\u2018JALIGI_YERLARI_MAYDONLI_1",
        "QISHLOQ_XOJALIGI_YERLARI_MAYDONLI_1",
        "QISHLOQ_XOJALIGI_YERLARI_MAYDONLI",
    ],
    # Non-agricultural land use polygons
    "NOQISHLOQ_XOJALIGI_YERLARI_MAYDONLI": [
        "NOQISHLOQ_XO\u2018JALIGI_YERLARI_MAYDONLI_1",
        "NOQISHLOQ_XOJALIGI_YERLARI_MAYDONLI_1",
        "NOQISHLOQ_XOJALIGI_YERLARI_MAYDONLI",
    ],
    # Lands not used in agriculture (polygon)
    "QX_DA_FOYDALANILMAYDIGAN_YERLAR_MAYDONLI": [
        "Q_X_DA_FOYDALANILMAYDIGAN_YERLAR_MAYDONLI",
        "Q_X_DA_FOYDALANILMAYDIGAN_YERLAR_MAYDONLI_1",
    ],
    # Hydrography polygons (water fund)
    "GIDROGRAFIYA_MAYDONLI": [
        "GIDROGRAFIYA_VA_GIDROINSHOOTLAR_MAYDONLI_1",
        "GIDROGRAFIYA_VA_GIDROINSHOOTLAR_MAYDONLI",
    ],
    # Roads polygons
    "YOLLAR_MAYDONLI": [
        "YO\u2018LLAR_VA_YO\u2018L_INSHOOTLARI_MAYDONLI_1",
        "YOLLAR_VA_YOL_INSHOOTLARI_MAYDONLI_1",
    ],
    # The authoritative per-contour calculation statement (HISOBLASH_QAYDNOMASI)
    "HISOBLASH_QAYDNOMASI": [
        "Хисоблаш_кайдномаси",
        "HISOBLASH_QAYDNOMASI",
        "Hisoblash_qaydnomasi",
    ],
    # Farmer boundary inventory
    "FERMER_CHEGARA_XATLOV": [
        "Фермер_чегара_хатлов",
        "FERMER_CHEGARA_XATLOV",
        "Fermer_chegara_xatlov",
    ],
    # Inventory land type
    "XATLOV_ER_TURI": [
        "Хатлов_ер_тури",
        "XATLOV_ER_TURI",
        "Xatlov_er_turi",
    ],
}

# Logical names of the layers the requirement document explicitly asks us to
# detect.  Used by the scanner to report a per-massif "readiness" status.
REQUIRED_LAYERS = [
    "HUDUD_CHEGARASI_MAYDONLI",
    "KONTURLAR_RAQAMI_MAYDONLI",
    "QISHLOQ_XOJALIGI_YERLARI_MAYDONLI",
    "HISOBLASH_QAYDNOMASI",
    "FERMER_CHEGARA_XATLOV",
    "XATLOV_ER_TURI",
]

# The single layer that, if missing, makes a massif impossible to balance.
PRIMARY_DATA_LAYER = "HISOBLASH_QAYDNOMASI"


# ---------------------------------------------------------------------------
# Field names inside HISOBLASH_QAYDNOMASI (the calculation statement)
#
# Mapped logical -> list of candidate physical field names.  Resolved lazily by
# geodatabase_reader so that minor schema drift between massifs is tolerated.
# ---------------------------------------------------------------------------

QAYDNOMA_FIELDS = {
    "contour": ["Kontur_raqami", "KONTUR_RAQAMI", "kontur_raqami"],
    "user_name": ["Yerdan_foydalanuvchilar_nomi", "Ердан_фойдаланувчи_номи"],
    "direction": ["Yonalishi", "YONALISHI"],
    "irrigated_total": ["Jami_Sugoriladigan_yerlar"],
    "irrigated_arable": ["Sugoriladigan_xaydalma_yerlar"],
    "sowable_area": ["Ekin_ekishga_yaroqli_maydon"],
    "meliorative_bad": ["Meliorativ_xolati_yomonlashgan"],
    "reused_area": ["Qayta_foydalanishga_kiritilgan_maydon"],
    "newly_developed": ["Yangidan_uzlashtirilgan_maydon"],
    "withdrawn": ["Foydalanishdan_chiqqan_yerlar"],
    "gardens_total": ["Bogzorlar_jami"],
    "gardens_cond_irrigated": ["Shartli_sugoriladigan_boglar"],
    "vineyards_total": ["Tokzorlar_jami"],
    "vineyards_cond_irrigated": ["Shartli_sugoriladigan_Tokzorlar"],
    "greenhouse_total": ["Issiqxona_jami"],
    "greenhouse_in_use": ["Foydalanilayotgan"],
    "greenhouse_abandoned": ["Qarovsiz_qoldirilgan"],
    "mulberry": ["Tutzorlar"],
    "poplar": ["Terakzorlar"],
    "fruit_nursery": ["Mevali_kuchatzorlar"],
    "other_perennial": ["Boshqa_kop_yillik_daraxtzorlar"],
    "virgin_irrigated": ["Sugoriladigan_buz_yerlar"],
}


# ---------------------------------------------------------------------------
# Massif registry - all 18 massifs of Chust district.
#
# ``code``   - zero padded ordinal used to build deterministic folder / file
#              prefixes (001 .. 018).
# ``key``    - ASCII slug used internally and inside log file names.
# ``name``   - Latin display name.
# ``name_cyr`` - Cyrillic display name shown on the official map sheet.
# ``aliases`` - extra spellings that may appear in folder names on disk, so the
#               scanner can match a folder even when the operator used a
#               different transliteration.
# ---------------------------------------------------------------------------

MASSIFS = [
    {"code": "001", "key": "varzik",      "name": "Varzik",       "name_cyr": "Варзик",      "aliases": ["варзик", "varzik massivi", "варзик массиви"]},
    {"code": "002", "key": "damobod",     "name": "Damobod",      "name_cyr": "Дамобод",     "aliases": ["дамобод"]},
    {"code": "003", "key": "karkidon",    "name": "Karkidon",     "name_cyr": "Каркидон",    "aliases": ["каркидон", "qorqidon"]},
    {"code": "004", "key": "mashal",      "name": "Mashal",       "name_cyr": "Машъал",      "aliases": ["машъал", "mashal", "машал"]},
    {"code": "005", "key": "uzbekistan",  "name": "Uzbekistan",   "name_cyr": "Ўзбекистон",  "aliases": ["ўзбекистон", "узбекистан", "ozbekiston"]},
    {"code": "006", "key": "govasoy",     "name": "Govasoy",      "name_cyr": "Ғовасой",     "aliases": ["ғовасой", "говасой"]},
    {"code": "007", "key": "baymok",      "name": "Baymok",       "name_cyr": "Баймоқ",      "aliases": ["баймоқ", "баймок"]},
    {"code": "008", "key": "sabzazor",    "name": "Sabzazor",     "name_cyr": "Сабзазор",    "aliases": ["сабзазор"]},
    {"code": "009", "key": "chustiy",     "name": "Chustiy",      "name_cyr": "Чустий",      "aliases": ["чустий", "chustiy"]},
    {"code": "010", "key": "norxojaev",   "name": "Norxojaev",    "name_cyr": "Норхожаев",   "aliases": ["норхожаев", "norxo'jaev", "norxojayev"]},
    {"code": "011", "key": "navoiy",      "name": "Navoiy",       "name_cyr": "Навоий",      "aliases": ["навоий", "a.navoiy", "а.навоий", "navoi"]},
    {"code": "012", "key": "chust_ijara", "name": "Chust Ijara",  "name_cyr": "Чуст Ижара",  "aliases": ["чуст ижара", "chust ijara", "ижара"]},
    {"code": "013", "key": "axcha",       "name": "Axcha",        "name_cyr": "Ахча",        "aliases": ["ахча", "axcha", "akcha"]},
    {"code": "014", "key": "olmos",       "name": "Olmos",        "name_cyr": "Олмос",       "aliases": ["олмос", "olmos"]},
    {"code": "015", "key": "galaba",      "name": "Galaba",       "name_cyr": "Ғалаба",      "aliases": ["ғалаба", "галаба", "g'alaba"]},
    {"code": "016", "key": "zarafshon",   "name": "Zarafshon",    "name_cyr": "Зарафшон",    "aliases": ["зарафшон", "zarafshon"]},
    {"code": "017", "key": "nurafshon",   "name": "Nurafshon",    "name_cyr": "Нурафшон",    "aliases": ["нурафшон", "nurafshon"]},
    {"code": "018", "key": "anorchilik",  "name": "Anorchilik",   "name_cyr": "Анорчилик",   "aliases": ["анорчилик", "anorchilik"]},
]


# ---------------------------------------------------------------------------
# Output / export configuration
# ---------------------------------------------------------------------------

# Default name of the folder created under each massif folder to receive output.
OUTPUT_DIRNAME = "BALANCE_OUTPUT"
# Default name of the district level output folder created under the root.
DISTRICT_OUTPUT_DIRNAME = "DISTRICT_SUMMARY"
LOG_DIRNAME = "logs"

# Export resolutions / quality.
PDF_MAP_DPI = 300
JPG_PREVIEW_DPI = 96
JPG_PREVIEW_WIDTH = 1200      # px - long edge of the preview image

# Map layout template (an .mxd authored to look like the A.Navoiy sample).  If
# the file is not found next to the package the map_layout module falls back to
# building a layout from scratch in code.
DEFAULT_MXD_TEMPLATE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "templates",
    "land_balance_layout.mxd",
)

# Coordinate system the maps are produced in.  Chust district lies in UTM zone
# 42N / WGS84 (EPSG:32642).  Used only when a layer is missing its own SR.
DEFAULT_WKID = 32642

# Rounding used throughout the balance (hectares, 2 decimals as in the sample).
AREA_DECIMALS = 2

# Square metres in one hectare - all GIS areas are stored in m2 and converted.
SQM_PER_HA = 10000.0


# ---------------------------------------------------------------------------
# Standalone (non-agricultural) polygon layers.
#
# The per-contour calculation statement (HISOBLASH_QAYDNOMASI) describes the
# *agricultural* land use of farm contours.  Land that is not part of a farm
# contour - the water fund, public roads, settlements, industrial sites - lives
# in its own polygon feature classes.  ``NONAGRI_LAYERS`` tells the data joiner
# which extra layers to pull in, which statutory category each belongs to, and a
# fallback balance column for polygons whose ``semantika`` cannot be classified.
#
# tuple = (logical_layer_name, default_main_category, fallback_balance_leaf)
# ---------------------------------------------------------------------------
NONAGRI_LAYERS = [
    ("GIDROGRAFIYA_MAYDONLI",                   "water_fund",   "canals"),
    ("YOLLAR_MAYDONLI",                          "industrial",   "roads"),
    ("NOQISHLOQ_XOJALIGI_YERLARI_MAYDONLI",     "settlement",   "other_land"),
    ("QX_DA_FOYDALANILMAYDIGAN_YERLAR_MAYDONLI", "state_reserve","other_land"),
]

# When True the joiner also derives an intra-contour "non-agricultural residual"
# (boundary area minus the sum of agricultural components) and books it under
# the agricultural category's "other_land" column - this reproduces the large
# "qishloq xojaligida foydalanilmaydigan yerlar" figure seen inside category I
# of the official A.Navoiy sheet.
BOOK_AGRI_RESIDUAL = True
