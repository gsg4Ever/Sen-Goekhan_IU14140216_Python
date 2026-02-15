from __future__ import annotations

# -----------------------------------------------------------------------------
# Domain model (Entities)
# -----------------------------------------------------------------------------
# Diese Datei enthält die fachlichen Kernobjekte (Entities) des Dashboards.
#
# Ziel: schlanke, gut testbare Datenklassen (dataclasses).
# - Invarianten / Wertebereiche werden über __post_init__ als Basisschutz geprüft.
# - UI-spezifisches Parsing (String → int/float/date) passiert in `validation.py`.
# - Persistenzdetails (SQL/Row-Objekte) bleiben in den Repositories.
#
# Hinweis zum Semester:
# Ein eigenes Entity `Semester` wird im Prototypen nicht persistiert.
# Stattdessen werden Semester-Informationen über `plan_semester_nr` / `ist_semester_nr`
# direkt an Modul bzw. ModulBelegung geführt. Damit bleibt das Modell schlank, ohne die
# KPI-Berechnungen zu verlieren.
# -----------------------------------------------------------------------------


from dataclasses import dataclass
from datetime import date
from typing import Optional


def _require_non_empty(val: str, field: str) -> None:
    """
    Prüft, ob ein Pflicht-String nicht leer ist.
    
    Zweck:
        Zentrale Hilfsfunktion für `__post_init__`, um wiederkehrende „nicht leer“-Checks
        konsistent umzusetzen.
    
    Parameter:
        val (str): Zu prüfender Wert.
        field (str): Feldname für die Fehlermeldung.
    
    Ausnahmen:
        ValueError: Wenn `val` leer/whitespace ist.
    """

    if not isinstance(val, str) or not val.strip():
        raise ValueError(f"{field} darf nicht leer sein")


@dataclass(slots=True)
class Student:
    """
    Repräsentiert den/die Nutzer:in des Dashboards.
    
    Zweck:
        Hält Stammdaten, die einer Person zugeordnet sind (z. B. für Kopfzeile/Identifikation).
        Für die KPI-Berechnung sind diese Daten im Prototypen nicht zwingend erforderlich,
        werden aber bewusst modelliert (Tutor-Feedback: „Person/Student“ ergänzen).
    
    Attribute:
        vorname (str): Vorname (Pflicht).
        nachname (str): Nachname (Pflicht).
        matrikelnummer (str): Matrikelnummer als natürlicher Schlüssel (Pflicht).
        geburtsdatum (date | None): Optionales Geburtsdatum.
        adresse (str | None): Optionale Adresse.
    
    Hinweise:
        Die Pflichtfelder werden in `__post_init__` auf „nicht leer“ geprüft.
    """

    vorname: str
    nachname: str
    matrikelnummer: str
    geburtsdatum: Optional[date] = None
    adresse: Optional[str] = None

    def __post_init__(self) -> None:
        """
        Validiert Pflichtfelder nach der Initialisierung.
        
        Zweck:
            Sicherstellt, dass Vorname/Nachname/Matrikelnummer gesetzt sind.
        """

        # Pflichtfelder dürfen nicht leer sein
        _require_non_empty(self.vorname, "vorname")
        _require_non_empty(self.nachname, "nachname")
        _require_non_empty(self.matrikelnummer, "matrikelnummer")


@dataclass(slots=True)
class Studiengang:
    """
    Fachlicher Rahmen eines Studiums, auf dem KPIs basieren.
    
    Zweck:
        Beschreibt den Studienkontext (Start, Zielsemester, Ziel-Ø-Note). Services verwenden
        diese Angaben, um Soll-/Prognose-Werte (z. B. Studiendauer) abzuleiten.
    
    Attribute:
        name (str): Bezeichnung des Studiengangs.
        start_datum (date): Studienstart.
        soll_studiensemester (int | None): Optionales Ziel (z. B. 6 Semester).
        soll_durchschnittsnote (float): Ziel-Durchschnittsnote (1.0..5.0).
    
    Hinweise:
        Die Soll-Dauer in Jahren wird über die Annahme „2 Semester pro Jahr“ abgeleitet.
    """

    name: str
    start_datum: date
    soll_studiensemester: Optional[int] = None
    soll_durchschnittsnote: float = 2.0

    def __post_init__(self) -> None:
        """
        Validiert Wertebereiche nach der Initialisierung.
        
        Zweck:
            Prüft Pflichtfelder und einfache Wertebereiche (Soll-Semester, Zielnote).
        """

        # Name ist Pflichtfeld
        _require_non_empty(self.name, "name")
        if self.soll_studiensemester is not None and int(self.soll_studiensemester) < 1:
            raise ValueError("soll_studiensemester muss >= 1 sein (falls gesetzt)")
        if not (1.0 <= float(self.soll_durchschnittsnote) <= 5.0):
            raise ValueError("soll_durchschnittsnote muss zwischen 1.0 und 5.0 liegen")

    

@dataclass(slots=True)
class Modul:
    """
    Stammdaten eines Moduls (Modulkatalog).
    
    Zweck:
        Enthält die stabilen Modulinformationen (Titel, ECTS, geplantes Semester).
        Diese Daten werden unabhängig von Prüfungsleistungen gepflegt und in Belegungen referenziert.
    
    Attribute:
        modul_id (int | None): Primärschlüssel (DB-Autoincrement); `None` vor dem INSERT.
        titel (str): Modultitel (in der DB eindeutig/UNIQUE).
        ects (int): ECTS-Punkte (> 0).
        plan_semester_nr (int): Geplantes Semester (> 0).
        default_soll_bestanden_am (date | None): Optionaler Vorschlagswert für das Soll-Datum.
    
    Hinweise:
        Die UI kann `default_soll_bestanden_am` als Vorbelegung nutzen, Belegungen dürfen davon abweichen.
    """

    modul_id: Optional[int]
    titel: str
    ects: int
    plan_semester_nr: int
    default_soll_bestanden_am: Optional[date] = None

    def __post_init__(self) -> None:
        """
        Validiert Wertebereiche nach der Initialisierung.
        
        Zweck:
            Stellt u. a. sicher, dass ECTS und geplantes Semester > 0 sind.
        """

        _require_non_empty(self.titel, "titel")
        # ECTS müssen positiv sein
        if int(self.ects) <= 0:
            raise ValueError("ects muss > 0 sein")
        if int(self.plan_semester_nr) <= 0:
            raise ValueError("plan_semester_nr muss > 0 sein")


@dataclass(slots=True)
class ModulBelegung:
    """
    Prüfungs-/Ist-Daten eines Moduls innerhalb eines Studiengangs.
    
    Zweck:
        Modelliert die Belegung als „Assoziationsklasse“ (UML): Sie verknüpft ein Modul
        (Stammdaten) mit einem Studiengang (Kontext) und speichert KPI-relevante Felder
        wie Bestehensdatum, Noten und Versuche.
    
    Attribute:
        belegung_id (int | None): Primärschlüssel; `None` vor dem INSERT.
        studiengang_id (int): Referenz auf den Studiengang (> 0).
        modul_id (int): Referenz auf das Modul (> 0).
        plan_semester_nr (int): Geplantes Semester (> 0).
        ist_semester_nr (int | None): Tatsächliches Semester (optional).
        soll_bestanden_am (date | None): Ziel-/Soll-Datum (optional).
        ist_bestanden_am (date | None): Bestehensdatum (optional).
        soll_note (float | None): Zielnote (optional).
        ist_note (float | None): Tatsächliche Note (optional).
        anzahl_versuche (int): Anzahl Prüfungsversuche (>= 1).
    
    Hinweise:
        Wertebereiche werden in `__post_init__` validiert (Basisschutz gegen ungültige Zustände).
    """

    belegung_id: Optional[int]
    studiengang_id: int
    modul_id: int
    plan_semester_nr: int
    ist_semester_nr: Optional[int]
    soll_bestanden_am: Optional[date]
    ist_bestanden_am: Optional[date]
    soll_note: Optional[float]
    ist_note: Optional[float]
    anzahl_versuche: int = 1

    def __post_init__(self) -> None:
        """
        Validiert Referenzen und Wertebereiche nach der Initialisierung.
        
        Zweck:
            Basisschutz gegen ungültige IDs/Notenbereiche/Versuchszahlen.
        """

        # Fremdschlüssel/Referenzen müssen > 0 sein
        if int(self.studiengang_id) <= 0:
            raise ValueError("studiengang_id muss > 0 sein")
        if int(self.modul_id) <= 0:
            raise ValueError("modul_id muss > 0 sein")
        if int(self.plan_semester_nr) <= 0:
            raise ValueError("plan_semester_nr muss > 0 sein")
        if self.ist_semester_nr is not None and int(self.ist_semester_nr) <= 0:
            raise ValueError("ist_semester_nr muss > 0 sein (falls gesetzt)")
        if self.soll_note is not None and not (1.0 <= float(self.soll_note) <= 5.0):
            raise ValueError("soll_note muss zwischen 1.0 und 5.0 liegen (falls gesetzt)")
        if self.ist_note is not None and not (1.0 <= float(self.ist_note) <= 5.0):
            raise ValueError("ist_note muss zwischen 1.0 und 5.0 liegen (falls gesetzt)")
        if int(self.anzahl_versuche) <= 0:
            raise ValueError("anzahl_versuche muss > 0 sein")