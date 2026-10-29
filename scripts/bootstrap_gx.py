#!/usr/bin/env python3
"""
Paso 2 del taller: inicializa el contexto Great Expectations (mode=file).

Crea/sincroniza de forma idempotente:
- gx/great_expectations.yml (contexto versionado)
- datasources, assets y batch definitions sobre data/raw/
- suites de expectativas (customers y orders)
- validation definitions y checkpoints con Data Docs

Uso (desde la raíz del proyecto):
    python scripts/bootstrap_gx.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Garantiza que `src` sea importable al ejecutar el script directo
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rich.console import Console  # noqa: E402

from src.quality.bootstrap import ErrorBootstrap, ejecutar_bootstrap  # noqa: E402

console = Console()


def main() -> None:
    """Ejecuta el bootstrap con salida amigable para el participante."""
    console.rule("[bold cyan]Bootstrap del contexto Great Expectations (mode=file)")
    try:
        contexto = ejecutar_bootstrap()
    except ErrorBootstrap as error:
        console.print(f"[bold red]Error:[/] {error}")
        sys.exit(2)

    console.print()
    console.print("[bold green]Contexto listo.[/] Artefactos versionados en:")
    console.print("  [cyan]gx/great_expectations.yml[/]        -> configuración del contexto")
    console.print("  [cyan]gx/expectations/[/]              -> suites de expectativas")
    console.print("  [cyan]gx/validation_definitions/[/]    -> vínculos datos-reglas")
    console.print("  [cyan]gx/checkpoints/[/]               -> puntos de control")
    console.print()
    console.print("Siguiente paso: [bold]python scripts/run_quality_gate.py[/]")


if __name__ == "__main__":
    main()
