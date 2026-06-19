# -*- coding: utf-8 -*-
"""
Desktop GUI (Tkinter) for the Chust District Electronic Land Balance system.

Functions exposed to the user:
    * Select the root folder containing the massif folders.
    * Detect / list all massifs (with data-readiness status).
    * Run processing (single massif or whole district) on a background thread.
    * Live progress bar + scrolling log.
    * Preview results (open the generated JPG / HTML / output folder).
    * Export reports (same as run, with map/report toggles).

Tkinter is bundled with the ArcGIS Desktop Python 2.7 install, so the GUI has
no third-party dependency.  Written to run on Python 2.7 and 3.
"""

from __future__ import unicode_literals

import os
import sys
import threading
import webbrowser

# Python 2 / 3 Tkinter compatibility ---------------------------------------
try:
    import Tkinter as tk
    import ttk
    import tkFileDialog as filedialog
    import tkMessageBox as messagebox
    import Queue as queue
except ImportError:                       # Python 3
    import tkinter as tk
    from tkinter import ttk
    from tkinter import filedialog
    from tkinter import messagebox
    import queue

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))      # package root
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from config import settings
from src import massif_scanner
from src import processor
from src.logger import get_logger


class QueueLogHandler(object):
    """Minimal logging-handler-like object that pushes records to a queue."""

    def __init__(self, q):
        self.q = q

    def __call__(self, message):
        self.q.put(("log", message))


class LandBalanceApp(object):
    def __init__(self, root):
        self.root = root
        self.root.title(settings.PROJECT_NAME)
        self.root.geometry("960x640")
        self.queue = queue.Queue()
        self.datasets = []
        self.worker = None
        self.last_outputs = {}

        self._build_ui()
        self.root.after(150, self._poll_queue)

    # ------------------------------------------------------------------
    def _build_ui(self):
        pad = {"padx": 6, "pady": 4}

        # --- top: folder selection ------------------------------------
        top = ttk.Frame(self.root)
        top.pack(fill="x", **pad)
        ttk.Label(top, text="Ildiz papka / Root folder:").pack(side="left")
        self.var_root = tk.StringVar()
        ttk.Entry(top, textvariable=self.var_root).pack(
            side="left", fill="x", expand=True, padx=6)
        ttk.Button(top, text="Tanlash / Browse...",
                   command=self._choose_folder).pack(side="left")
        ttk.Button(top, text="Aniqlash / Detect",
                   command=self._detect).pack(side="left", padx=4)

        # --- middle: massif table -------------------------------------
        mid = ttk.Frame(self.root)
        mid.pack(fill="both", expand=True, **pad)
        cols = ("code", "name", "mdb", "excel", "mxd", "status")
        self.tree = ttk.Treeview(mid, columns=cols, show="headings",
                                 selectmode="extended", height=10)
        headers = {
            "code": "Kod", "name": "Massiv", "mdb": ".mdb",
            "excel": "Excel", "mxd": ".mxd", "status": "Holat / Status",
        }
        widths = {"code": 50, "name": 200, "mdb": 60, "excel": 60,
                  "mxd": 60, "status": 320}
        for c in cols:
            self.tree.heading(c, text=headers[c])
            self.tree.column(c, width=widths[c],
                             anchor="center" if c != "name" and c != "status" else "w")
        self.tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(mid, orient="vertical", command=self.tree.yview)
        sb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=sb.set)

        # --- options --------------------------------------------------
        opts = ttk.Frame(self.root)
        opts.pack(fill="x", **pad)
        self.var_map = tk.BooleanVar(value=True)
        self.var_report = tk.BooleanVar(value=True)
        self.var_selected = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text="Xarita (PDF/JPG)", variable=self.var_map).pack(side="left")
        ttk.Checkbutton(opts, text="Hisobot (PDF/Excel/HTML)", variable=self.var_report).pack(side="left", padx=8)
        ttk.Checkbutton(opts, text="Faqat tanlanganlar / Selected only",
                        variable=self.var_selected).pack(side="left", padx=8)

        # --- action buttons -------------------------------------------
        act = ttk.Frame(self.root)
        act.pack(fill="x", **pad)
        self.btn_run = ttk.Button(act, text="Ishga tushirish / Run",
                                  command=self._run)
        self.btn_run.pack(side="left")
        ttk.Button(act, text="Natija papkasi / Open output",
                   command=self._open_output).pack(side="left", padx=6)
        ttk.Button(act, text="Ko'rish / Preview",
                   command=self._preview).pack(side="left")

        # --- progress + log -------------------------------------------
        prog = ttk.Frame(self.root)
        prog.pack(fill="x", **pad)
        self.progress = ttk.Progressbar(prog, maximum=100)
        self.progress.pack(side="left", fill="x", expand=True)
        self.var_status = tk.StringVar(value="Tayyor / Ready")
        ttk.Label(prog, textvariable=self.var_status, width=40).pack(side="left", padx=6)

        logframe = ttk.Frame(self.root)
        logframe.pack(fill="both", expand=True, **pad)
        self.log_text = tk.Text(logframe, height=10, wrap="word", state="disabled")
        self.log_text.pack(side="left", fill="both", expand=True)
        lsb = ttk.Scrollbar(logframe, orient="vertical", command=self.log_text.yview)
        lsb.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=lsb.set)

    # ------------------------------------------------------------------
    # actions
    # ------------------------------------------------------------------
    def _choose_folder(self):
        folder = filedialog.askdirectory(title="Ildiz papkani tanlang")
        if folder:
            self.var_root.set(folder)
            self._detect()

    def _detect(self):
        root = self.var_root.get().strip()
        if not root or not os.path.isdir(root):
            messagebox.showwarning("Diqqat", "Iltimos mavjud papkani tanlang.")
            return
        log = get_logger("chust_gui")
        self.datasets = massif_scanner.scan_root(root, log)
        for item in self.tree.get_children():
            self.tree.delete(item)
        for ds in self.datasets:
            status = self._readiness(ds)
            self.tree.insert("", "end", values=(
                ds.code or "--", ds.name,
                "yes" if ds.mdb else "NO",
                len(ds.excels),
                "yes" if ds.mxd else "no",
                status))
        self._log("Aniqlandi / detected %d massiv." % len(self.datasets))

    def _readiness(self, ds):
        if ds.mdb:
            return "Tayyor / ready"
        if ds.archives:
            return "Arxiv (ochiladi) / archive will be extracted"
        return "Geodatabaza yo'q / no .mdb"

    def _selected_datasets(self):
        if not self.var_selected.get():
            return list(self.datasets)
        sel = self.tree.selection()
        if not sel:
            return list(self.datasets)
        names = set(self.tree.item(i, "values")[1] for i in sel)
        return [d for d in self.datasets if d.name in names]

    def _run(self):
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Info", "Jarayon allaqachon ishlamoqda.")
            return
        root = self.var_root.get().strip()
        if not root or not os.path.isdir(root):
            messagebox.showwarning("Diqqat", "Iltimos ildiz papkani tanlang.")
            return
        if not self.datasets:
            self._detect()
        datasets = self._selected_datasets()
        if not datasets:
            messagebox.showwarning("Diqqat", "Massiv topilmadi.")
            return

        self.btn_run.configure(state="disabled")
        self.progress["value"] = 0
        self._log("=" * 50)
        self._log("Ishga tushdi / started: %d massiv" % len(datasets))

        make_map = self.var_map.get()
        make_report = self.var_report.get()

        def _work():
            def progress(pct, msg):
                self.queue.put(("progress", (pct, msg)))
            log = get_logger("chust_gui",
                             os.path.join(root, settings.LOG_DIRNAME))
            try:
                outcome = processor.process_district(
                    datasets, root, log, progress, make_map, make_report)
                self.queue.put(("done", outcome))
            except Exception as exc:
                self.queue.put(("error", "%s" % exc))

        self.worker = threading.Thread(target=_work)
        self.worker.setDaemon(True)
        self.worker.start()

    def _open_output(self):
        root = self.var_root.get().strip()
        if not root:
            return
        target = os.path.join(root, settings.DISTRICT_OUTPUT_DIRNAME)
        if not os.path.isdir(target):
            target = root
        self._open_path(target)

    def _preview(self):
        # Prefer a JPG preview, then an HTML report, from the last outputs.
        for key in ("jpg_preview", "html_report", "district_html",
                    "pdf_map", "pdf_report"):
            path = self.last_outputs.get(key)
            if path and os.path.exists(path):
                self._open_path(path)
                return
        messagebox.showinfo("Info", "Hali natija yo'q / no results yet.")

    def _open_path(self, path):
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)              # noqa - Windows only
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", path])
            else:
                webbrowser.open("file://%s" % path)
        except Exception as exc:
            messagebox.showerror("Xato", "Ochib bo'lmadi: %s" % exc)

    # ------------------------------------------------------------------
    # queue polling (thread -> UI)
    # ------------------------------------------------------------------
    def _poll_queue(self):
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == "log":
                    self._log(payload)
                elif kind == "progress":
                    pct, msg = payload
                    self.progress["value"] = pct
                    self.var_status.set(msg[:60])
                    self._log(msg)
                elif kind == "done":
                    self._on_done(payload)
                elif kind == "error":
                    self._log("ERROR: %s" % payload)
                    messagebox.showerror("Xato / Error", payload)
                    self.btn_run.configure(state="normal")
        except queue.Empty:
            pass
        self.root.after(150, self._poll_queue)

    def _on_done(self, outcome):
        self.btn_run.configure(state="normal")
        self.progress["value"] = 100
        results = outcome.get("results", [])
        ok = sum(1 for r in results if r.success)
        self.var_status.set("Tayyor / done: %d/%d" % (ok, len(results)))
        # collect outputs for preview
        self.last_outputs = {}
        for r in results:
            if r.success:
                self.last_outputs.update(r.outputs)
        self.last_outputs.update(outcome.get("district_outputs", {}))
        # update the status column
        by_name = dict((r.name, r) for r in results)
        for item in self.tree.get_children():
            vals = list(self.tree.item(item, "values"))
            r = by_name.get(vals[1])
            if r:
                if r.success:
                    extra = ""
                    if r.balance is not None:
                        extra = " (%.1f ga)" % r.balance.headline()["total_area"]
                    vals[5] = "OK%s" % extra
                else:
                    vals[5] = "XATO: %s" % ("; ".join(r.errors)[:60])
                self.tree.item(item, values=vals)
        self._log("Yakunlandi / finished: %d/%d massiv muvaffaqiyatli." % (ok, len(results)))
        messagebox.showinfo("Tayyor / Done",
                            "%d/%d massiv qayta ishlandi." % (ok, len(results)))

    def _log(self, message):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")


def main():
    root = tk.Tk()
    try:
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
    except Exception:
        pass
    LandBalanceApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
