# -*- coding: utf-8 -*-
"""
Personal geodatabase (.mdb) reader - ArcPy layer.

Opens an ESRI personal geodatabase, tolerantly resolves the logical layer and
field names defined in :mod:`config.settings` against whatever physical names
the particular massif actually uses, and reads attribute rows / polygon areas.

This module *requires* arcpy and therefore only runs inside the ArcGIS Desktop
10.8.2 Python 2.7 environment.  ``arcpy`` is imported lazily inside the methods
that need it so that the module can still be imported (e.g. for introspection
or documentation) on a machine without ArcGIS - in that case ``ARCPY_AVAILABLE``
is False and any read attempt raises a clear RuntimeError.
"""

from __future__ import unicode_literals

import os

from config import settings

try:
    import arcpy
    ARCPY_AVAILABLE = True
except ImportError:                       # pragma: no cover - non-ArcGIS host
    arcpy = None
    ARCPY_AVAILABLE = False


class GeodatabaseError(Exception):
    pass


class GeodatabaseReader(object):
    """Thin, fault-tolerant accessor over one .mdb personal geodatabase."""

    def __init__(self, mdb_path, logger=None):
        if not ARCPY_AVAILABLE:
            raise GeodatabaseError(
                "arcpy is not available - GeodatabaseReader can only run "
                "inside ArcGIS Desktop 10.8.2 (Python 2.7).")
        if not mdb_path or not os.path.exists(mdb_path):
            raise GeodatabaseError("Geodatabase not found: %s" % mdb_path)
        self.path = mdb_path
        self.logger = logger
        self._catalog = None          # cached list of dataset names (upper-cased map)
        self._resolved = {}           # logical -> physical name cache

    # ------------------------------------------------------------------
    # catalog / name resolution
    # ------------------------------------------------------------------
    def _log(self, level, msg, *args):
        if self.logger:
            getattr(self.logger, level)(msg, *args)

    def _build_catalog(self):
        if self._catalog is not None:
            return self._catalog
        old = arcpy.env.workspace
        names = {}
        try:
            arcpy.env.workspace = self.path
            datasets = []
            datasets += list(arcpy.ListFeatureClasses() or [])
            datasets += list(arcpy.ListTables() or [])
            # feature classes inside feature datasets
            for fds in (arcpy.ListDatasets("", "Feature") or []):
                for fc in (arcpy.ListFeatureClasses("", "", fds) or []):
                    datasets.append(os.path.join(fds, fc))
            for d in datasets:
                names[_norm_name(os.path.basename(d))] = d
        finally:
            arcpy.env.workspace = old
        self._catalog = names
        return names

    def resolve_layer(self, logical_name):
        """Return the physical dataset name for a logical layer, or None."""
        if logical_name in self._resolved:
            return self._resolved[logical_name]
        catalog = self._build_catalog()
        candidates = settings.LAYERS.get(logical_name, [logical_name])
        physical = None
        for cand in candidates:
            key = _norm_name(cand)
            if key in catalog:
                physical = catalog[key]
                break
        if physical is None:
            # Last resort: fuzzy contains-match on the first candidate token.
            token = _norm_name(candidates[0])
            for key, value in catalog.items():
                if token and token in key:
                    physical = value
                    break
        self._resolved[logical_name] = physical
        if physical:
            self._log("debug", "Resolved layer %s -> %s", logical_name, physical)
        else:
            self._log("warning", "Layer not found in %s: %s (tried %s)",
                      os.path.basename(self.path), logical_name, candidates)
        return physical

    def layer_path(self, logical_name):
        physical = self.resolve_layer(logical_name)
        if not physical:
            return None
        return os.path.join(self.path, physical)

    def has_layer(self, logical_name):
        return self.resolve_layer(logical_name) is not None

    def feature_count(self, logical_name):
        path = self.layer_path(logical_name)
        if not path:
            return 0
        try:
            return int(arcpy.GetCount_management(path).getOutput(0))
        except Exception as exc:               # pragma: no cover
            self._log("warning", "GetCount failed for %s: %s", logical_name, exc)
            return 0

    # ------------------------------------------------------------------
    # field resolution
    # ------------------------------------------------------------------
    def list_fields(self, logical_name):
        path = self.layer_path(logical_name)
        if not path:
            return []
        try:
            return [f.name for f in arcpy.ListFields(path)]
        except Exception:                      # pragma: no cover
            return []

    def resolve_field(self, logical_name, candidates):
        """Pick the first existing field name from a candidate list."""
        fields = dict((_norm_name(f), f) for f in self.list_fields(logical_name))
        for cand in candidates:
            hit = fields.get(_norm_name(cand))
            if hit:
                return hit
        return None

    # ------------------------------------------------------------------
    # reading rows
    # ------------------------------------------------------------------
    def read_rows(self, logical_name, field_map):
        """Read selected attribute rows from a layer.

        ``field_map`` maps an output key -> list of candidate field names.  The
        special key ``"area_ha"`` is satisfied from the geometry (SHAPE@AREA)
        converted to hectares using the layer's linear unit, falling back to the
        Shape_Area attribute when no geometry token is available.

        Yields a dict per feature.
        """
        path = self.layer_path(logical_name)
        if not path:
            return

        # Resolve each logical field to a physical name.
        resolved = {}
        for out_key, candidates in field_map.items():
            if out_key == "area_ha":
                continue
            fld = self.resolve_field(logical_name, candidates)
            if fld:
                resolved[out_key] = fld

        cursor_fields = list(resolved.values())
        want_area = "area_ha" in field_map
        if want_area:
            cursor_fields = ["SHAPE@AREA"] + cursor_fields

        # m2 -> ha factor (areas come back in the SR linear unit squared).
        factor = self._area_to_ha_factor(path)

        try:
            with arcpy.da.SearchCursor(path, cursor_fields) as cur:
                for row in cur:
                    record = {}
                    offset = 0
                    if want_area:
                        area_units = row[0] or 0.0
                        record["area_ha"] = (area_units * factor) if area_units else 0.0
                        offset = 1
                    for i, out_key in enumerate(resolved.keys()):
                        record[out_key] = row[offset + i]
                    yield record
        except Exception as exc:                # pragma: no cover
            self._log("error", "Failed reading %s: %s", logical_name, exc)
            return

    def _area_to_ha_factor(self, path):
        """Return multiplier that converts SHAPE@AREA values into hectares."""
        try:
            sr = arcpy.Describe(path).spatialReference
            unit = (sr.linearUnitName or "").lower() if sr else ""
        except Exception:
            unit = ""
        if "foot" in unit or "feet" in unit:
            # square feet -> hectares
            return 0.09290304 / settings.SQM_PER_HA
        # default: metres -> square metres -> hectares
        return 1.0 / settings.SQM_PER_HA

    # ------------------------------------------------------------------
    def __repr__(self):
        return "<GeodatabaseReader %s>" % os.path.basename(self.path)


def _norm_name(name):
    """Normalise a dataset / field name for case- and apostrophe-insensitive
    comparison."""
    if name is None:
        return ""
    text = name if isinstance(name, type("")) else ("%s" % name)
    for ch in ("'", "`", "\u2018", "\u2019", "\u02bb"):
        text = text.replace(ch, "")
    return text.strip().upper()
