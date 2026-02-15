"""
Startpunkt der Anwendung (Studien-Dashboard).

Zweck:
    Startet die Tkinter-GUI des Prototyps. Die Oberfläche kapselt alle Interaktionen
    (CRUD für Modulbelegungen) und ruft dafür ausschließlich die Service-Schicht auf.

Ausführung:
    python -m Phase03.src.main
"""

from __future__ import annotations

from Phase03.src.ui_tk import run


if __name__ == "__main__":
    run()