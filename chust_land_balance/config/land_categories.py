# -*- coding: utf-8 -*-
"""
Official land-fund classification of the Republic of Uzbekistan.

Two things are described here:

1.  ``MAIN_CATEGORIES`` - the eight statutory categories of the State Land
    Fund (yer fondi toifalari).  These are the rows of the summary (SVOD)
    table, addressed in the requirement document as: Agricultural land,
    Settlement land, Industrial/transport/communication/defence land,
    Nature-protection / health / recreation land, Historical-cultural land,
    Forest-fund land, Water-fund land and State-reserve land.

2.  ``BALANCE_COLUMNS`` - the ordered list of numeric columns that make up the
    land balance for every parcel and every category.  These are the columns of
    the A.Navoiy reference table (umumiy maydon, ekin yerlari -> sugoriladigan /
    lalmi, kop yillik daraxtzorlar -> boglar / tokzorlar / tutzorlar ..., boz
    yerlar, pichanzorlar, yaylovlar, jami qishloq xojaligi yerlari,
    ormonzorlar, butazorlar, qishloq xojaligida foydalanilmaydigan yerlar ->
    suv osti / yollar / binolar / hovli / boshqa).

3.  ``SEMANTIKA_TO_BALANCE`` - maps the free-text ``semantika`` land-use label
    that the GIS polygons carry to the balance column it contributes to.  This
    is what lets the system classify a polygon layer when the per-contour
    statement does not already carry a value.

This module never imports arcpy and is safe to unit-test.
"""

from __future__ import unicode_literals


# ---------------------------------------------------------------------------
# 1.  Eight statutory land-fund categories (rows of the SVOD table)
# ---------------------------------------------------------------------------
# Each entry: (roman, key, latin label, cyrillic label)
MAIN_CATEGORIES = [
    ("I",    "agricultural",      "Agricultural land",
     "Қишлоқ хўжалигига мўлжалланган ерлар"),
    ("II",   "settlement",        "Settlement land",
     "Аҳоли пунктларидаги ерлар"),
    ("III",  "industrial",        "Industry, transport, communication, defence land",
     "Саноат, транспорт, алоқа, мудофаа ва бошқа мақсадларга мўлжалланган ерлар"),
    ("IV",   "nature_protection", "Nature-protection, health, recreation land",
     "Табиатни муҳофаза қилиш, соғломлаштириш ва рекреация мақсадларига мўлжалланган ерлар"),
    ("V",    "historical",        "Historical-cultural land",
     "Тарихий-маданий аҳамиятга молик ерлар"),
    ("VI",   "forest_fund",       "Forest-fund land",
     "Ўрмон фонди ерлари"),
    ("VII",  "water_fund",        "Water-fund land",
     "Сув фонди ерлари"),
    ("VIII", "state_reserve",     "State-reserve land",
     "Давлат захира ерлари"),
]

# Quick lookup: key -> (roman, latin, cyr)
MAIN_CATEGORY_BY_KEY = dict(
    (key, (roman, latin, cyr)) for (roman, key, latin, cyr) in MAIN_CATEGORIES
)


# ---------------------------------------------------------------------------
# 2.  Balance columns (the numeric land-balance breakdown)
# ---------------------------------------------------------------------------
# ``key``       internal identifier used in code and in the LandBalance object.
# ``latin``     short English label (for logs / CSV headers).
# ``cyr``       Cyrillic label exactly as printed on the official table.
# ``parent``    key of the aggregate column this one rolls up into (or None for
#               a top level column).  Used to render the multi-row spanned
#               header and to validate that the parts add up to the whole.
# ``is_total``  True for the aggregate columns that are computed as the sum of
#               their children rather than stored directly.
BALANCE_COLUMNS = [
    # ---- total ----------------------------------------------------------
    {"key": "total_area",        "latin": "Total area",              "cyr": "Умумий майдон",                 "parent": None,            "is_total": True},

    # ---- arable / crop lands -------------------------------------------
    {"key": "crops_total",       "latin": "Crop lands (total)",      "cyr": "Экин ерлари жами",              "parent": None,            "is_total": True},
    {"key": "irrigated",         "latin": "Irrigated",               "cyr": "Суғориладиган",                 "parent": "crops_total",   "is_total": False},
    {"key": "rainfed",           "latin": "Rainfed (lalmi)",         "cyr": "Лалми",                         "parent": "crops_total",   "is_total": False},
    {"key": "greenhouse",        "latin": "Greenhouses",             "cyr": "Шундан иссиқхоналар",           "parent": "crops_total",   "is_total": False},

    # ---- perennial plantations -----------------------------------------
    {"key": "perennial_total",   "latin": "Perennial plantations",   "cyr": "Кўп йиллик дарахтзорлар жами",  "parent": None,            "is_total": True},
    {"key": "gardens",           "latin": "Gardens",                 "cyr": "Боғлар",                        "parent": "perennial_total", "is_total": False},
    {"key": "vineyards",         "latin": "Vineyards",               "cyr": "Токзорлар",                     "parent": "perennial_total", "is_total": False},
    {"key": "mulberry",          "latin": "Mulberry plantations",    "cyr": "Тутзорлар",                     "parent": "perennial_total", "is_total": False},
    {"key": "fruit_nursery",     "latin": "Fruit nurseries / other", "cyr": "Мевали кўчатзорлар ва бошқа",   "parent": "perennial_total", "is_total": False},

    # ---- other agricultural --------------------------------------------
    {"key": "virgin",            "latin": "Virgin (boz) lands",      "cyr": "Бўз ерлар",                     "parent": None,            "is_total": False},
    {"key": "hayfields",         "latin": "Hayfields",               "cyr": "Пичанзорлар",                   "parent": None,            "is_total": False},
    {"key": "pastures",          "latin": "Pastures",                "cyr": "Яйловлар",                      "parent": None,            "is_total": False},

    # ---- AGRICULTURAL LAND SUBTOTAL ------------------------------------
    {"key": "agricultural_total","latin": "Agricultural land total", "cyr": "Жами қишлоқ хўжалиги ерлари",   "parent": None,            "is_total": True},

    # ---- melioration / forests / shrubs --------------------------------
    {"key": "meliorative",       "latin": "Lands under melioration", "cyr": "Мелиоратив қурилиш ҳолатидаги ерлар", "parent": None,      "is_total": False},
    {"key": "forest_total",      "latin": "Forests (total)",         "cyr": "Жами ўрмонзорлар",              "parent": None,            "is_total": True},
    {"key": "shelterbelts",      "latin": "Shelterbelts",            "cyr": "Ихота дарахтзорлар",            "parent": "forest_total",  "is_total": False},
    {"key": "poplar",            "latin": "Poplar groves",           "cyr": "Теракзорлар",                   "parent": "forest_total",  "is_total": False},
    {"key": "shrubs",            "latin": "Shrubs",                  "cyr": "Буталар",                       "parent": None,            "is_total": False},

    # ---- NON-AGRICULTURAL LAND -----------------------------------------
    {"key": "nonagri_total",     "latin": "Non-agricultural (total)", "cyr": "Жами қишлоқ хўжалигида фойдаланилмайдиган ерлар", "parent": None, "is_total": True},
    {"key": "water_total",       "latin": "Under-water lands total",  "cyr": "Жами сув ости ерлари",         "parent": "nonagri_total", "is_total": True},
    {"key": "rivers",            "latin": "Rivers and streams",       "cyr": "Дарё ва сойлар",               "parent": "water_total",   "is_total": False},
    {"key": "lakes_natural",     "latin": "Natural lakes",            "cyr": "Табиий кўллар",                "parent": "water_total",   "is_total": False},
    {"key": "lakes_artificial",  "latin": "Artificial lakes / ponds", "cyr": "Сунъий кўллар ҳовузлар",       "parent": "water_total",   "is_total": False},
    {"key": "canals",            "latin": "Canals, collectors, drains","cyr": "Канал коллектор ва зовурлар",  "parent": "water_total",   "is_total": False},
    {"key": "roads",             "latin": "Roads",                    "cyr": "Йўллар",                       "parent": "nonagri_total", "is_total": False},
    {"key": "buildings",         "latin": "Lands under buildings",    "cyr": "Бино иншоотлар қурилиш ости ерлари", "parent": "nonagri_total", "is_total": False},
    {"key": "yards",             "latin": "Yards, streets, squares",  "cyr": "Ҳовли кўча ва майдонлар",       "parent": "nonagri_total", "is_total": False},
    {"key": "other_land",        "latin": "Other lands",              "cyr": "Бошқа ерлар",                  "parent": "nonagri_total", "is_total": False},
]

# Ordered list of column keys.
BALANCE_KEYS = [c["key"] for c in BALANCE_COLUMNS]
BALANCE_COLUMN_BY_KEY = dict((c["key"], c) for c in BALANCE_COLUMNS)

# Leaf (directly measured) columns - everything that is not a computed total.
LEAF_KEYS = [c["key"] for c in BALANCE_COLUMNS if not c["is_total"]]

# Children of each aggregate column (used only for header rendering).
TOTAL_CHILDREN = {}
for _c in BALANCE_COLUMNS:
    p = _c["parent"]
    if p is not None:
        TOTAL_CHILDREN.setdefault(p, []).append(_c["key"])


# ---------------------------------------------------------------------------
# Aggregation formulas - how each computed total is derived.
#
# These reproduce exactly the arithmetic of the official A.Navoiy reference
# sheet, where (importantly):
#   * ``crops_total`` = irrigated + rainfed   (greenhouse is "of which", i.e. a
#     subset of irrigated and is therefore NOT added again);
#   * ``agricultural_total`` = crops + perennials + virgin + hayfields +
#     pastures;
#   * ``total_area`` = agricultural + meliorative + forests + shrubs +
#     non-agricultural.
# Verified numerically against the A.Navoiy massif totals.
# ---------------------------------------------------------------------------
AGG_FORMULAS = [
    ("crops_total",        ["irrigated", "rainfed"]),
    ("perennial_total",    ["gardens", "vineyards", "mulberry", "fruit_nursery"]),
    ("forest_total",       ["shelterbelts", "poplar"]),
    ("water_total",        ["rivers", "lakes_natural", "lakes_artificial", "canals"]),
    ("agricultural_total", ["crops_total", "perennial_total", "virgin", "hayfields", "pastures"]),
    ("nonagri_total",      ["water_total", "roads", "buildings", "yards", "other_land"]),
    ("total_area",         ["agricultural_total", "meliorative", "forest_total", "shrubs", "nonagri_total"]),
]

# Columns that are "of which" subsets and must never be summed into a total.
SUBSET_KEYS = ["greenhouse"]


# ---------------------------------------------------------------------------
# 3.  GIS ``semantika`` label -> balance column
#
# The labels are normalised before lookup (see normalize_semantika) because the
# raw values contain inconsistent apostrophes (', `, U+2018, U+02BB) and stray
# control bytes left over from the .mdb code page.  Keys below are stored in the
# normalised form: upper-cased, apostrophe-stripped, single spaced, ASCII-ish.
# ---------------------------------------------------------------------------

# Agricultural land-use polygon labels ------------------------------------
SEMANTIKA_TO_BALANCE = {
    # arable
    "SUGORILADIGAN XAYDALADIGAN YERLAR":   "irrigated",
    "SUGORILADIGAN XAYDALANADIGAN YERLAR": "irrigated",
    "LALMI XAYDALADIGAN YERLAR":           "rainfed",
    "LALMI YERLAR":                        "rainfed",
    # perennials
    "MEVALI VA SITRUSLI BOGLAR":           "gardens",
    "REZAVOR MEVALI BOGLAR":               "gardens",
    "BOGLAR":                              "gardens",
    "UZUMZORLAR":                          "vineyards",
    "TOKZORLAR":                           "vineyards",
    "TUTZOR MAYDONLI":                     "mulberry",
    "TUTZOR":                              "mulberry",
    "TUTZORLAR":                           "mulberry",
    "KOCHATZORLAR":                        "fruit_nursery",
    "MEVALI KOCHATZORLAR":                 "fruit_nursery",
    # greenhouses
    "ISSIQXONALAR VA QISHDA OSIMLIKLARNI YETISHTIRISHVA SAQLASHUCHUN ISSIQ SIRLANGAN XONA": "greenhouse",
    "ISSIQXONALAR":                        "greenhouse",
    # rangeland / hay
    "YAYLOV":                              "pastures",
    "YAYLOVLAR":                           "pastures",
    "PICHANZOR":                           "hayfields",
    "PICHANZORLAR":                        "hayfields",
    "BOZ YERLAR":                          "virgin",
    # forest / shrubs
    "SIYRAK ORMON":                        "forest_total",
    "ORMON":                               "forest_total",
    "IXOTA DARAXTZORLAR":                  "shelterbelts",
    "TERAKZORLAR":                         "poplar",
    "BUTAZORLAR":                          "shrubs",
    "BUTALAR":                             "shrubs",

    # --- non-agricultural land-use polygon labels --------------------
    "AHOLI PUNKTI":                        "other_land",
    "DALA_TOMORQA":                        "other_land",
    "DALA TOMORQA":                        "other_land",
    "QURILISHLAR":                         "buildings",
    "ELEKTRNIMSTANSIYA":                   "buildings",
    "QABRISTON":                           "other_land",
    "XAROBALAR":                           "other_land",
    "OZGA YERDAN FOYDALANUCHILAR":         "other_land",
    "FOYDALANILMAYDIGAN YERLAR":           "other_land",
    "SUV QOPLAMLI QUMLAR":                 "other_land",

    # --- hydrography polygon labels (water fund) ---------------------
    "BASSEYNLAR":                          "lakes_artificial",
    "BETONLANGAN KANALLAR":                "canals",
    "KANALLAR":                            "canals",
    "NASOS STANSIYALARI":                  "buildings",
    "DARYO":                               "rivers",
    "DARYO VA SOYLAR":                     "rivers",
    "KOLLAR":                              "lakes_natural",
    "TABIIY KOLLAR":                       "lakes_natural",
    "SUNIY KOLLAR":                        "lakes_artificial",

    # --- roads -------------------------------------------------------
    "YOLLAR":                              "roads",
    "AVTOMOBIL YOLLARI":                   "roads",
}


# ---------------------------------------------------------------------------
# 4.  ``Yonalishi`` (specialization) normalisation
# ---------------------------------------------------------------------------
# The statement stores the farm specialization in free text ("Пахта-ғалла",
# "п-г", "Боғдорчилик", "Чорвачилик", ...).  We normalise it to a small set so
# the report can group / colour by specialization consistently.
SPECIALIZATION_ALIASES = {
    "ПАХТА-ҒАЛЛА": "Пахтачилик-ғаллачилик",
    "П-Г": "Пахтачилик-ғаллачилик",
    "ПАХТАЧИЛИК-ҒАЛЛАЧИЛИК": "Пахтачилик-ғаллачилик",
    "БОҒДОРЧИЛИК": "Боғдорчилик",
    "УЗУМЧИЛИК": "Узумчилик",
    "ЧОРВАЧИЛИК": "Чорвачилик",
    "ҚОРАМОЛЧИЛИК": "Чорвачилик",
    "САБЗАВОТЧИЛИК": "Сабзавотчилик",
}


# ---------------------------------------------------------------------------
# 5.  Cartographic colours per balance leaf category (RGB 0-255).
#
# Chosen to resemble the A.Navoiy reference sheet: warm tones for crops, greens
# for plantations/pasture, blues for water, greys for built-up / other.
# ---------------------------------------------------------------------------
CATEGORY_COLORS = {
    "irrigated":        (255, 235, 175),
    "rainfed":          (233, 215, 160),
    "greenhouse":       (255, 200, 120),
    "gardens":          (170, 215, 120),
    "vineyards":        (190, 120, 190),
    "mulberry":         (120, 180, 90),
    "fruit_nursery":    (200, 230, 150),
    "virgin":           (220, 220, 180),
    "hayfields":        (200, 225, 130),
    "pastures":         (215, 235, 160),
    "meliorative":      (245, 220, 200),
    "forest_total":     (90, 150, 80),
    "shelterbelts":     (110, 165, 95),
    "poplar":           (130, 175, 100),
    "shrubs":           (160, 195, 120),
    "rivers":           (150, 200, 235),
    "lakes_natural":    (120, 180, 230),
    "lakes_artificial": (140, 195, 235),
    "canals":           (170, 210, 240),
    "roads":            (180, 180, 180),
    "buildings":        (200, 150, 140),
    "yards":            (220, 200, 190),
    "other_land":       (225, 225, 225),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_semantika(value):
    """Normalise a raw ``semantika`` string for dictionary lookup.

    Strips control bytes, unifies the four kinds of apostrophe used in Uzbek
    Latin, collapses whitespace and upper-cases.  Returns ``""`` for empty /
    None input.
    """
    if value is None:
        return ""
    try:
        text = value if isinstance(value, type(u"")) else value.decode("utf-8", "ignore")
    except Exception:
        text = u"%s" % (value,)
    # Drop the apostrophe family entirely so "BOG'LAR" == "BOGLAR".  Mojibake
    # from the .mdb code page sometimes leaves an apostrophe stand-in followed
    # by a stray space (e.g. "BOG\x18 LAR"), so remove an immediately following
    # space too.
    for ch in (u"'", u"`", u"\u2018", u"\u2019", u"\u02bb", u"\u02bc",
               u"\u0018", u"\u02b9"):
        text = text.replace(ch + u" ", u"").replace(ch, u"")
    # Parentheses carry no meaning for classification ("TUTZOR (MAYDONLI)").
    text = text.replace(u"(", u" ").replace(u")", u" ")
    # Replace any remaining control / non-printing chars with a space.
    cleaned = []
    for ch in text:
        if ord(ch) < 32:
            cleaned.append(u" ")
        else:
            cleaned.append(ch)
    text = u"".join(cleaned)
    # Collapse whitespace, upper-case.
    text = u" ".join(text.split()).upper()
    return text


def classify_semantika(value):
    """Return the balance column key for a raw ``semantika`` value, or None."""
    return SEMANTIKA_TO_BALANCE.get(normalize_semantika(value))


def normalize_specialization(value):
    """Map a free-text specialization to a canonical Cyrillic label."""
    if not value:
        return u""
    raw = (u"%s" % value).strip().upper()
    return SPECIALIZATION_ALIASES.get(raw, (u"%s" % value).strip())
