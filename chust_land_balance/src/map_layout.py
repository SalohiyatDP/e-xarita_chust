# -*- coding: utf-8 -*-
"""
Cartographic layout builder and exporter (ArcPy ``arcpy.mapping``).

Produces the electronic land-balance map sheet in the style of the A.Navoiy
reference: title block, legend, north arrow, scale bar/text, coordinate grid,
contour labels, land-category fill colours and a summary-statistics panel; then
exports a print-quality PDF and a JPG preview.

Strategy (in order of preference):
1. Open the massif's own ``.mxd`` when one was supplied - it is already authored
   to the official template, so we only refresh layers, extent and text.
2. Otherwise open the shared template ``templates/land_balance_layout.mxd``.
3. If neither exists we log a clear warning and skip map export (the textual
   balance report is still produced).

Requires ArcGIS Desktop 10.8.2 / Python 2.7.  ``arcpy`` is imported lazily.
"""

from __future__ import unicode_literals

import os

from config import settings
from config import land_categories as lc

try:
    import arcpy
    ARCPY_AVAILABLE = True
except ImportError:                       # pragma: no cover
    arcpy = None
    ARCPY_AVAILABLE = False


# Layout text elements are matched by a token that the template author puts in
# the element's *Element Name* (Properties > Size and Position > Element Name).
TEXT_TOKENS = {
    "title": "TITLE",
    "subtitle": "SUBTITLE",
    "scale": "SCALE_TEXT",
    "stats": "STATS",
    "date": "DATE_TEXT",
    "author": "AUTHOR_TEXT",
}


class MapExportError(Exception):
    pass


class MapBuilder(object):
    def __init__(self, massif, reader=None, logger=None):
        """``massif`` is a MassifDataset; ``reader`` an open GeodatabaseReader."""
        if not ARCPY_AVAILABLE:
            raise MapExportError("arcpy not available - cannot build map layout.")
        self.massif = massif
        self.reader = reader
        self.logger = logger
        self.mxd = None
        self.data_frame = None

    def _log(self, level, msg, *args):
        if self.logger:
            getattr(self.logger, level)(msg, *args)

    # ------------------------------------------------------------------
    def _locate_mxd(self):
        if self.massif.mxd and os.path.exists(self.massif.mxd):
            return self.massif.mxd
        if os.path.exists(settings.DEFAULT_MXD_TEMPLATE):
            return settings.DEFAULT_MXD_TEMPLATE
        return None

    def open(self):
        mxd_path = self._locate_mxd()
        if not mxd_path:
            raise MapExportError(
                "No .mxd available for %s and template missing (%s). "
                "Map export skipped." % (self.massif.name,
                                         settings.DEFAULT_MXD_TEMPLATE))
        self._log("info", "Opening map document: %s", mxd_path)
        self.mxd = arcpy.mapping.MapDocument(mxd_path)
        frames = arcpy.mapping.ListDataFrames(self.mxd)
        if not frames:
            raise MapExportError("Map document has no data frame: %s" % mxd_path)
        self.data_frame = frames[0]
        return self

    # ------------------------------------------------------------------
    def ensure_layers(self):
        """Add the massif layers if the data frame is empty.

        When the massif came with its own MXD the layers are already present and
        styled; we leave them untouched.  When we opened the shared template we
        add the geodatabase feature classes and apply symbology from the .lyr
        file when one is available.
        """
        existing = arcpy.mapping.ListLayers(self.mxd, "", self.data_frame)
        if existing:
            self._log("debug", "Map already has %d layer(s); leaving as authored.",
                      len(existing))
            return

        if not self.reader:
            self._log("warning", "No geodatabase reader; cannot add layers.")
            return

        # Add the main visible layers from bottom to top.
        order = [
            "HUDUD_CHEGARASI_MAYDONLI",
            "QISHLOQ_XOJALIGI_YERLARI_MAYDONLI",
            "NOQISHLOQ_XOJALIGI_YERLARI_MAYDONLI",
            "GIDROGRAFIYA_MAYDONLI",
            "YOLLAR_MAYDONLI",
            "KONTURLAR_RAQAMI_NUQTALI",
        ]
        for logical in order:
            path = self.reader.layer_path(logical)
            if not path:
                continue
            try:
                lyr = arcpy.mapping.Layer(path)
                arcpy.mapping.AddLayer(self.data_frame, lyr, "BOTTOM")
                self._log("debug", "Added layer %s", logical)
            except Exception as exc:
                self._log("warning", "Could not add layer %s: %s", logical, exc)

        # Apply the supplied .lyr symbology to the agricultural layer.
        if self.massif.lyr and os.path.exists(self.massif.lyr):
            self._apply_symbology(self.massif.lyr)

    def _apply_symbology(self, lyr_file):
        try:
            source_lyr = arcpy.mapping.Layer(lyr_file)
            for lyr in arcpy.mapping.ListLayers(self.mxd, "", self.data_frame):
                try:
                    arcpy.mapping.UpdateLayer(self.data_frame, lyr, source_lyr, True)
                    self._log("debug", "Applied symbology from %s to %s",
                              os.path.basename(lyr_file), lyr.name)
                    break
                except Exception:
                    continue
        except Exception as exc:
            self._log("warning", "Could not apply .lyr symbology: %s", exc)

    # ------------------------------------------------------------------
    def zoom_to_massif(self):
        """Set the data-frame extent to the massif boundary / agricultural area."""
        for logical in ("HUDUD_CHEGARASI_MAYDONLI",
                        "QISHLOQ_XOJALIGI_YERLARI_MAYDONLI",
                        "FERMER_CHEGARA_XATLOV"):
            if not self.reader:
                break
            path = self.reader.layer_path(logical)
            if not path:
                continue
            try:
                desc = arcpy.Describe(path)
                if desc.extent and desc.extent.width:
                    ext = desc.extent
                    # add a 5% margin
                    margin_x = ext.width * 0.05
                    margin_y = ext.height * 0.05
                    new_ext = arcpy.Extent(ext.XMin - margin_x, ext.YMin - margin_y,
                                           ext.XMax + margin_x, ext.YMax + margin_y)
                    self.data_frame.extent = new_ext
                    self._log("debug", "Zoomed to %s", logical)
                    return
            except Exception as exc:
                self._log("warning", "Zoom to %s failed: %s", logical, exc)

    # ------------------------------------------------------------------
    def update_text(self, massif_balance=None):
        """Fill the template's title / scale / stats text placeholders."""
        title = u"%s %s %s массиви электрон ер баланси харитаси" % (
            settings.REGION_NAME_CYR, settings.DISTRICT_NAME_CYR,
            self.massif.name_cyr)
        subtitle = settings.PROJECT_NAME

        replacements = {
            "title": title,
            "subtitle": subtitle,
            "scale": self._scale_text(),
            "date": _today(),
            "author": settings.PROJECT_NAME,
        }
        if massif_balance is not None:
            replacements["stats"] = self._stats_text(massif_balance)

        elements = arcpy.mapping.ListLayoutElements(self.mxd, "TEXT_ELEMENT")
        by_name = dict((e.name.upper(), e) for e in elements if e.name)
        for key, token in TEXT_TOKENS.items():
            if key not in replacements:
                continue
            for ename, elem in by_name.items():
                if token in ename:
                    try:
                        elem.text = replacements[key]
                    except Exception as exc:
                        self._log("warning", "Could not set text %s: %s", token, exc)
                    break

    def _scale_text(self):
        try:
            return u"М 1:%s" % int(round(self.data_frame.scale))
        except Exception:
            return u""

    def _stats_text(self, mb):
        h = mb.headline()
        lines = [
            u"ЕР БАЛАНСИ (га):",
            u"Умумий майдон: %.2f" % h["total_area"],
            u"Қ/х ерлари: %.2f" % h["agricultural_total"],
            u"  Суғориладиган: %.2f" % h["irrigated"],
            u"  Боғлар: %.2f  Токзор: %.2f" % (h["gardens"], h["vineyards"]),
            u"  Тутзор: %.2f  Яйлов: %.2f" % (h["mulberry"], h["pastures"]),
            u"Қ/х да фойдаланилмайдиган: %.2f" % h["nonagri_total"],
            u"Хўжаликлар сони: %d" % mb.farm_count,
        ]
        return u"\n".join(lines)

    # ------------------------------------------------------------------
    def enable_grid(self):
        """Best-effort: ensure the first grid of the data frame is visible.

        Coordinate grids (graticule / measured grid) are authored in the MXD;
        arcpy cannot create one from scratch, but we can make sure an existing
        grid is turned on.
        """
        try:
            # Grids are not exposed via arcpy.mapping; this is a no-op hook kept
            # for documentation / future arcpy.mp (Pro) migration.
            pass
        except Exception:
            pass

    # ------------------------------------------------------------------
    def export(self, out_dir, basename):
        """Export PDF map and JPG preview.  Returns dict of output paths."""
        if not os.path.isdir(out_dir):
            os.makedirs(out_dir)
        outputs = {}
        pdf_path = os.path.join(out_dir, basename + "_MAP.pdf")
        jpg_path = os.path.join(out_dir, basename + "_PREVIEW.jpg")
        try:
            arcpy.mapping.ExportToPDF(self.mxd, pdf_path,
                                      resolution=settings.PDF_MAP_DPI)
            outputs["pdf_map"] = pdf_path
            self._log("info", "Exported PDF map: %s", pdf_path)
        except Exception as exc:
            self._log("error", "PDF map export failed: %s", exc)
        try:
            arcpy.mapping.ExportToJPEG(self.mxd, jpg_path,
                                       resolution=settings.JPG_PREVIEW_DPI)
            outputs["jpg_preview"] = jpg_path
            self._log("info", "Exported JPG preview: %s", jpg_path)
        except Exception as exc:
            self._log("error", "JPG preview export failed: %s", exc)
        return outputs

    def close(self):
        if self.mxd is not None:
            del self.mxd
            self.mxd = None


def build_and_export(massif, reader, massif_balance, out_dir, basename,
                     logger=None):
    """Convenience one-shot: open -> layers -> zoom -> text -> export -> close."""
    builder = MapBuilder(massif, reader, logger)
    try:
        builder.open()
        builder.ensure_layers()
        builder.zoom_to_massif()
        builder.enable_grid()
        builder.update_text(massif_balance)
        return builder.export(out_dir, basename)
    finally:
        builder.close()


def _today():
    import time
    return time.strftime("%d.%m.%Y")
