"""
Startpunkt der Anwendung (Studien-Dashboard).

Zweck:
    Startet die Tkinter-GUI des Prototyps. Die Oberfläche kapselt alle Interaktionen
    (CRUD für Modulbelegungen) und ruft dafür ausschließlich die Service-Schicht auf.

Ausführung:
    python -m Phase3.src.main
"""

from __future__ import annotations

try:
    import tkinter  # noqa: F401
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Tkinter fehlt.\n"
        "- Linux (Debian/Ubuntu): sudo apt install python3-tk\n"
        "- Fedora: sudo dnf install python3-tkinter\n"
        "- Arch: sudo pacman -S tk\n"
        "Unter Windows/macOS bitte Python neu installieren und Tcl/Tk mit installieren."
    ) from exc

from Phase3.src.ui_tk import run

if __name__ == "__main__":
    run()
