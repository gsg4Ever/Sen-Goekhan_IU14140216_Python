from __future__ import annotations

from pathlib import Path

# Phase03: Gesamtarchitektur-UML (PlantUML)
# - Ziel: 1:1-Abbild der realen Klassen/Signaturen aus dem Code (UI/Service/Repo/Model/DB-Protocol)
# - Dieses Skript schreibt die UML-Datei `uml_class_diagram_architecture_phase3.puml` neben diesem Skript.

PUML = r'''@startuml
skinparam classAttributeIconSize 0
hide circle

' -------------------------
' UI
' -------------------------
package "UI" {
  class DashboardApp {
    +Modul anlegen Dialog
    +CRUD ModulBelegung: Create/Load/Update/Delete
    +Diagramme: Note/Ø-Note/ΔTage/ECTS

    +Studiengang bearbeiten (Name/Start/Soll)
    +Modul-Auswahl: Combobox (Titel -> modul_id)
  }
}

' -------------------------
' Service
' -------------------------
package "Service" {
  class DashboardService {
    <u>+from_db(db: DatabaseProtocol, owns_db: bool = False): DashboardService</u>
    <u>+bootstrap(db_path: str [0..1] = None, reset_db: bool = False): DashboardService</u>
    +close(): void

    +ensure_demo_data(): (student_id: int, studiengang_id: int, sg: Studiengang)
    +update_studiengang(studiengang_id: int, sg: Studiengang): void

    +create_modul(titel: str, ects: int, plan_semester_nr: int, default_soll_bestanden_am: date [0..1]): int
    +list_module(): List((modul_id: int, titel: str))
    +get_modul_by_id(modul_id: int): Modul [0..1]

    +list_latest_belegungen(studiengang_id: int, limit: int): List[Any]
    +create_belegung(belegung: ModulBelegung): int
    +get_belegung(studiengang_id: int, belegung_id: int): ModulBelegung [0..1]
    +update_belegung(belegung: ModulBelegung): void
    +delete_belegung(studiengang_id: int, belegung_id: int): void

    +compute_kpis(studiengang_id: int, start_datum: date, soll_dauer_jahre: float, soll_studiensemester: int [0..1], ects_pro_semester: int = 30): DashboardKPIs
    +get_series_ist_soll_note_pro_modul(studiengang_id: int): List((titel: str, ist_note: float [0..1], soll_note: float [0..1]))
    +get_series_zeitabweichung_pro_modul(studiengang_id: int): List((titel: str, delta_tage: int))
    +get_series_ects_fortschritt_ueber_zeit(studiengang_id: int): List((datum: date, ects_kumulativ: float))
    +get_series_durchschnittsnote_ueber_zeit(studiengang_id: int): List((datum: date, durchschnitt: float))
  }

  class DashboardKPIs {
    fortschritt_ects: float
    ist_durchschnittsnote: float [0..1]
    ist_studiendauer_jahre: float
    delta_studiendauer_jahre: float

    ist_studienende: date [0..1]
    soll_studienende: date [0..1]

    prognose_studienende: date [0..1]
    delta_studienende_tage: int [0..1]

    prognose_studienende_plan: date [0..1]
    delta_studienende_plan_tage: int [0..1]
    verzug_bisher_tage: int [0..1]

    ziel_ects: float
    erledigt_ects: float
  }
}

' -------------------------
' Repository / DB
' -------------------------
package "Repository" {
  interface CursorProtocol {
    +lastrowid: Any
    +fetchone(): Any
    +fetchall(): List[Any]
  }

  interface DatabaseProtocol {
    +execute(sql: str, params: Sequence[Any] = ()): CursorProtocol
    +executemany(sql: str, seq_of_params: Iterable[Sequence[Any]]): CursorProtocol
    +executescript(sql_script: str): void
    +commit(): void
    +rollback(): void
    +close(): void
  }

  class SQLiteDatabase

  class StudentRepository {
    +upsert(student: Student): int
  }

  class StudiengangRepository {
    +create(student_id: int, sg: Studiengang): int
    +get_latest_for_student(student_id: int): (studiengang_id: int, sg: Studiengang) [0..1]
    +update(studiengang_id: int, sg: Studiengang): void
  }

  class ModulRepository {
    +create(m: Modul): int
    +update_by_id(modul_id: int, m: Modul): void
    +get_by_id(modul_id: int): Modul [0..1]
    +get_by_title(titel: str): Modul [0..1]
    +list_all(): List[Any]
    +get_total_ects(): float
  }

  class ModulBelegungRepository {
    +create(b: ModulBelegung): int
    +get(studiengang_id: int, belegung_id: int): ModulBelegung [0..1]
    +update(b: ModulBelegung): void
    +delete(studiengang_id: int, belegung_id: int): void
    +list_latest(studiengang_id: int, limit: int = 200): List[Any]

    +sum_ects_completed(studiengang_id: int): float
    +avg_grade_weighted(studiengang_id: int): float [0..1]
    +last_completion_date(studiengang_id: int): date [0..1]

    +plot_latest_per_module(studiengang_id: int): List[Any]
    +plot_completions(studiengang_id: int): List[Any]
  }
}

' -------------------------
' Model
' -------------------------
package "Model" {
  class Student {
    vorname: str
    nachname: str
    matrikelnummer: str
    geburtsdatum: date [0..1]
    adresse: str [0..1]
  }

  class Studiengang {
    name: str
    start_datum: date
    soll_studiensemester: int [0..1]
    soll_durchschnittsnote: float
  }

  class Modul {
    modul_id: int [0..1] «PK, AUTOINCREMENT»
    titel: str «UNIQUE»
    ects: int
    plan_semester_nr: int
    default_soll_bestanden_am: date [0..1]
  }

  class ModulBelegung {
    belegung_id: int [0..1] «PK»
    studiengang_id: int «FK»
    modul_id: int «FK»
    plan_semester_nr: int
    ist_semester_nr: int [0..1]

    soll_bestanden_am: date [0..1]
    ist_bestanden_am: date [0..1]

    soll_note: float [0..1]
    ist_note: float [0..1]

    anzahl_versuche: int
  }
}

' -------------------------
' Dependencies (downwards)
' -------------------------
DashboardApp --> DashboardService

DashboardService --> StudentRepository
DashboardService --> StudiengangRepository
DashboardService --> ModulRepository
DashboardService --> ModulBelegungRepository

StudentRepository --> DatabaseProtocol
StudiengangRepository --> DatabaseProtocol
ModulRepository --> DatabaseProtocol
ModulBelegungRepository --> DatabaseProtocol

SQLiteDatabase ..|> DatabaseProtocol

' -------------------------
' Domain associations
' -------------------------
Student "1" --> "0..*" Studiengang
Studiengang "1" --> "0..*" ModulBelegung
Modul "1" --> "0..*" ModulBelegung

@enduml
'''

def main() -> None:
    out_path = Path(__file__).with_name("uml_class_diagram_architecture_phase3.puml")
    out_path.write_text(PUML, encoding="utf-8")
    print(f"Wrote: {out_path}")

if __name__ == "__main__":
    main()
