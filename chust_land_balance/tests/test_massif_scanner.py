# -*- coding: utf-8 -*-
"""Tests for massif discovery and registry matching."""

from __future__ import unicode_literals

import os

from src import massif_scanner


def _touch(path):
    with open(path, "w") as fh:
        fh.write("x")


def test_scan_detects_massif_folders_and_matches_registry(tmp_path):
    root = str(tmp_path)
    # 001 Varzik with a geodatabase + excel
    v = os.path.join(root, "001 Varzik")
    os.makedirs(v)
    _touch(os.path.join(v, "VARZIK MASSIVI.mdb"))
    _touch(os.path.join(v, "Varzik.xls"))
    _touch(os.path.join(v, "map.mxd"))
    # 011 Navoiy with only an archive
    n = os.path.join(root, "011 Navoiy")
    os.makedirs(n)
    _touch(os.path.join(n, "navoiy.7z"))
    # a junk folder that should be ignored
    os.makedirs(os.path.join(root, "notes"))
    _touch(os.path.join(root, "notes", "readme.txt"))

    datasets = massif_scanner.scan_root(root)
    by_code = dict((d.code, d) for d in datasets if d.code)

    assert "001" in by_code
    assert by_code["001"].key == "varzik"
    assert by_code["001"].has_geodatabase
    assert by_code["001"].is_processable

    assert "011" in by_code
    assert by_code["011"].key == "navoiy"
    # only an archive -> not yet processable, but archive recorded
    assert by_code["011"].archives
    assert not by_code["011"].has_geodatabase

    # ordering: registered massifs sorted by code
    codes = [d.code for d in datasets if d.code]
    assert codes == sorted(codes)


def test_primary_excel_prefers_name_match(tmp_path):
    root = str(tmp_path)
    folder = os.path.join(root, "001 Varzik")
    os.makedirs(folder)
    _touch(os.path.join(folder, "VARZIK MASSIVI.mdb"))
    _touch(os.path.join(folder, "random.xls"))
    _touch(os.path.join(folder, "Varzik.xls"))
    datasets = massif_scanner.scan_root(root)
    ds = datasets[0]
    assert os.path.basename(ds.primary_excel()).lower() == "varzik.xls"


def test_output_folders_are_skipped(tmp_path):
    from config import settings
    root = str(tmp_path)
    out = os.path.join(root, settings.OUTPUT_DIRNAME)
    os.makedirs(out)
    _touch(os.path.join(out, "something.mdb"))
    datasets = massif_scanner.scan_root(root)
    assert datasets == []
