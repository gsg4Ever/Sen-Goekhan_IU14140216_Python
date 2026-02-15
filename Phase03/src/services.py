from __future__ import annotations

# -----------------------------------------------------------------------------
# Service-Schicht (Anwendungsfälle + KPI-Berechnung)
# -----------------------------------------------------------------------------
# Diese Schicht kapselt die fachliche Logik und stellt eine stabile API für die UI bereit.
#
# Architektur-Regel (Tutor-Feedback):
# - UI spricht nur mit Services.
# - Services orchestrieren Use-Cases und nutzen Repositories.
# - Repositories kapseln SQL und nutzen `DatabaseProtocol` für den DB-Zugriff.
#
# Ausnahme (bewusst): `DashboardService.bootstrap()` fungiert als „Composition Root“
# für den Prototypen. Dort werden DB-Verbindung/Schema initialisiert und Repositories
# instanziiert. Die eigentliche Fachlogik (CRUD/KPI) nutzt weiterhin nur Repositories.
# -----------------------------------------------------------------------------


"""Service-Schicht des Studien-Dashboards (Phase 3).

Zweck:
    Kapselt die fachliche Logik der Anwendung: Use-Cases (CRUD) und KPI-Berechnung.
    Die UI ruft ausschließlich Methoden dieser Schicht auf.

Architektur:
    - UI → Services → Repositories → Datenbank
    - Repositories kapseln SQL und arbeiten gegen `DatabaseProtocol`.

Hinweise:
    `DashboardService.bootstrap()` fungiert im Prototyp als „Composition Root“:
    DB-Verbindung/Schemainit werden dort erstellt, damit die UI keinerlei DB-Wissen benötigt.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Optional

from Phase03.src.db import connect, create_schema
from Phase03.src.db_protocol import DatabaseProtocol
from Phase03.src.models import Modul, ModulBelegung, Student, Studiengang
from Phase03.src.repositories import (
    ModulBelegungRepository,
    ModulRepository,
    StudentRepository,
    StudiengangRepository,
)


@dataclass(slots=True)
class DashboardKPIs:
    """
    Aggregierte KPIs, die im Dashboard angezeigt werden.
    
    Zweck:
        Bündelt alle Kennzahlen, die die UI in Kopfzeile/Diagrammen darstellt.
    
    Begriffe (zur Vermeidung von Missverständnissen):
        - ist_studienende: Datum der letzten bestandenen Prüfung (falls vorhanden)
        - soll_studienende: Zieltermin aus Startdatum + Soll-Dauer
        - prognose_studienende: Hochrechnung des Enddatums auf Basis der aktuellen Pace (ECTS-gewichtet)
    """

    fortschritt_ects: float
    ist_durchschnittsnote: Optional[float]
    ist_studiendauer_jahre: float
    delta_studiendauer_jahre: float

    # Datum der letzten bestandenen Prüfung (falls vorhanden)
    ist_studienende: Optional[date]

    # Ziel-/Soll-Enddatum (aus Soll-Semestern bzw. Soll-Dauer)
    soll_studienende: Optional[date]

    # Prognose-Enddatum (ECTS-gewichtete Pace) + Abweichung zum Soll (in Tagen)
    prognose_studienende: Optional[date]
    delta_studienende_tage: Optional[int]

    # Alternative Prognose (Plan ab jetzt): Soll-Ende + Verzögerung bis heute
    prognose_studienende_plan: Optional[date]
    delta_studienende_plan_tage: Optional[int]
    verzug_bisher_tage: Optional[int]

    # Transparenz: Ziel-ECTS vs. erledigte ECTS (für Interpretation)
    ziel_ects: float
    erledigt_ects: float



class DashboardService:
    """
    Fassade für alle Anwendungsfälle der Anwendung.
    
    Zweck:
        Stellt eine stabile API für die UI bereit. Die GUI kennt nur diese Klasse und
        greift weder direkt auf Repositories noch auf SQL zu.
    
    Hinweise:
        - `bootstrap()` erzeugt DB + Repositories (Prototyp/Composition Root).
        - CRUD-Methoden delegieren an Repositories.
        - KPI-Methoden berechnen Kennzahlen und liefern Plot-Serien für Matplotlib.
    """

    def __init__(
        self,
        db: DatabaseProtocol,
        modul_repo: ModulRepository,
        belegung_repo: ModulBelegungRepository,
        student_repo: StudentRepository,
        studiengang_repo: StudiengangRepository,
        *,
        owns_db: bool = False,
    ) -> None:
        """
        Initialisiert den Service.
        
        Zweck:
            Speichert Repositories und merkt sich optional, ob die DB vom Service verwaltet wird.
        
        Parameter:
            db (DatabaseProtocol): Datenbank-Adapter.
            modul_repo (ModulRepository): Zugriff auf Modultabelle.
            belegung_repo (ModulBelegungRepository): Zugriff auf Belegungen.
            student_repo (StudentRepository): Zugriff auf Student-Stammdaten.
            studiengang_repo (StudiengangRepository): Zugriff auf Studiengang-Stammdaten.
            owns_db (bool): Wenn True, wird die DB bei `close()` geschlossen.
        """

        self._db = db
        self._owns_db = owns_db

        self.modul_repo = modul_repo
        self.belegung_repo = belegung_repo
        self.student_repo = student_repo
        self.studiengang_repo = studiengang_repo

    # -----------------------------
    # Factory helpers
    # -----------------------------
    @classmethod
    def from_db(cls, db: DatabaseProtocol, *, owns_db: bool = False) -> "DashboardService":
        """
        Erzeugt einen Service für ein bereits existierendes DB-Objekt.
        
        Zweck:
            Erstellt die benötigten Repositories für die gegebene DB-Instanz.
        
        Parameter:
            db (DatabaseProtocol): Geöffnete Datenbank.
            owns_db (bool): Ob der Service die DB später selbst schließen soll.
        
        Rückgabe:
            DashboardService: Fertig konfigurierter Service.
        """

        return cls(
            db=db,
            modul_repo=ModulRepository(db),
            belegung_repo=ModulBelegungRepository(db),
            student_repo=StudentRepository(db),
            studiengang_repo=StudiengangRepository(db),
            owns_db=owns_db,
        )

    @classmethod
    def bootstrap(
        cls,
        *,
        db_path: Optional[str] = None,
        reset_db: bool = False,
    ) -> "DashboardService":
        """
        Bootstrapt die Anwendung (DB öffnen + Schema anlegen).
        
        Zweck:
            Erstellt eine DB-Verbindung (optional mit Pfad), legt das Schema an und gibt einen
            einsatzbereiten Service zurück.
        
        Parameter:
            db_path (str | None): Optionaler Pfad zur SQLite-Datei.
            reset_db (bool): Wenn True, werden Tabellen vor dem Anlegen gelöscht (Demo/Test).
        
        Rückgabe:
            DashboardService: Fertig konfigurierter Service.
        
        Hinweise:
            Für Persistenz über Neustarts sollte `reset_db=False` bleiben (Standard im UI).
        """

        db = connect(db_path)
        create_schema(db, reset_db=reset_db)
        return cls.from_db(db, owns_db=True)

    def close(self) -> None:
        """
        Schließt die DB-Verbindung (nur wenn der Service sie besitzt).
        
        Zweck:
            Verhindert Resource-Leaks, wenn die GUI beendet wird.
        """

        if self._owns_db:
            self._db.close()

    # -----------------------------
    # Demo/bootstrap data (Student + Studiengang)
    # -----------------------------
    def ensure_demo_data(self) -> tuple[int, int, Studiengang]:
        """
        Stellt sicher, dass Demo-Student und -Studiengang existieren.
        
        Zweck:
            Der Prototyp soll ohne zusätzliche Einrichtung laufen. Falls noch keine Daten existieren,
            werden ein Student und ein Studiengang angelegt.
        
        Rückgabe:
            tuple[int, int, Studiengang]: (student_id, studiengang_id, studiengang_model)
        """

        student = Student(vorname="Goekhan", nachname="Sen", matrikelnummer="IU14140216")
        student_id = self.student_repo.upsert(student)

        existing = self.studiengang_repo.get_latest_for_student(student_id)
        if existing:
            sg_id, sg = existing
            return student_id, sg_id, sg

        sg = Studiengang(
            name="Angewandte Kuenstliche Intelligenz",
            start_datum=date(2025, 6, 1),
            soll_studiensemester=6,
            soll_durchschnittsnote=2.0,
        )
        sg_id = self.studiengang_repo.create(student_id, sg)
        return student_id, sg_id, sg

    def update_studiengang(self, studiengang_id: int, sg: Studiengang) -> None:
        """
        Speichert Änderungen am aktuellen Studiengang.
        
        Parameter:
            studiengang_id (int): Primärschlüssel des Studiengangs.
            sg (Studiengang): Neue Studiengangsdaten.
        """

        self.studiengang_repo.update(studiengang_id, sg)

    # -----------------------------
    # Modul master data
    # -----------------------------
    def create_modul(
        self,
        titel: str,
        ects: int,
        plan_semester_nr: int,
        default_soll_bestanden_am: Optional[date],
    ) -> int:
        """
        Legt ein neues Modul im Modulkatalog an.
        
        Zweck:
            Erstellt ein `Modul`-Objekt und delegiert die Persistenz an das Modul-Repository.
        
        Parameter:
            titel (str): Modultitel.
            ects (int): ECTS-Punkte.
            plan_semester_nr (int): Geplantes Semester.
            default_soll_bestanden_am (date | None): Optionales Standard-Soll-Datum.
        
        Rückgabe:
            int: Primärschlüssel `modul_id`.
        """

        m = Modul(
            modul_id=None,
            titel=titel,
            ects=ects,
            plan_semester_nr=plan_semester_nr,
            default_soll_bestanden_am=default_soll_bestanden_am,
        )
        return self.modul_repo.create(m)

    def list_module(self) -> list[tuple[int, str]]:
        """
        Liefert die Modulliste für die Combobox.
        
        Rückgabe:
            list[tuple[int, str]]: Paare aus (modul_id, titel).
        """

        rows = self.modul_repo.list_all()
        return [(int(r["modul_id"]), str(r["titel"])) for r in rows]

    def get_modul_by_id(self, modul_id: int) -> Optional[Modul]:
        """
        Lädt ein Modul anhand seiner ID.
        
        Zweck:
            Wird u. a. beim Laden einer Belegung in das Formular verwendet.
        
        Parameter:
            modul_id (int): Primärschlüssel des Moduls.
        
        Rückgabe:
            Modul | None: Modul oder `None`.
        """

        return self.modul_repo.get_by_id(modul_id)

    # -----------------------------
    # ModulBelegung CRUD
    # -----------------------------
    def list_latest_belegungen(self, studiengang_id: int, *, limit: int = 200) -> list[Any]:
        """
        Liefert die zuletzt angelegten Belegungen für die Tabellenansicht.
        
        Parameter:
            studiengang_id (int): Kontext-Studiengang.
            limit (int): Maximale Anzahl Zeilen.
        
        Rückgabe:
            list[Any]: DB-Rows (inkl. Modultitel/ECTS via Join).
        """

        return self.belegung_repo.list_latest(studiengang_id, limit=limit)

    def create_belegung(self, belegung: ModulBelegung) -> int:
        """
        Legt eine neue Modulbelegung an (CRUD: Create).
        
        Parameter:
            belegung (ModulBelegung): Neue Belegung.
        
        Rückgabe:
            int: Primärschlüssel `belegung_id`.
        """

        return self.belegung_repo.create(belegung)

    def get_belegung(self, studiengang_id: int, belegung_id: int) -> Optional[ModulBelegung]:
        """
        Lädt eine Modulbelegung (CRUD: Read).
        
        Parameter:
            studiengang_id (int): Kontext-Studiengang.
            belegung_id (int): Primärschlüssel.
        
        Rückgabe:
            ModulBelegung | None: Belegung oder `None`.
        """

        return self.belegung_repo.get(studiengang_id, belegung_id)

    def update_belegung(self, belegung: ModulBelegung) -> None:
        """
        Aktualisiert eine Modulbelegung (CRUD: Update).
        
        Parameter:
            belegung (ModulBelegung): Belegung mit gesetzter `belegung_id`.
        """

        self.belegung_repo.update(belegung)

    def delete_belegung(self, studiengang_id: int, belegung_id: int) -> None:
        """
        Löscht eine Modulbelegung (CRUD: Delete).
        
        Parameter:
            studiengang_id (int): Kontext-Studiengang.
            belegung_id (int): Primärschlüssel.
        """

        self.belegung_repo.delete(studiengang_id, belegung_id)

    # -----------------------------
    # KPI
    # -----------------------------
    def compute_kpis(
        self,
        studiengang_id: int,
        *,
        start_datum: date,
        soll_dauer_jahre: float,
        soll_studiensemester: Optional[int] = None,
        ects_pro_semester: int = 30,
    ) -> DashboardKPIs:
        """
        Berechnet zentrale KPIs für einen Studiengang.
        
        Zweck:
            Ermittelt Fortschritt (ECTS), Durchschnittsnote sowie Zeitkennzahlen (Ist/Soll/Prognose).
        
        Parameter:
            studiengang_id (int): Kontext-Studiengang.
            start_datum (date): Startdatum des Studiums.
            soll_dauer_jahre (float): Soll-Studiendauer in Jahren.
            soll_studiensemester (int | None): Optionales Ziel in Semestern (zur Ziel-ECTS-Bestimmung).
            ects_pro_semester (int): Annahme für Ziel-ECTS (Default: 30).
        
        Rückgabe:
            DashboardKPIs: Aggregierte Kennzahlen.
        
        Hinweise:
            Die Prognose basiert auf der aktuellen Pace (verstrichene Zeit relativ zu erreichten ECTS).
            Zusätzlich wird das Datum der letzten bestandenen Prüfung separat ausgewiesen.
        """

        # Ziel-ECTS stabil bestimmen:
        # Wenn noch nicht alle Module im System angelegt sind, wäre eine Prognose auf Basis
        # von `SUM(ECTS aus Modul-Tabelle)` irreführend (-> Fortschritt 100% und viel zu frühe Prognose).
        #
        # Daher: Wenn Soll-Semester bekannt sind, leiten wir die Ziel-ECTS standardmäßig mit
        # 30 ECTS/Semester ab (IU-typisch). Andernfalls fällt es auf die im System angelegten
        # Modul-ECTS zurück.
        ziel_ects = 0.0
        if soll_studiensemester is not None and int(soll_studiensemester) > 0:
            ziel_ects = float(int(soll_studiensemester) * int(ects_pro_semester))
        if ziel_ects <= 0:
            ziel_ects = float(self.modul_repo.get_total_ects())

        erledigt_ects = float(self.belegung_repo.sum_ects_completed(studiengang_id))
        fortschritt = (erledigt_ects / ziel_ects) if ziel_ects > 0 else 0.0

        avg = self.belegung_repo.avg_grade_weighted(studiengang_id)
        last_passed = self.belegung_repo.last_completion_date(studiengang_id)

        # Falls keine Soll-Dauer übergeben wurde, kann diese aus Soll-Semestern abgeleitet werden.
        # Standardannahme: 2 Semester entsprechen 1 Jahr.
        if (not soll_dauer_jahre or float(soll_dauer_jahre) <= 0.0) and soll_studiensemester is not None:
            soll_dauer_jahre = float(soll_studiensemester) / 2.0

        # Soll-Enddatum (falls Soll-Dauer bekannt)
        soll_end: Optional[date]
        if soll_dauer_jahre and float(soll_dauer_jahre) > 0:
            soll_end = start_datum + timedelta(days=int(round(float(soll_dauer_jahre) * 365.25)))
        else:
            soll_end = None

        # Referenzdatum für die "Ist"-Dauer / Pace:
        # - Wenn alles erledigt ist, nimm die letzte bestandene Prüfung.
        # - Sonst: nimm das heutige Datum, um die aktuelle Pace abzubilden.
        if ziel_ects > 0 and erledigt_ects >= ziel_ects and last_passed is not None:
            ref_date = last_passed
        else:
            ref_date = date.today()

        elapsed_days = max(0, (ref_date - start_datum).days)

        # Ist-Dauer (in Jahren) + Delta zur Soll-Dauer
        ist_dauer_jahre = (elapsed_days / 365.25) if elapsed_days > 0 else 0.0
        delta_dauer = ist_dauer_jahre - float(soll_dauer_jahre or 0.0)

        # Prognose-Enddatum (Trend/ Pace, ECTS-gewichtet):
        # Wenn du *schneller* als geplant bist, kann diese Prognose auch *vor* dem Soll-Ende liegen.
        # Wenn du *langsamer* bist, liegt sie entsprechend dahinter.
        prognose_end: Optional[date] = None
        delta_end_days: Optional[int] = None
        if erledigt_ects > 0 and ziel_ects > 0:
            pace_days_per_ects = elapsed_days / erledigt_ects
            prognose_total_days = int(round(pace_days_per_ects * ziel_ects))
            prognose_end = start_datum + timedelta(days=prognose_total_days)
            if soll_end is not None:
                delta_end_days = (prognose_end - soll_end).days

        # Alternative Prognose (Plan ab jetzt):
        # -> Soll-Ende + Verzögerung bis heute (für offene Module wird damit implizit Delta=0 angenommen).
        prognose_plan: Optional[date] = None
        delta_plan_days: Optional[int] = None
        verzug_bisher: Optional[int] = None
        if soll_end is not None and ziel_ects > 0:
            soll_total_days = max(0, (soll_end - start_datum).days)
            planned_days_per_ects = (soll_total_days / ziel_ects) if ziel_ects > 0 else 0.0
            expected_elapsed_days = planned_days_per_ects * erledigt_ects
            verzug_bisher = int(round(elapsed_days - expected_elapsed_days))
            prognose_plan = soll_end + timedelta(days=verzug_bisher)
            delta_plan_days = (prognose_plan - soll_end).days
        return DashboardKPIs(
            fortschritt_ects=fortschritt,
            ist_durchschnittsnote=avg,
            ist_studiendauer_jahre=ist_dauer_jahre,
            delta_studiendauer_jahre=delta_dauer,
            ist_studienende=last_passed,
            soll_studienende=soll_end,
            prognose_studienende=prognose_end,
            delta_studienende_tage=delta_end_days,

            prognose_studienende_plan=prognose_plan,
            delta_studienende_plan_tage=delta_plan_days,
            verzug_bisher_tage=verzug_bisher,

            ziel_ects=ziel_ects,
            erledigt_ects=erledigt_ects,
        )

    # -----------------------------
    # Plot data (UI does matplotlib)
    # -----------------------------
    def get_series_ist_soll_note_pro_modul(self, studiengang_id: int) -> list[tuple[str, float | None, float | None]]:
        """
        Datenserie für Soll-/Ist-Note je Modul (Plot 1).
        
        Zweck:
            Liefert pro Modul die aktuellste Belegung und extrahiert Soll-/Ist-Noten für eine Balken-/Punktdarstellung.
        
        Parameter:
            studiengang_id (int): Kontext-Studiengang.
        
        Rückgabe:
            list[Any]: Row-Objekte aus `ModulBelegungRepository.plot_latest_per_module()`.
        """

        rows = self.belegung_repo.plot_latest_per_module(studiengang_id)
        out: list[tuple[str, float | None, float | None]] = []
        for r in rows:
            label = f"#{r['modul_id']} {r['titel']}"
            ist = float(r["ist_note"]) if r["ist_note"] is not None else None
            soll = float(r["soll_note"]) if r["soll_note"] is not None else None
            out.append((label, ist, soll))
        return out

    def get_series_zeitabweichung_pro_modul(self, studiengang_id: int) -> list[tuple[str, int]]:
        """
        Datenserie für Zeitabweichung je Modul (Plot 2).
        
        Zweck:
            Liefert pro Modul die Abweichung in Tagen (Ist-Datum minus Soll-Datum), sofern beide Datumswerte vorliegen.
        
        Parameter:
            studiengang_id (int): Kontext-Studiengang.
        
        Rückgabe:
            list[Any]: Row-Objekte (inkl. `delta_days`).
        """

        rows = self.belegung_repo.plot_latest_per_module(studiengang_id)
        out: list[tuple[str, int]] = []
        for r in rows:
            if r["delta_days"] is None:
                continue
            out.append((str(r["titel"]), int(r["delta_days"])))
        return out

    def get_series_ects_fortschritt_ueber_zeit(self, studiengang_id: int) -> list[tuple[date, float]]:
        """
        Datenserie für kumulative ECTS über die Zeit (Plot 3).
        
        Zweck:
            Liefert Zeitreihendaten aller bestandenen Module, sortiert nach Bestehensdatum.
        
        Parameter:
            studiengang_id (int): Kontext-Studiengang.
        
        Rückgabe:
            list[Any]: Row-Objekte mit Datum/ECTS/Note.
        """

        rows = self.belegung_repo.plot_completions(studiengang_id)
        by_date: dict[date, float] = {}
        for r in rows:
            d = date.fromisoformat(str(r["ist_bestanden_am"]))
            by_date[d] = by_date.get(d, 0.0) + float(r["ects"] or 0.0)

        cum = 0.0
        out: list[tuple[date, float]] = []
        for d in sorted(by_date):
            cum += by_date[d]
            out.append((d, cum))
        return out

    def get_series_durchschnittsnote_ueber_zeit(self, studiengang_id: int) -> list[tuple[date, float]]:
        """
        Datenserie für Durchschnittsnote über die Zeit (Plot 4).
        
        Zweck:
            Liefert die gleiche Basis wie ECTS-Zeitreihe und wird in der UI zu einer
            fortlaufenden (ECTS-gewichteten) Durchschnittsnote aggregiert.
        
        Parameter:
            studiengang_id (int): Kontext-Studiengang.
        
        Rückgabe:
            list[Any]: Row-Objekte mit Datum/ECTS/Note.
        """

        rows = self.belegung_repo.plot_completions(studiengang_id)
        events: list[tuple[date, float, float]] = []
        for r in rows:
            if r["ist_note"] is None:
                continue
            d = date.fromisoformat(str(r["ist_bestanden_am"]))
            events.append((d, float(r["ects"] or 0.0), float(r["ist_note"])))
        events.sort(key=lambda x: x[0])

        per_day: dict[date, tuple[float, float]] = {}
        for d, ects, grade in events:
            e, w = per_day.get(d, (0.0, 0.0))
            per_day[d] = (e + ects, w + ects * grade)

        cum_ects = 0.0
        cum_weight = 0.0
        out: list[tuple[date, float]] = []
        for d in sorted(per_day):
            e, w = per_day[d]
            cum_ects += e
            cum_weight += w
            if cum_ects > 0:
                out.append((d, cum_weight / cum_ects))
        return out