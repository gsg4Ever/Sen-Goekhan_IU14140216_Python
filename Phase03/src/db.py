from __future__ import annotations

# -----------------------------------------------------------------------------
# Infrastructure: SQLite DB
# -----------------------------------------------------------------------------
# Enthält:
# - SQLiteDatabase: dünner Adapter um sqlite3.Connection (für DatabaseProtocol)
# - connect(): öffnet DB (Default-Pfad: Phase03/docs/database/database.db)
# - create_schema(): legt Tabellen/Indizes an (optional reset_db für Demo/Test)
#
# Hinweis zur Entkopplung (Tutor-Feedback Phase 2):
# Repositories typisieren gegen `DatabaseProtocol` (typing.Protocol), nicht gegen sqlite3.
# -----------------------------------------------------------------------------


"""SQLite-Infrastruktur (Phase 3).

Zweck:
    Stellt die konkrete SQLite-Implementierung bereit, die von der Anwendung genutzt wird.
    Repositories und Services typisieren dabei gegen `DatabaseProtocol` (siehe `db_protocol.py`).

Inhalt:
    - SQLiteDatabase: Adapter um `sqlite3.Connection` passend zu `DatabaseProtocol`
    - connect(): Öffnet die Datenbank (Default-Pfad unter `Phase03/docs/database`)
    - create_schema(): Legt Tabellen/Indizes an (optional: Reset für Demo/Test)

Hinweise:
    `DatabaseProtocol` wird aus Kompatibilitätsgründen re-exportiert, damit bestehende
    Imports weiterhin funktionieren. Die eigentliche Protocol-Definition liegt in
    `db_protocol.py`.
"""

import os
import sqlite3
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

from Phase03.src.db_protocol import DatabaseProtocol

__all__ = [
    "DatabaseProtocol",
    "SQLiteDatabase",
    "connect",
    "create_schema",
]


class SQLiteDatabase:
    """
    SQLite-Adapter passend zu `DatabaseProtocol`.
    
    Zweck:
        Kapselt eine `sqlite3.Connection` und bietet nur die Methoden an, die in
        Repository-/Service-Schicht benötigt werden.
    
    Hinweise:
        Der Adapter erleichtert das Testen (Mocking über das Protocol) und reduziert
        direkte Abhängigkeiten von `sqlite3`.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        """
        Initialisiert den Datenbank-Adapter.
        
        Zweck:
            Speichert die übergebene `sqlite3.Connection` als interne Implementierungsdetails.
        
        Parameter:
            conn (sqlite3.Connection): Offene Datenbankverbindung.
        """

        self._conn = conn

    # --- DatabaseProtocol ---
    def execute(self, sql: str, params: Sequence[Any] = ()) -> Any:
        """
        Führt ein einzelnes SQL-Statement aus.
        
        Zweck:
            Dient als zentrale Ausführungsfunktion für Repositories (SELECT/INSERT/UPDATE/DELETE).
        
        Parameter:
            sql (str): SQL-Statement (ggf. mit Platzhaltern `?`).
            params (Sequence[Any]): Parameterwerte für die Platzhalter.
        
        Rückgabe:
            Any: Cursor-ähnliches Objekt (bei sqlite3: `sqlite3.Cursor`).
        """

        return self._conn.execute(sql, params)

    def executemany(self, sql: str, seq_of_params: Iterable[Sequence[Any]]) -> Any:
        """
        Führt ein SQL-Statement für viele Parameter-Sätze aus.
        
        Zweck:
            Effiziente Bulk-Operation, z. B. mehrere INSERTs in einem Schritt.
        
        Parameter:
            sql (str): SQL-Statement.
            seq_of_params (Iterable[Sequence[Any]]): Iterable von Parameter-Tupeln.
        
        Rückgabe:
            Any: Cursor-ähnliches Objekt.
        """

        return self._conn.executemany(sql, seq_of_params)

    def executescript(self, sql_script: str) -> None:
        # sqlite3 liefert hier einen Cursor zurück; im Projekt wird dieser Rückgabewert nicht genutzt.
        """
        Führt ein SQL-Skript (mehrere Statements) aus.
        
        Zweck:
            Wird typischerweise zum Anlegen/Zurücksetzen des Schemas genutzt.
        
        Parameter:
            sql_script (str): Mehrzeiliges SQL-Skript.
        """

        self._conn.executescript(sql_script)

    def commit(self) -> None:
        """
        Bestätigt die aktuelle Transaktion (COMMIT).
        """

        self._conn.commit()

    def rollback(self) -> None:
        """
        Setzt die aktuelle Transaktion zurück (ROLLBACK).
        """

        self._conn.rollback()

    def close(self) -> None:
        """
        Schließt die Datenbankverbindung.
        
        Hinweise:
            Im Prototyp übernimmt die Service-Schicht (`DashboardService.close`) das kontrollierte Schließen.
        """

        self._conn.close()

    # Komfortzugriff für Debugging (wird von Repositories/Services nicht benötigt).
    @property
    def conn(self) -> sqlite3.Connection:
        """
        Gibt die rohe `sqlite3.Connection` zurück.
        
        Zweck:
            Ermöglicht Low-Level-Debugging, ohne das Protocol-Design in den Repositories zu durchbrechen.
        
        Rückgabe:
            sqlite3.Connection: Interne Datenbankverbindung.
        """

        return self._conn


def _default_db_path() -> Path:
    """
    Ermittelt den Standardpfad der SQLite-Datenbank.
    
    Zweck:
        Legt die Datenbank standardmäßig unterhalb des Phase03-Projektordners an:
        `Phase03/docs/database/database.db`.
    
    Rückgabe:
        Path: Vollständiger Pfad zur Datenbankdatei.
    
    Hinweise:
        Das Zielverzeichnis wird bei Bedarf automatisch erstellt.
    """

    here = Path(__file__).resolve()
    phase_root = here.parents[1]
    db_dir = phase_root / "docs" / "database"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "database.db"


def connect(db_path: Optional[str | os.PathLike[str]] = None) -> SQLiteDatabase:
    """
    Öffnet eine SQLite-Verbindung und gibt einen `SQLiteDatabase`-Adapter zurück.
    
    Zweck:
        Erstellt eine Verbindung zur Datenbankdatei, aktiviert Foreign Keys und setzt
        `row_factory` auf `sqlite3.Row`, damit Repositories spaltenbasiert zugreifen können.
    
    Parameter:
        db_path (str | PathLike | None): Optionaler Pfad zur Datenbankdatei.
    
    Rückgabe:
        SQLiteDatabase: Adapter-Objekt, das `DatabaseProtocol` erfüllt.
    """

    path = Path(db_path) if db_path is not None else _default_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return SQLiteDatabase(conn)


def create_schema(db: DatabaseProtocol, reset_db: bool = False) -> None:
    """
    Legt das Datenbankschema (Tabellen/Indizes) an.
    
    Zweck:
        Erstellt die Tabellen `student`, `studiengang`, `modul` und `modul_belegung`
        inklusive Indizes. Optional kann das Schema für einen reproduzierbaren Demo-Lauf
        vorher zurückgesetzt werden.
    
    Parameter:
        db (DatabaseProtocol): Datenbank-Adapter.
        reset_db (bool): Wenn True, werden bestehende Tabellen vorher gelöscht.
    
    Hinweise:
        Für echte Persistenz sollte `reset_db=False` bleiben (Standard im UI).
    """

    if reset_db:
        db.executescript(
            """
            DROP TABLE IF EXISTS modul_belegung;
            DROP TABLE IF EXISTS modul;
            DROP TABLE IF EXISTS studiengang;
            DROP TABLE IF EXISTS student;
            """
        )

    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS student(
            student_id INTEGER PRIMARY KEY AUTOINCREMENT,
            vorname TEXT NOT NULL,
            nachname TEXT NOT NULL,
            matrikelnummer TEXT NOT NULL UNIQUE,
            geburtsdatum TEXT,
            adresse TEXT
        );

        CREATE TABLE IF NOT EXISTS studiengang(
            studiengang_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            start_datum TEXT NOT NULL,
            soll_studiensemester INTEGER,
            soll_durchschnittsnote REAL NOT NULL,
            FOREIGN KEY(student_id) REFERENCES student(student_id) ON DELETE CASCADE
        );

        -- Modul-Stammdaten: modul_id automatisch, titel eindeutig
        CREATE TABLE IF NOT EXISTS modul(
            modul_id INTEGER PRIMARY KEY AUTOINCREMENT,
            titel TEXT NOT NULL UNIQUE,
            ects INTEGER NOT NULL,
            plan_semester_nr INTEGER NOT NULL,
            default_soll_bestanden_am TEXT
        );

        -- Modul-Belegung: KPI-relevante Daten pro Studiengang/Modul
        CREATE TABLE IF NOT EXISTS modul_belegung(
            belegung_id INTEGER PRIMARY KEY AUTOINCREMENT,
            studiengang_id INTEGER NOT NULL,
            modul_id INTEGER NOT NULL,
            plan_semester_nr INTEGER NOT NULL,
            ist_semester_nr INTEGER,
            soll_bestanden_am TEXT,
            ist_bestanden_am TEXT,
            soll_note REAL,
            ist_note REAL,
            anzahl_versuche INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY(studiengang_id) REFERENCES studiengang(studiengang_id) ON DELETE CASCADE,
            FOREIGN KEY(modul_id) REFERENCES modul(modul_id) ON DELETE RESTRICT
        );

        CREATE INDEX IF NOT EXISTS idx_mb_sg ON modul_belegung(studiengang_id);
        CREATE INDEX IF NOT EXISTS idx_mb_modul ON modul_belegung(modul_id);
        CREATE INDEX IF NOT EXISTS idx_mb_istdatum ON modul_belegung(ist_bestanden_am);
        """
    )
    db.commit()