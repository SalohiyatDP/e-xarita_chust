# -*- coding: utf-8 -*-
"""
Processing orchestration.

Ties the whole pipeline together for a single massif and for the whole
district.  Designed to be driven from either the CLI or the GUI, with an
optional ``progress`` callback so a GUI can show live status.

Per massif:
    archive -> .mdb  (auto-extract .zip/.7z when needed)
    open geodatabase -> read statement + Excel -> join -> calculate balance
    -> write reports (HTML/Excel/PDF) -> build & export map (PDF/JPG)

District:
    aggregate every successful massif balance -> overview + SVOD reports.

Robust by design: every massif is processed inside its own try/except so one
bad data set never aborts the batch; missing files are reported, not fatal.
"""

from __future__ import unicode_literals

import os
import time
import zipfile

from config import settings
from src import balance_calculator
from src import data_joiner
from src import district_summary
from src import excel_reader
from src import report_generator
from src.logger import get_logger


class MassifResult(object):
    def __init__(self, massif):
        self.massif = massif
        self.success = False
        self.balance = None              # MassifBalance
        self.outputs = {}                # role -> path
        self.errors = []
        self.warnings = []
        self.duration = 0.0

    @property
    def name(self):
        return self.massif.name


def _extract_archive_if_needed(massif, work_dir, logger):
    """If the massif has no .mdb but has an archive, try to extract it.

    Supports .zip natively (stdlib) and .7z when ``py7zr`` or a ``7z`` binary is
    available.  Returns the path to an extracted .mdb or None.
    """
    if massif.mdb:
        return massif.mdb
    if not massif.archives:
        return None

    if not os.path.isdir(work_dir):
        os.makedirs(work_dir)

    for archive in massif.archives:
        low = archive.lower()
        try:
            if low.endswith(".zip"):
                logger.info("Extracting ZIP archive: %s", archive)
                with zipfile.ZipFile(archive) as zf:
                    zf.extractall(work_dir)
            elif low.endswith(".7z"):
                if not _extract_7z(archive, work_dir, logger):
                    continue
            else:
                continue
        except Exception as exc:
            logger.error("Failed to extract %s: %s", archive, exc)
            continue
        mdb = _find_mdb(work_dir)
        if mdb:
            logger.info("Extracted geodatabase: %s", mdb)
            massif.mdb = mdb
            return mdb
    return None


def _extract_7z(archive, work_dir, logger):
    # Try py7zr first.
    try:
        import py7zr
        with py7zr.SevenZipFile(archive, "r") as z:
            z.extractall(work_dir)
        return True
    except ImportError:
        pass
    except Exception as exc:
        logger.error("py7zr extraction failed for %s: %s", archive, exc)
    # Fall back to a 7z / 7za command-line binary if present on PATH.
    import subprocess
    for exe in ("7z", "7za", "7z.exe", "C:/Program Files/7-Zip/7z.exe"):
        try:
            subprocess.check_call([exe, "x", "-y", "-o%s" % work_dir, archive])
            return True
        except Exception:
            continue
    logger.error("Cannot extract .7z (install py7zr or 7-Zip): %s", archive)
    return False


def _find_mdb(folder):
    for root, _dirs, files in os.walk(folder):
        for f in files:
            if f.lower().endswith(".mdb"):
                return os.path.join(root, f)
    return None


def process_massif(massif, out_root=None, logger=None, progress=None,
                   make_map=True, make_report=True):
    """Process one :class:`MassifDataset`.  Returns a :class:`MassifResult`."""
    start = time.time()
    result = MassifResult(massif)
    log = logger or get_logger("massif_%s" % (massif.key or "x"))

    def _emit(pct, message):
        if progress:
            progress(pct, message)
        log.info(message)

    basename = "%s_%s" % (massif.code or "000", massif.key)
    massif_out = out_root or os.path.join(massif.folder, settings.OUTPUT_DIRNAME)
    work_dir = os.path.join(massif_out, "_extracted")

    try:
        _emit(5, u"[%s] Boshlanmoqda / Starting" % massif.name)

        # 1) ensure we have a geodatabase
        mdb = _extract_archive_if_needed(massif, work_dir, log)
        if not mdb:
            msg = u"Geodatabase (.mdb) topilmadi / not found for %s" % massif.name
            result.errors.append(msg)
            log.error(msg)
            return result

        # 2) open geodatabase (requires arcpy)
        from src import geodatabase_reader as gdb
        if not gdb.ARCPY_AVAILABLE:
            msg = (u"arcpy mavjud emas - .mdb o'qib bo'lmaydi. ArcGIS Desktop "
                   u"10.8.2 (Python 2.7) ichida ishga tushiring.")
            result.errors.append(msg)
            log.error(msg)
            return result

        reader = gdb.GeodatabaseReader(mdb, log)
        _emit(20, u"[%s] Geodatabaza ochildi / opened" % massif.name)

        # 2a) report layer readiness
        for logical in settings.REQUIRED_LAYERS:
            present = reader.has_layer(logical)
            if not present:
                w = u"Qatlam topilmadi / layer missing: %s" % logical
                result.warnings.append(w)
                log.warning(w)
        if not reader.has_layer(settings.PRIMARY_DATA_LAYER):
            msg = (u"Asosiy qatlam yo'q / primary layer missing: %s"
                   % settings.PRIMARY_DATA_LAYER)
            result.errors.append(msg)
            log.error(msg)
            return result

        # 3) read the contour-statement Excel (best effort)
        excel_sheet = None
        primary_xls = massif.primary_excel()
        if primary_xls:
            _emit(30, u"[%s] Excel o'qilmoqda: %s"
                  % (massif.name, os.path.basename(primary_xls)))
            excel_sheet = excel_reader.read_workbook(primary_xls, logger=log)

        # 4) join GIS + Excel -> parcels
        _emit(45, u"[%s] Ma'lumotlar birlashtirilmoqda / joining" % massif.name)
        parcels = data_joiner.join_massif(reader, excel_sheet, log)
        if not parcels:
            msg = u"Hech qanday kontur o'qilmadi / no parcels read."
            result.errors.append(msg)
            log.error(msg)
            return result

        # 5) calculate balance
        _emit(60, u"[%s] Balans hisoblanmoqda / calculating" % massif.name)
        mb = balance_calculator.calculate(
            parcels, massif.name, massif.name_cyr, massif.code, log)
        result.balance = mb
        result.warnings.extend(mb.warnings)

        # 6) reports
        if make_report:
            _emit(72, u"[%s] Hisobot tayyorlanmoqda / report" % massif.name)
            rep = report_generator.generate_report(mb, massif_out, basename, log)
            result.outputs.update(rep)

        # 7) map
        if make_map:
            _emit(85, u"[%s] Xarita tayyorlanmoqda / map layout" % massif.name)
            try:
                from src import map_layout
                map_out = map_layout.build_and_export(
                    massif, reader, mb, massif_out, basename, log)
                result.outputs.update(map_out)
            except Exception as exc:
                w = u"Xarita yaratilmadi / map export skipped: %s" % exc
                result.warnings.append(w)
                log.warning(w)

        result.success = True
        _emit(100, u"[%s] Tugadi / done" % massif.name)
    except Exception as exc:
        log.exception("Unhandled error processing %s", massif.name)
        result.errors.append(u"%s" % exc)
    finally:
        result.duration = time.time() - start
    return result


def process_district(datasets, root, logger=None, progress=None,
                     make_map=True, make_report=True):
    """Process every massif dataset and build the district summary.

    Returns dict: {"results": [MassifResult...], "district_outputs": {...},
    "district_balance": MassifBalance}.
    """
    district_out = os.path.join(root, settings.DISTRICT_OUTPUT_DIRNAME)
    log_dir = os.path.join(root, settings.LOG_DIRNAME)
    log = logger or get_logger("chust_district", log_dir)

    log.info("=" * 60)
    log.info("Chust district batch: %d massif data set(s).", len(datasets))

    results = []
    balances = []
    total = max(1, len(datasets))
    for i, ds in enumerate(datasets):
        if progress:
            progress(int(100.0 * i / total),
                     u"Massiv %d/%d: %s" % (i + 1, total, ds.name))
        massif_out = os.path.join(ds.folder, settings.OUTPUT_DIRNAME)
        res = process_massif(ds, massif_out, log, None, make_map, make_report)
        results.append(res)
        if res.success and res.balance is not None:
            balances.append(res.balance)

    district_outputs = {}
    district_balance = None
    if balances:
        if progress:
            progress(98, u"Tuman bo'yicha jamlanma / district summary")
        district_balance = district_summary.aggregate_district(balances, log)
        district_outputs = _write_district_reports(
            balances, district_balance, district_out, log)

    ok = sum(1 for r in results if r.success)
    log.info("Batch finished: %d/%d massifs succeeded.", ok, len(results))
    if progress:
        progress(100, u"Tayyor / finished: %d/%d" % (ok, len(results)))

    return {
        "results": results,
        "district_outputs": district_outputs,
        "district_balance": district_balance,
    }


def _write_district_reports(balances, district_balance, out_dir, log):
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    overview = district_summary.build_overview_table(balances)
    svod = district_summary.build_district_svod(district_balance)
    title = u"%s %s - ер балансининг туман жадвали" % (
        settings.REGION_NAME_CYR, settings.DISTRICT_NAME_CYR)
    meta = u"%s | Массивлар сони: %d" % (
        time.strftime("%d.%m.%Y"), len(balances))

    outputs = {}
    html_path = os.path.join(out_dir, "DISTRICT_SUMMARY.html")
    outputs["district_html"] = report_generator.write_html(
        [overview, svod], html_path, title, meta)
    log.info("District HTML summary: %s", html_path)

    xlsx_path = os.path.join(out_dir, "DISTRICT_SUMMARY.xlsx")
    xls_out = report_generator.write_excel([overview, svod], xlsx_path, title)
    if xls_out:
        outputs["district_excel"] = xls_out
        log.info("District Excel summary: %s", xls_out)

    pdf_path = os.path.join(out_dir, "DISTRICT_SUMMARY.pdf")
    pdf_out = report_generator.write_pdf([overview, svod], pdf_path, title,
                                         meta, log)
    if pdf_out:
        outputs["district_pdf"] = pdf_out
    return outputs
