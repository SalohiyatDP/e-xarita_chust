# -*- coding: utf-8 -*-
"""
Domain model for the land balance.

``LandBalance`` is a thin, dependency-free container around the ordered set of
balance columns defined in :mod:`config.land_categories`.  It knows how to:

* add two balances together (aggregate parcels -> category -> massif),
* recompute its derived totals from its leaf values following the official
  formulas, and
* round / export itself for reporting.

``ParcelRecord`` represents one land parcel (one row of the detailed table):
its identity (contour number, land user, specialization, cadastre, legal doc),
its statutory main category (I..VIII) and its :class:`LandBalance`.

Nothing here touches arcpy - fully unit-testable.
"""

from __future__ import unicode_literals

from config import land_categories as lc
from config import settings


def _r(value, decimals=settings.AREA_DECIMALS):
    return round(float(value or 0.0), decimals)


class LandBalance(object):
    """An ordered map of balance-column key -> hectares."""

    __slots__ = ("values",)

    def __init__(self, values=None):
        # Initialise every known column to 0.0 so callers never KeyError.
        self.values = dict((k, 0.0) for k in lc.BALANCE_KEYS)
        if values:
            for k, v in values.items():
                if k in self.values and v is not None:
                    self.values[k] = float(v)

    # -- item access ----------------------------------------------------
    def __getitem__(self, key):
        return self.values[key]

    def __setitem__(self, key, value):
        if key not in self.values:
            raise KeyError("Unknown balance column: %s" % key)
        self.values[key] = float(value or 0.0)

    def get(self, key, default=0.0):
        return self.values.get(key, default)

    # -- arithmetic -----------------------------------------------------
    def add(self, other):
        """In-place accumulate another balance (leaf + measured totals)."""
        for k in lc.BALANCE_KEYS:
            self.values[k] += other.values.get(k, 0.0)
        return self

    def __add__(self, other):
        result = LandBalance(self.values)
        return result.add(other)

    # -- derivation -----------------------------------------------------
    def recompute_totals(self):
        """Recompute every aggregate column from its parts (official formulas).

        Leaf values are left untouched.  Called after a balance has been
        populated from raw sources to make the totals internally consistent.
        """
        for total_key, parts in lc.AGG_FORMULAS:
            self.values[total_key] = sum(self.values.get(p, 0.0) for p in parts)
        return self

    def set_measured_total(self, area_ha):
        """Override ``total_area`` with a directly measured boundary area.

        Many official sheets print the surveyed parcel area rather than the sum
        of components (they can differ by a few hundredths due to rounding).
        The residual, if positive, is pushed into ``other_land`` so the columns
        still reconcile.  Safe to call from any prior state - the component
        totals are recomputed first.
        """
        if not area_ha:
            self.recompute_totals()
            return self
        measured = float(area_ha)
        # Make total_area reflect the true sum of components before measuring.
        self.recompute_totals()
        component_sum = self.values["total_area"]
        residual = round(measured - component_sum, settings.AREA_DECIMALS)
        if residual > 0:
            self.values["other_land"] += residual
            self.recompute_totals()
        self.values["total_area"] = measured
        return self

    def rounded(self, decimals=settings.AREA_DECIMALS):
        """Return a plain dict with every value rounded for reporting."""
        return dict((k, _r(v, decimals)) for k, v in self.values.items())

    def is_empty(self):
        return all(abs(v) < 1e-9 for v in self.values.values())

    def __repr__(self):
        return "<LandBalance total=%.2f agri=%.2f>" % (
            self.values["total_area"], self.values["agricultural_total"])


class ParcelRecord(object):
    """One parcel / contour row of the detailed land-balance table."""

    def __init__(self, contour=None, user_name=None, address=None,
                 cadastre=None, tax_id=None, specialization=None,
                 main_category="agricultural", land_subtype=None,
                 legal_doc=None, legal_date=None, legal_number=None,
                 balance=None):
        self.contour = contour
        self.user_name = user_name or ""
        self.address = address or ""
        self.cadastre = cadastre or ""
        self.tax_id = tax_id or ""
        self.specialization = specialization or ""
        # one of the keys in lc.MAIN_CATEGORY_BY_KEY
        self.main_category = main_category or "agricultural"
        self.land_subtype = land_subtype or ""
        self.legal_doc = legal_doc or ""
        self.legal_date = legal_date or ""
        self.legal_number = legal_number or ""
        self.balance = balance if balance is not None else LandBalance()

    @property
    def total_area(self):
        return self.balance["total_area"]

    def describe(self):
        d = {
            "contour": self.contour,
            "user_name": self.user_name,
            "specialization": self.specialization,
            "main_category": self.main_category,
            "cadastre": self.cadastre,
            "legal_doc": self.legal_doc,
            "legal_date": self.legal_date,
            "legal_number": self.legal_number,
        }
        d.update(self.balance.rounded())
        return d
