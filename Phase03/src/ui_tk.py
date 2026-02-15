from __future__ import annotations

# -----------------------------------------------------------------------------
# UI layer (Tkinter + Matplotlib)
# -----------------------------------------------------------------------------
# Verantwortlich für:
# - Eingabe/Änderung/Löschen von ModulBelegungen (CRUD)
# - Anzeige der zentralen KPIs (Fortschritt, Durchschnittsnote, Studiendauer-Prognose)
# - Visualisierung als Diagramme
#
# Wichtig (Architekturregel):
# Die UI greift nicht direkt auf SQL/DB zu, sondern verwendet ausschließlich `DashboardService`.
#
# UML-Namensmapping:
# Im UML-Diagramm wird die UI-Klasse als `DashboardGUI` bezeichnet.
# In der Implementierung heißt die Klasse `DashboardApp` (funktional identisch).
# -----------------------------------------------------------------------------


from datetime import date
from tkinter import Tk, ttk, StringVar, messagebox, Toplevel

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.dates as mdates

from Phase03.src.models import ModulBelegung, Studiengang
from Phase03.src.services import DashboardService
from Phase03.src.validation import (
    ValidationError,
    parse_date,
    parse_int,
    parse_float,
    parse_optional_float,
    parse_optional_int,
)


class DashboardApp:
    """
    Tkinter-Hauptfenster des Prototyps (UI-Schicht).
    
    Zweck:
        Stellt Eingabemasken, Tabellenansicht und Diagramme bereit, um Modulbelegungen
        zu verwalten (CRUD) und zentrale KPIs zu visualisieren.
    
    Ablauf:
        1) Service bootstrappen (DB öffnen + Schema sicherstellen)
        2) Demo-Student/Studiengang anlegen (falls noch nicht vorhanden)
        3) Widgets aufbauen, Daten laden und Plots aktualisieren
    
    Hinweise:
        Architekturregel: Die UI greift nie direkt auf SQL/DB zu, sondern nutzt ausschließlich
        `DashboardService` als Schnittstelle zur Fachlogik.
    """

    def __init__(self, root: Tk) -> None:
        """
        Initialisiert das Hauptfenster und die Service-Anbindung.
        
        Zweck:
            Erstellt den `DashboardService`, lädt/erstellt Demo-Daten und baut anschließend
            die komplette Oberfläche auf.
        
        Parameter:
            root (Tk): Tkinter-Rootfenster.
        """

        self.root = root
        root.title("Studien-Dashboard Prototyp (Phase 3)")

        # WICHTIG: Standardmäßig wird eine persistente DB genutzt.
        # `reset_db=True` würde bei jedem Start alle Tabellen löschen und damit
        # sämtliche zuvor erfassten Daten verwerfen.
        self.svc = DashboardService.bootstrap(reset_db=False)
        _, self.studiengang_id, self.sg = self.svc.ensure_demo_data()

        # UI state
        self.modul_id_by_title: dict[str, int] = {}

        # UI initial aufbauen und anschließend Daten/Plots laden
        self._build_ui()
        self._reload_module_choices()
        self.refresh()

    # -----------------------------
    # UI build
    # -----------------------------
    def _build_ui(self) -> None:
        """
        Erzeugt und arrangiert alle Widgets der Oberfläche.
        
        Zweck:
            Baut die linke Seite (Formular + Tabelle) sowie die rechte Seite (Diagramme)
            und initialisiert die zugehörigen Tkinter-Variablen.
        """

        self.root.update_idletasks()
        # Bildschirmgröße ermitteln, um das Fenster initial sinnvoll zu dimensionieren
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w = min(1500, max(1150, sw - 80))
        h = min(900, max(700, sh - 120))
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 3)
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.minsize(1100, 650)

        # PanedWindow: links Formular/Tabelle, rechts Diagramme
        paned = ttk.Panedwindow(self.root, orient="horizontal")
        paned.pack(fill="both", expand=True)

        left = ttk.Frame(paned, padding=12)
        right = ttk.Frame(paned, padding=8)
        paned.add(left, weight=3)
        paned.add(right, weight=2)

        left.columnconfigure(1, weight=1)

        self.kpi_var = StringVar(value="")
        ttk.Label(left, textvariable=self.kpi_var, justify="left").grid(row=0, column=0, columnspan=3, sticky="w")

        # Studiengang settings (editable)
        self.v_sg_name = StringVar(value=self.sg.name)
        self.v_sg_start = StringVar(value=self.sg.start_datum.isoformat())
        self.v_sg_soll_sem = StringVar(value=str(self.sg.soll_studiensemester or ""))
        self.v_sg_soll_avg = StringVar(value=str(self.sg.soll_durchschnittsnote))

        # Belegung form fields
        self.v_belegung_id = StringVar(value="")
        self.v_modul_title = StringVar(value="")
        self.v_plan_sem = StringVar(value="1")
        self.v_ist_sem = StringVar(value="")
        self.v_soll_datum = StringVar(value="2025-06-30")
        self.v_ist_datum = StringVar(value="")
        self.v_soll_note = StringVar(value="2.0")
        self.v_ist_note = StringVar(value="")
        self.v_anzahl = StringVar(value="1")

        row = 1
        self._add_row(left, row, "Studiengang-Name", self.v_sg_name); row += 1
        self._add_row(left, row, "Startdatum (YYYY-MM-DD)", self.v_sg_start); row += 1
        self._add_row(left, row, "Soll-Semester", self.v_sg_soll_sem); row += 1
        self._add_row(left, row, "Soll-Durchschnittsnote", self.v_sg_soll_avg); row += 1

        cfg = ttk.Frame(left)
        cfg.grid(row=row, column=0, columnspan=3, sticky="e", pady=(4, 10))
        ttk.Button(cfg, text="Studiengang speichern", command=self.on_save_studiengang).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(cfg, text="Modul anlegen…", command=self.on_create_modul_dialog).grid(row=0, column=1)
        row += 1

        self._add_row(left, row, "Belegung-ID (für Update/Load)", self.v_belegung_id); row += 1

        ttk.Label(left, text="Modul (Auswahl)").grid(row=row, column=0, sticky="w", pady=2)
        self.modul_combo = ttk.Combobox(left, textvariable=self.v_modul_title, state="readonly")
        self.modul_combo.grid(row=row, column=1, sticky="ew", pady=2)
        row += 1

        self._add_row(left, row, "Plan-Semester", self.v_plan_sem); row += 1
        self._add_row(left, row, "Ist-Semester", self.v_ist_sem); row += 1
        self._add_row(left, row, "Soll-Datum bestanden", self.v_soll_datum); row += 1
        self._add_row(left, row, "Ist-Datum bestanden", self.v_ist_datum); row += 1
        self._add_row(left, row, "Soll-Note (Modul)", self.v_soll_note); row += 1
        self._add_row(left, row, "Ist-Note (Modul)", self.v_ist_note); row += 1
        self._add_row(left, row, "Anzahl Versuche", self.v_anzahl); row += 1

        btns = ttk.Frame(left)
        btns.grid(row=row, column=0, columnspan=3, sticky="e", pady=(8, 8))
        ttk.Button(btns, text="Create", command=self.on_create).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(btns, text="Load", command=self.on_load).grid(row=0, column=1, padx=(0, 6))
        ttk.Button(btns, text="Update", command=self.on_update).grid(row=0, column=2, padx=(0, 6))
        ttk.Button(btns, text="Delete", command=self.on_delete).grid(row=0, column=3, padx=(0, 6))
        ttk.Button(btns, text="Refresh", command=self.refresh).grid(row=0, column=4, padx=(0, 6))
        ttk.Button(btns, text="Close", command=self.on_close).grid(row=0, column=5)
        row += 1

        self.table = ttk.Treeview(
            left,
            columns=("belegung_id", "modul", "ects", "plan", "ist", "ist_datum", "ist_note", "soll_note", "versuche"),
            show="headings",
            height=10,
        )
        for col, title, width, anchor in [
            ("belegung_id", "ID", 55, "w"),
            ("modul", "Modul", 320, "w"),
            ("ects", "ECTS", 55, "center"),
            ("plan", "Plan", 55, "center"),
            ("ist", "Ist", 55, "center"),
            ("ist_datum", "Ist-Datum", 95, "center"),
            ("ist_note", "Ist-Note", 70, "center"),
            ("soll_note", "Soll-Note", 70, "center"),
            ("versuche", "Vers.", 55, "center"),
        ]:
            self.table.heading(col, text=title)
            self.table.column(col, width=width, anchor=anchor)

        self.table.grid(row=row, column=0, columnspan=3, sticky="nsew")
        left.rowconfigure(row, weight=1)
        self.table.bind("<<TreeviewSelect>>", self._on_table_select)

        # ---------------- Right side: plots (Phase-2 layout) ----------------
        right.rowconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        nb_top = ttk.Notebook(right)
        nb_top.grid(row=0, column=0, sticky="nsew", pady=(0, 8))

        tab_note = ttk.Frame(nb_top)
        tab_avg = ttk.Frame(nb_top)
        for t in (tab_note, tab_avg):
            t.rowconfigure(0, weight=1)
            t.columnconfigure(0, weight=1)
        nb_top.add(tab_note, text="Note pro Modul")
        nb_top.add(tab_avg, text="Ø-Note über Zeit")

        self._fig_note = Figure(figsize=(4, 2.6), dpi=100)
        self._ax_note = self._fig_note.add_subplot(111)
        self._canvas_note = FigureCanvasTkAgg(self._fig_note, master=tab_note)
        self._canvas_note.get_tk_widget().grid(row=0, column=0, sticky="nsew")

        self._fig_avg = Figure(figsize=(4, 2.6), dpi=100)
        self._ax_avg = self._fig_avg.add_subplot(111)
        self._canvas_avg = FigureCanvasTkAgg(self._fig_avg, master=tab_avg)
        self._canvas_avg.get_tk_widget().grid(row=0, column=0, sticky="nsew")

        nb_bottom = ttk.Notebook(right)
        nb_bottom.grid(row=1, column=0, sticky="nsew")

        tab_delta = ttk.Frame(nb_bottom)
        tab_ects = ttk.Frame(nb_bottom)
        for t in (tab_delta, tab_ects):
            t.rowconfigure(0, weight=1)
            t.columnconfigure(0, weight=1)
        nb_bottom.add(tab_delta, text="ΔTage pro Modul")
        nb_bottom.add(tab_ects, text="ECTS über Zeit")

        self._fig_delta = Figure(figsize=(4, 2.6), dpi=100)
        self._ax_delta = self._fig_delta.add_subplot(111)
        self._canvas_delta = FigureCanvasTkAgg(self._fig_delta, master=tab_delta)
        self._canvas_delta.get_tk_widget().grid(row=0, column=0, sticky="nsew")

        self._fig_ects = Figure(figsize=(4, 2.6), dpi=100)
        self._ax_ects = self._fig_ects.add_subplot(111)
        self._canvas_ects = FigureCanvasTkAgg(self._fig_ects, master=tab_ects)
        self._canvas_ects.get_tk_widget().grid(row=0, column=0, sticky="nsew")

        nb_top.bind("<<NotebookTabChanged>>", lambda _e: self._safe_update_plots())
        nb_bottom.bind("<<NotebookTabChanged>>", lambda _e: self._safe_update_plots())

    def _add_row(self, parent: ttk.Frame, row: int, label: str, var: StringVar) -> None:
        """
        Hilfsfunktion zum Anlegen einer Label+Entry-Zeile.
        
        Zweck:
            Reduziert redundanten UI-Code beim Aufbau des Formulars.
        
        Parameter:
            parent: Container-Widget.
            row (int): Grid-Zeile.
            label (str): Beschriftung.
            var (StringVar): Gebundene Variable für das Entry-Feld.
        """

        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=2)
        ttk.Entry(parent, textvariable=var).grid(row=row, column=1, sticky="ew", pady=2)

    # -----------------------------
    # Module UI
    # -----------------------------
    def _reload_module_choices(self) -> None:
        """
        Aktualisiert die Modulauswahl der Combobox.
        
        Zweck:
            Lädt alle Module aus dem Service und baut das interne Mapping
            `titel -> modul_id` für spätere Aktionen auf.
        """

        modules = self.svc.list_module()
        self.modul_id_by_title = {title: mid for mid, title in modules}
        titles = [title for _, title in modules]
        self.modul_combo["values"] = titles
        if titles and (self.v_modul_title.get() not in titles):
            self.v_modul_title.set(titles[0])

    def on_create_modul_dialog(self) -> None:
        """
        Öffnet einen Dialog zum Anlegen eines neuen Moduls.
        
        Zweck:
            Erfasst Modul-Stammdaten (Titel/ECTS/Plansemester/optional Soll-Datum) und speichert
            diese über den Service. Danach wird die Modulliste der UI aktualisiert.
        """

        win = Toplevel(self.root)
        win.title("Modul anlegen")

        v_title = StringVar(value="")
        v_ects = StringVar(value="5")
        v_plan = StringVar(value="1")
        v_soll = StringVar(value="")  # optional

        frm = ttk.Frame(win, padding=12)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(1, weight=1)

        ttk.Label(frm, text="Titel").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Entry(frm, textvariable=v_title).grid(row=0, column=1, sticky="ew", pady=2)

        ttk.Label(frm, text="ECTS").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Entry(frm, textvariable=v_ects).grid(row=1, column=1, sticky="ew", pady=2)

        ttk.Label(frm, text="Plan-Semester").grid(row=2, column=0, sticky="w", pady=2)
        ttk.Entry(frm, textvariable=v_plan).grid(row=2, column=1, sticky="ew", pady=2)

        ttk.Label(frm, text="Default Soll-Datum (optional, YYYY-MM-DD)").grid(row=3, column=0, sticky="w", pady=2)
        ttk.Entry(frm, textvariable=v_soll).grid(row=3, column=1, sticky="ew", pady=2)

        btns = ttk.Frame(frm)
        btns.grid(row=4, column=0, columnspan=2, sticky="e", pady=(10, 0))

        def _save() -> None:
            try:
                title = v_title.get().strip()
                ects = parse_int(v_ects.get(), field="ECTS", min_value=1)
                plan = parse_int(v_plan.get(), field="Plan-Semester", min_value=1)
                soll_raw = v_soll.get().strip()
                soll = parse_date(soll_raw) if soll_raw else None

                self.svc.create_modul(title, ects, plan, soll)
                win.destroy()
                self._reload_module_choices()
                self.refresh()
            except Exception as exc:
                messagebox.showerror("Fehler", str(exc))

        ttk.Button(btns, text="Speichern", command=_save).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(btns, text="Abbrechen", command=win.destroy).grid(row=0, column=1)

    # -----------------------------
    # Studiengang
    # -----------------------------
    def _sg_from_form(self) -> Studiengang:
        """
        Erzeugt ein `Studiengang`-Objekt aus den Formularfeldern.
        
        Zweck:
            Liest Eingaben (Name/Start/Soll-Semester/Ziel-Ø-Note) aus und gibt ein neues
            `Studiengang`-Objekt zurück.
        
        Rückgabe:
            Studiengang: Studiengang basierend auf den UI-Feldern.
        
        Ausnahmen:
            ValidationError: Bei ungültigen Eingaben (z. B. Datum/Numbers).
        """

        name = self.v_sg_name.get().strip() or self.sg.name
        start = parse_date(self.v_sg_start.get())
        soll_sem = parse_int(self.v_sg_soll_sem.get(), field="Soll-Semester", min_value=1)
        soll_avg = parse_float(self.v_sg_soll_avg.get(), field="Soll-Durchschnittsnote", min_value=1.0, max_value=5.0)
        return Studiengang(name=name, start_datum=start, soll_studiensemester=soll_sem, soll_durchschnittsnote=soll_avg)

    def on_save_studiengang(self) -> None:
        """
        Speichert Studiengang-Änderungen aus der UI.
        
        Zweck:
            Validiert die Eingaben, persistiert sie über den Service und aktualisiert anschließend
            KPIs und Diagramme.
        """

        try:
            new_sg = self._sg_from_form()
            self.svc.update_studiengang(self.studiengang_id, new_sg)
            self.sg = new_sg
            self.refresh()
            messagebox.showinfo("OK", "Studiengang-Daten gespeichert.")
        except Exception as exc:
            messagebox.showerror("Fehler", str(exc))

    # -----------------------------
    # KPI header / plots
    # -----------------------------
    def _update_kpi_header(self) -> None:
        """
        Aktualisiert die KPI-Kopfzeile im UI.
        
        Zweck:
            Ruft `compute_kpis()` im Service auf und formatiert die Kennzahlen als Textblock
            für das Label im oberen Bereich.
        """

        # Soll-Studiendauer in Jahren aus Soll-Semestern ableiten (2 Semester = 1 Jahr).
        # Falls kein Soll-Semester gesetzt ist, bleibt die Soll-Dauer 0.0 (unbekannt).
        soll_dauer = float(self.sg.soll_studiensemester) / 2.0 if self.sg.soll_studiensemester is not None else 0.0
        k = self.svc.compute_kpis(
            self.studiengang_id,
            start_datum=self.sg.start_datum,
            soll_dauer_jahre=soll_dauer,
            soll_studiensemester=self.sg.soll_studiensemester,
        )

        avg = f"{k.ist_durchschnittsnote:.2f}" if k.ist_durchschnittsnote is not None else "-"
        last_passed = k.ist_studienende.isoformat() if k.ist_studienende else "-"
        soll_end = k.soll_studienende.isoformat() if k.soll_studienende else "-"
        prog_end = k.prognose_studienende.isoformat() if k.prognose_studienende else "-"
        delta_end = f"{k.delta_studienende_tage:+d} Tage" if k.delta_studienende_tage is not None else "-"

        plan_end = k.prognose_studienende_plan.isoformat() if k.prognose_studienende_plan else "-"
        verzug = f"{k.verzug_bisher_tage:+d} Tage" if k.verzug_bisher_tage is not None else "-"

        self.kpi_var.set(
            "\n".join(
                [
                    f"Studiengang: {self.sg.name}",
                    f"Fortschritt (ECTS): {k.fortschritt_ects:.1%}",
                    f"Ist-Durchschnittsnote: {avg} (Soll: {self.sg.soll_durchschnittsnote:.2f})",
                    f"Ist-Studiendauer: {k.ist_studiendauer_jahre:.2f} Jahre (Delta zu Soll: {k.delta_studiendauer_jahre:+.2f})",
                    f"Soll-Studienende: {soll_end}",
                    f"Prognose-Studienende (Pace, ECTS-gewichtet): {prog_end} (Delta zu Soll: {delta_end})",
                    f"Prognose-Studienende (Plan ab jetzt): {plan_end} (Verzug bisher: {verzug})",
                    f"ECTS: {k.erledigt_ects:.0f}/{k.ziel_ects:.0f}",
                    f"Letzte bestandene Prüfung: {last_passed}",
                ]
            )
        )

    def _clear_ax_with_message(self, ax, msg: str) -> None:
        """
        Leert eine Matplotlib-Achse und zeigt eine Statusmeldung.
        
        Zweck:
            Wird genutzt, um „keine Daten“ oder Fehlermeldungen lesbar im Plotbereich darzustellen.
        
        Parameter:
            ax: Matplotlib-Achse.
            msg (str): Anzuzeigender Text.
        """

        ax.clear()
        ax.text(0.5, 0.5, msg, ha="center", va="center", transform=ax.transAxes)
        ax.set_xticks([])
        ax.set_yticks([])

    def _safe_update_plots(self) -> None:
        """
        Aktualisiert Plots mit Fehlerbehandlung.
        
        Zweck:
            Verhindert, dass Plot-Fehler die GUI „abschießen“. Stattdessen wird eine
            verständliche Meldung in den Achsen dargestellt.
        """

        try:
            self._update_plots()
        except Exception as exc:
            messagebox.showerror("Plot-Fehler", str(exc))

    def _update_plots(self) -> None:
        # 1) Note pro Modul (Ist vs Soll)
        """
        Erzeugt/aktualisiert alle Diagramme.
        
        Zweck:
            Holt Datenserien über den Service und zeichnet:
            - Soll/Ist-Noten pro Modul
            - Zeitabweichung (Tage) pro Modul
            - ECTS-Fortschritt über Zeit
            - Durchschnittsnote über Zeit
        
        Hinweise:
            Die Plots werden bewusst in der UI erzeugt (Darstellung), die Daten kommen aus dem Service.
        """

        data1 = self.svc.get_series_ist_soll_note_pro_modul(self.studiengang_id)
        self._ax_note.clear()
        if not data1:
            self._clear_ax_with_message(self._ax_note, "Keine Noten-Daten vorhanden")
        else:
            labels = [x[0] for x in data1]
            ist_vals = [x[1] for x in data1]
            soll_vals = [x[2] for x in data1]
            short = [lbl[:22] + "…" if len(lbl) > 23 else lbl for lbl in labels]
            xs = list(range(len(labels)))
            width = 0.38
            ist_plot = [v if v is not None else 0.0 for v in ist_vals]
            soll_plot = [v if v is not None else 0.0 for v in soll_vals]
            self._ax_note.bar([x - width/2 for x in xs], ist_plot, width=width, label="Ist")
            self._ax_note.bar([x + width/2 for x in xs], soll_plot, width=width, label="Soll")
            self._ax_note.axhline(self.sg.soll_durchschnittsnote, linestyle="--", linewidth=1)
            self._ax_note.set_title("Note pro Modul (Ist / Soll)")
            self._ax_note.set_ylabel("Note")
            self._ax_note.set_xticks(xs)
            self._ax_note.set_xticklabels(short, rotation=45, ha="right")
            self._ax_note.set_ylim(1.0, 5.0)
            self._ax_note.invert_yaxis()
            self._ax_note.legend(loc="best")
        self._fig_note.tight_layout()
        self._canvas_note.draw()

        # 2) Ø-Note über Zeit
        data4 = self.svc.get_series_durchschnittsnote_ueber_zeit(self.studiengang_id)
        self._ax_avg.clear()
        if not data4:
            self._clear_ax_with_message(self._ax_avg, "Keine Noten-Zeitreihe vorhanden")
        else:
            xs = [d for d, _ in data4]
            ys = [v for _, v in data4]
            self._ax_avg.plot(xs, ys, marker="o", linewidth=1.5)
            self._ax_avg.axhline(self.sg.soll_durchschnittsnote, linestyle="--", linewidth=1)
            self._ax_avg.set_title("Ø-Note über Zeit")
            self._ax_avg.set_ylabel("Ø-Note")
            self._ax_avg.set_ylim(1.0, 5.0)
            self._ax_avg.invert_yaxis()
            self._ax_avg.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
            self._ax_avg.tick_params(axis="x", rotation=30)
        self._fig_avg.tight_layout()
        self._canvas_avg.draw()

        # 3) ΔTage pro Modul
        data2 = self.svc.get_series_zeitabweichung_pro_modul(self.studiengang_id)
        self._ax_delta.clear()
        if not data2:
            self._clear_ax_with_message(self._ax_delta, "Keine Termin-Daten vorhanden")
        else:
            labels = [x[0] for x in data2]
            values = [x[1] for x in data2]
            short = [lbl[:22] + "…" if len(lbl) > 23 else lbl for lbl in labels]
            self._ax_delta.bar(range(len(values)), values)
            self._ax_delta.axhline(0, linestyle="--", linewidth=1)
            self._ax_delta.set_title("ΔTage pro Modul (Ist − Soll)")
            self._ax_delta.set_ylabel("Tage")
            self._ax_delta.set_xticks(range(len(values)))
            self._ax_delta.set_xticklabels(short, rotation=45, ha="right")
        self._fig_delta.tight_layout()
        self._canvas_delta.draw()

        # 4) ECTS über Zeit
        data3 = self.svc.get_series_ects_fortschritt_ueber_zeit(self.studiengang_id)
        self._ax_ects.clear()
        if not data3:
            self._clear_ax_with_message(self._ax_ects, "Keine Zeitreihen-Daten vorhanden")
        else:
            xs = [d for d, _ in data3]
            ys = [v for _, v in data3]
            self._ax_ects.plot(xs, ys, marker="o", linewidth=1.5)
            self._ax_ects.set_title("ECTS über Zeit")
            self._ax_ects.set_ylabel("kumulierte ECTS")
            self._ax_ects.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
            self._ax_ects.tick_params(axis="x", rotation=30)
        self._fig_ects.tight_layout()
        self._canvas_ects.draw()

    # -----------------------------
    # CRUD
    # -----------------------------
    def _selected_modul_id(self) -> int:
        """
        Ermittelt die ausgewählte `modul_id` aus der Combobox.
        
        Rückgabe:
            int: Modul-ID der aktuellen Auswahl.
        
        Ausnahmen:
            ValidationError: Wenn kein Modul ausgewählt wurde oder die Zuordnung fehlt.
        """

        title = self.v_modul_title.get().strip()
        if not title or title not in self.modul_id_by_title:
            raise ValidationError("Bitte ein Modul auswählen (oder zuerst Modul anlegen).")
        return int(self.modul_id_by_title[title])

    def _build_belegung_from_form(self, belegung_id_required: bool = False) -> ModulBelegung:
        """
        Erzeugt eine `ModulBelegung` aus den Formularfeldern.
        
        Zweck:
            Parst/validiert die Eingaben (Semester, Datum, Noten, Versuche) und erstellt das
            Domänenobjekt, das anschließend über den Service gespeichert wird.
        
        Rückgabe:
            ModulBelegung: Belegung basierend auf den UI-Feldern.
        
        Ausnahmen:
            ValidationError: Bei ungültigen Eingaben.
        """

        belegung_id = self.v_belegung_id.get().strip()
        if belegung_id_required and not belegung_id:
            raise ValidationError("Bitte Belegung-ID setzen (Load oder Auswahl in der Tabelle).")

        modul_id = self._selected_modul_id()

        return ModulBelegung(
            belegung_id=parse_int(belegung_id, field="Belegung-ID", min_value=1) if belegung_id else None,
            studiengang_id=self.studiengang_id,
            modul_id=modul_id,
            plan_semester_nr=parse_int(self.v_plan_sem.get(), field="Plan-Semester", min_value=1),
            ist_semester_nr=parse_optional_int(self.v_ist_sem.get(), field="Ist-Semester", min_value=1),
            soll_bestanden_am=parse_date(self.v_soll_datum.get()),
            ist_bestanden_am=parse_date(self.v_ist_datum.get()),
            soll_note=parse_optional_float(self.v_soll_note.get(), field="Soll-Note (Modul)", min_value=1.0, max_value=5.0),
            ist_note=parse_optional_float(self.v_ist_note.get(), field="Ist-Note (Modul)", min_value=1.0, max_value=5.0),
            anzahl_versuche=parse_int(self.v_anzahl.get(), field="Anzahl Versuche", min_value=1),
        )

    def refresh(self) -> None:
        """
        Lädt Tabelle/KPIs neu und aktualisiert die Diagramme.
        
        Zweck:
            Zentraler Refresh nach CRUD-Operationen oder beim Start.
        """

        try:
            self.sg = self._sg_from_form()
        except Exception:
            pass
        self._update_kpi_header()
        self._reload_module_choices()

        for item in self.table.get_children():
            self.table.delete(item)

        rows = self.svc.list_latest_belegungen(self.studiengang_id, limit=200)
        for r in rows:
            self.table.insert(
                "",
                "end",
                values=(
                    r["belegung_id"],
                    f"#{r['modul_id']} {r['modul_titel']}",
                    r["ects"],
                    r["plan_semester_nr"],
                    r["ist_semester_nr"] or "",
                    r["ist_bestanden_am"] or "",
                    r["ist_note"] if r["ist_note"] is not None else "",
                    r["soll_note"] if r["soll_note"] is not None else "",
                    r["anzahl_versuche"],
                ),
            )

        self._safe_update_plots()

    def on_create(self) -> None:
        """
        Event-Handler: Belegung anlegen (CRUD: Create).
        """

        try:
            b = self._build_belegung_from_form(belegung_id_required=False)
            new_id = self.svc.create_belegung(b)
            self.v_belegung_id.set(str(new_id))
            self.refresh()
        except Exception as exc:
            messagebox.showerror("Fehler", str(exc))

    def on_load(self) -> None:
        """
        Event-Handler: Belegung in Formular laden (CRUD: Read).
        
        Zweck:
            Lädt anhand der Belegung-ID den Datensatz und füllt die Eingabefelder, damit
            danach Update/Delete möglich sind.
        """

        try:
            belegung_id = parse_int(self.v_belegung_id.get(), field="Belegung-ID", min_value=1)
            b = self.svc.get_belegung(self.studiengang_id, belegung_id)
            if not b:
                raise ValidationError("Belegung nicht gefunden.")
            # select module title
            m = self.svc.get_modul_by_id(b.modul_id)
            if m:
                self.v_modul_title.set(m.titel)
            self.v_plan_sem.set(str(b.plan_semester_nr))
            self.v_ist_sem.set(str(b.ist_semester_nr or ""))
            self.v_soll_datum.set(b.soll_bestanden_am.isoformat() if b.soll_bestanden_am else "")
            self.v_ist_datum.set(b.ist_bestanden_am.isoformat() if b.ist_bestanden_am else "")
            self.v_soll_note.set(str(b.soll_note or ""))
            self.v_ist_note.set(str(b.ist_note or ""))
            self.v_anzahl.set(str(b.anzahl_versuche))
        except Exception as exc:
            messagebox.showerror("Fehler", str(exc))

    def on_update(self) -> None:
        """
        Event-Handler: Belegung aktualisieren (CRUD: Update).
        """

        try:
            b = self._build_belegung_from_form(belegung_id_required=True)
            self.svc.update_belegung(b)
            self.refresh()
        except Exception as exc:
            messagebox.showerror("Fehler", str(exc))

    def on_delete(self) -> None:
        """
        Event-Handler: Belegung löschen (CRUD: Delete).
        """

        try:
            belegung_id = parse_int(self.v_belegung_id.get(), field="Belegung-ID", min_value=1)
            if not messagebox.askyesno("Bestätigung", f"Belegung #{belegung_id} wirklich löschen?"):
                return
            self.svc.delete_belegung(self.studiengang_id, belegung_id)
            self.v_belegung_id.set("")
            self.refresh()
        except Exception as exc:
            messagebox.showerror("Fehler", str(exc))

    def _on_table_select(self, _evt=None) -> None:
        """
        Event-Handler: Tabellenzeile ausgewählt.
        
        Zweck:
            Übernimmt die ausgewählte Belegung-ID in das Eingabefeld, um Load/Update/Delete
            zu erleichtern.
        """

        sel = self.table.selection()
        if not sel:
            return
        values = self.table.item(sel[0], "values")
        if values:
            self.v_belegung_id.set(str(values[0]))

    def on_close(self) -> None:
        """
        Schließt die Anwendung kontrolliert.
        
        Zweck:
            Schließt Service/DB (falls nötig) und beendet das Tkinter-Fenster.
        """

        try:
            self.svc.close()
        finally:
            self.root.destroy()


def run() -> None:
    """
    Startet die Tkinter-GUI (Hilfsfunktion für main.py).
    
    Zweck:
        Erstellt das Root-Fenster, instanziiert `DashboardApp` und startet die Tkinter-Eventloop.
    """

    root = Tk()
    try:
        ttk.Style().theme_use("clam")
    except Exception:
        pass
    app = DashboardApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()