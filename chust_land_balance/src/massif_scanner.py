# -*- coding: utf-8 -*-
"""
Massif discovery.

Walks a root folder, finds every sub-folder that looks like a massif data set
and gathers the data files it contains (.mdb, .mxd, .lyr, .xls/.xlsx).  Each
discovered folder is matched against the 18-massif registry in
``config.settings`` so that the rest of the pipeline can refer to a massif by
its stable ``key`` / ``code`` regardless of how the operator named the folder.

No arcpy dependency - pure os/glob, unit-testable on any interpreter.
"""

from __future__ import unicode_literals

import os

from config import settings


# File extensions we care about, grouped by role.
_MDB_EXT = (".mdb",)
_MXD_EXT = (".mxd",)
_LYR_EXT = (".lyr",)
_XLS_EXT = (".xls", ".xlsx")
_ARCHIVE_EXT = (".7z", ".zip", ".rar")


class MassifDataset(object):
    """Everything we discovered about a single massif folder."""

    def __init__(self, folder, registry=None):
        self.folder = folder
        self.folder_name = os.path.basename(os.path.normpath(folder))
        self.registry = registry          # matching entry from settings.MASSIFS
        self.mdb = None
        self.mxd = None
        self.lyr = None
        self.excels = []
        self.archives = []

    # -- convenience accessors ------------------------------------------
    @property
    def code(self):
        return self.registry["code"] if self.registry else None

    @property
    def key(self):
        return self.registry["key"] if self.registry else _slug(self.folder_name)

    @property
    def name(self):
        return self.registry["name"] if self.registry else self.folder_name

    @property
    def name_cyr(self):
        return self.registry["name_cyr"] if self.registry else self.folder_name

    @property
    def has_geodatabase(self):
        return bool(self.mdb)

    @property
    def is_processable(self):
        """A massif can be processed if we found a geodatabase for it."""
        return self.has_geodatabase

    def primary_excel(self):
        """Best-guess contour statement workbook for this massif."""
        if not self.excels:
            return None
        # Prefer a workbook whose name contains the massif name/alias.
        candidates = []
        names = [self.name.lower(), self.key.lower()]
        if self.registry:
            names += [a.lower() for a in self.registry.get("aliases", [])]
            names.append(self.registry["name_cyr"].lower())
        for path in self.excels:
            base = os.path.basename(path).lower()
            score = sum(1 for n in names if n and n in base)
            candidates.append((score, -len(base), path))
        candidates.sort(reverse=True)
        return candidates[0][2]

    def describe(self):
        return {
            "folder": self.folder,
            "code": self.code,
            "key": self.key,
            "name": self.name,
            "mdb": self.mdb,
            "mxd": self.mxd,
            "lyr": self.lyr,
            "excels": list(self.excels),
            "archives": list(self.archives),
            "processable": self.is_processable,
        }


def _slug(text):
    out = []
    for ch in text.lower():
        if ch.isalnum():
            out.append(ch)
        elif out and out[-1] != "_":
            out.append("_")
    return "".join(out).strip("_") or "massif"


def _match_registry(folder_name):
    """Return the MASSIFS entry that best matches a folder name, or None."""
    low = folder_name.lower()
    best = None
    best_score = 0
    for entry in settings.MASSIFS:
        tokens = [entry["key"].lower(), entry["name"].lower(),
                  entry["name_cyr"].lower(), entry["code"]]
        tokens += [a.lower() for a in entry.get("aliases", [])]
        score = 0
        for tok in tokens:
            if not tok:
                continue
            if tok == low:
                score = max(score, 100)            # exact folder == token
            elif tok in low:
                score = max(score, 50 + len(tok))  # token contained
        # A leading ordinal like "001" or "011 Navoiy" is a strong signal.
        if low.startswith(entry["code"]):
            score = max(score, 90)
        if score > best_score:
            best_score = score
            best = entry
    return best if best_score > 0 else None


def _collect_files(folder):
    """Return dict of role -> list of file paths inside ``folder`` (shallow)."""
    found = {"mdb": [], "mxd": [], "lyr": [], "xls": [], "arch": []}
    try:
        entries = os.listdir(folder)
    except OSError:
        return found
    for name in entries:
        path = os.path.join(folder, name)
        if not os.path.isfile(path):
            continue
        low = name.lower()
        if low.endswith(_MDB_EXT):
            found["mdb"].append(path)
        elif low.endswith(_MXD_EXT):
            found["mxd"].append(path)
        elif low.endswith(_LYR_EXT):
            found["lyr"].append(path)
        elif low.endswith(_XLS_EXT):
            found["xls"].append(path)
        elif low.endswith(_ARCHIVE_EXT):
            found["arch"].append(path)
    return found


def _build_dataset(folder):
    files = _collect_files(folder)
    ds = MassifDataset(folder, _match_registry(os.path.basename(os.path.normpath(folder))))
    ds.mdb = files["mdb"][0] if files["mdb"] else None
    ds.mxd = files["mxd"][0] if files["mxd"] else None
    ds.lyr = files["lyr"][0] if files["lyr"] else None
    ds.excels = files["xls"]
    ds.archives = files["arch"]
    return ds


def scan_root(root, logger=None):
    """Scan ``root`` for massif data sets.

    A folder qualifies as a massif if it directly contains a geodatabase, a map
    document, a layer file, an Excel workbook or a recognised archive.  The root
    folder itself is also inspected (some users keep one massif at the top).

    Returns a list of :class:`MassifDataset`, ordered by registry ``code`` then
    folder name, with unmatched folders appended at the end.
    """
    datasets = []
    if not root or not os.path.isdir(root):
        if logger:
            logger.error("Root folder does not exist: %s", root)
        return datasets

    def _looks_like_massif(files):
        return any(files[k] for k in ("mdb", "mxd", "lyr", "xls", "arch"))

    # 1) the root itself
    root_files = _collect_files(root)
    if _looks_like_massif(root_files):
        datasets.append(_build_dataset(root))

    # 2) immediate sub-folders
    try:
        children = sorted(os.listdir(root))
    except OSError as exc:
        if logger:
            logger.error("Cannot list root folder %s: %s", root, exc)
        return datasets

    for name in children:
        sub = os.path.join(root, name)
        if not os.path.isdir(sub):
            continue
        # Skip output / log folders we generated ourselves.
        if name in (settings.OUTPUT_DIRNAME, settings.DISTRICT_OUTPUT_DIRNAME,
                    settings.LOG_DIRNAME):
            continue
        files = _collect_files(sub)
        if _looks_like_massif(files):
            datasets.append(_build_dataset(sub))

    # Sort: registered massifs by code, then unmatched alphabetically.
    def _sort_key(ds):
        if ds.registry:
            return (0, ds.registry["code"])
        return (1, ds.folder_name.lower())

    datasets.sort(key=_sort_key)

    if logger:
        logger.info("Scanned %s - found %d massif data set(s).", root, len(datasets))
        for ds in datasets:
            logger.info("  [%s] %s  (mdb=%s, excel=%d, mxd=%s)",
                        ds.code or "--", ds.name,
                        "yes" if ds.mdb else "NO",
                        len(ds.excels),
                        "yes" if ds.mxd else "no")
    return datasets
