"""
Datenbank-Interfaces (Protocols) für Repository- und Service-Schicht.

Zweck:
    Entkoppelt die Anwendung von der konkreten Datenbank-Implementierung (hier: SQLite),
    indem Repositories/Services nur gegen kleine, stabile Interfaces typisieren.

Inhalt:
    - CursorProtocol: minimales Cursor-Verhalten (fetchone/fetchall/lastrowid)
    - DatabaseProtocol: minimale DB-API (execute/executemany/executescript + Transaktionen)

Hinweise:
    Die konkrete Implementierung des Interfaces erfolgt in `db.py` (SQLiteDatabase).
"""

from __future__ import annotations

from typing import Any, Iterable, Protocol, Sequence


class CursorProtocol(Protocol):
    """
    Cursor-Interface, das von Repositories benötigt wird.
    
    Zweck:
        Beschreibt nur die Cursor-Funktionen, die im Projekt tatsächlich verwendet werden
        (z. B. für SELECT-Abfragen und `lastrowid` nach INSERT).
    
    Hinweise:
        Ein echtes `sqlite3.Cursor` bietet deutlich mehr. Für die Entkopplung genügt hier
        ein „Minimalvertrag“ (Interface/Protocol).
    """

    # sqlite3.Cursor stellt `lastrowid` bereit; bei UPDATE kann dieser Wert 0/None sein.
    lastrowid: Any

    def fetchone(self) -> Any: ...
    def fetchall(self) -> list[Any]: ...


class DatabaseProtocol(Protocol):
    """
    Minimales Datenbank-Interface für Repositories/Services.
    
    Zweck:
        Vereinheitlicht den Zugriff auf die Persistenz (execute/commit/rollback/close),
        ohne die Anwendung an `sqlite3` zu koppeln.
    
    Hinweise:
        Repositories erhalten ein Objekt dieses Typs (z. B. `SQLiteDatabase`) und führen
        ausschließlich darüber SQL-Befehle aus.
    """

    def execute(self, sql: str, params: Sequence[Any] = ()) -> CursorProtocol: ...
    def executemany(self, sql: str, seq_of_params: Iterable[Sequence[Any]]) -> CursorProtocol: ...
    def executescript(self, sql_script: str) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
    def close(self) -> None: ...