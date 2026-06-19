# -*- coding: utf-8 -*-
"""
Command-line batch runner for the Chust land balance system.

Examples
--------
    # process every massif found under a root folder
    python run_cli.py --root "D:\\Chust\\Massivlar"

    # only scan and list what was found (no processing)
    python run_cli.py --root "D:\\Chust\\Massivlar" --scan-only

    # process a single massif by its registry key or code
    python run_cli.py --root "D:\\Chust\\Massivlar" --massif varzik

    # skip the (slow) map export and produce reports only
    python run_cli.py --root "D:\\Chust\\Massivlar" --no-map

Runs under both Python 2.7 (ArcGIS) and Python 3.
"""

from __future__ import unicode_literals, print_function

import argparse
import os
import sys

# Make the package importable when launched as a loose script.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from config import settings
from src import massif_scanner
from src import processor
from src.logger import get_logger


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Chust District Electronic Land Balance batch processor.")
    parser.add_argument("--root", required=True,
                        help="Root folder that contains the massif folders.")
    parser.add_argument("--massif", default=None,
                        help="Process only this massif (registry key or code).")
    parser.add_argument("--scan-only", action="store_true",
                        help="Only scan and list discovered massifs.")
    parser.add_argument("--no-map", action="store_true",
                        help="Skip cartographic map (PDF/JPG) export.")
    parser.add_argument("--no-report", action="store_true",
                        help="Skip balance report generation.")
    args = parser.parse_args(argv)

    root = os.path.abspath(args.root)
    log_dir = os.path.join(root, settings.LOG_DIRNAME)
    log = get_logger("chust_cli", log_dir)

    if not os.path.isdir(root):
        log.error("Root folder does not exist: %s", root)
        return 2

    datasets = massif_scanner.scan_root(root, log)
    if not datasets:
        log.error("No massif data sets found under %s", root)
        return 1

    if args.massif:
        sel = args.massif.strip().lower()
        datasets = [d for d in datasets
                    if (d.key and d.key.lower() == sel)
                    or (d.code and d.code == args.massif.strip())]
        if not datasets:
            log.error("No massif matched '%s'.", args.massif)
            return 1

    if args.scan_only:
        print("\nDiscovered massifs:")
        for d in datasets:
            print("  [%s] %-14s mdb=%-3s excel=%d mxd=%s  (%s)" % (
                d.code or "--", d.name,
                "yes" if d.mdb else "NO", len(d.excels),
                "yes" if d.mxd else "no", d.folder))
        return 0

    def _progress(pct, msg):
        print("  %3d%%  %s" % (pct, msg))

    outcome = processor.process_district(
        datasets, root, log, _progress,
        make_map=not args.no_map, make_report=not args.no_report)

    print("\n================ SUMMARY ================")
    for res in outcome["results"]:
        status = "OK " if res.success else "FAIL"
        extra = ""
        if res.balance is not None:
            extra = " total=%.2f ha" % res.balance.headline()["total_area"]
        print("  [%s] %-14s %s (%.1fs)%s"
              % (status, res.name,
                 ",".join(sorted(res.outputs.keys())) or "-",
                 res.duration, extra))
        for e in res.errors:
            print("        ERROR: %s" % e)
    if outcome["district_outputs"]:
        print("  District summary: %s"
              % ", ".join(outcome["district_outputs"].values()))
    ok = sum(1 for r in outcome["results"] if r.success)
    print("  %d/%d massifs succeeded." % (ok, len(outcome["results"])))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
