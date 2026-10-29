#!/usr/bin/env python3
"""
Demo del taller: el gate en acción (ESCENARIO VERDE vs ESCENARIO BLOQUEADO).

Este script demuestra, de punta a punta, la idea central de la Unidad 3:
"el proceso termina bien" no garantiza "el dato es correcto". El gate de
calidad convierte esa diferencia en una señal operativa.

Escenarios:
  A. DATOS LIMPIOS     -> regenera datasets con error_rate=0 -> gate PASS  (exit 0)
  B. DATOS CONTAMINADOS -> regenera datasets con errores    -> gate BLOCK (exit 1)

Al final, deja los datos contaminados en data/raw y el reporte HTML de
Data Docs disponible para inspección de evidencia.

Uso (desde la raíz del proyecto):
    python scripts/demo_gate.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rich.console import Console  # noqa: E402
from rich.panel import Panel  # noqa: E402

from src.quality import gate  # noqa: E402
from scripts.generate_data import generar_customers, generar_orders  # noqa: E402

console = Console()

RAIZ = Path(__file__).resolve().parents[1]
SCRIPT_GATE = RAIZ / "scripts" / "run_quality_gate.py"


def correr_gate_como_proceso() -> int:
    """
    Ejecuta el gate como proceso independiente (exit code real de shell).

    Returns
    -------
    int
        Exit code del proceso hijo (0 = verdec, 1 = bloqueado).

    """
    proceso = subprocess.run(
        [sys.executable, str(SCRIPT_GATE)],
        cwd=str(RAIZ),
        capture_output=False,
    )
    return proceso.returncode


def main() -> None:
    """Corre los dos escenarios y verifica que el gate se comporte como debe."""
    console.rule("[bold cyan]DEMO: el gate de calidad frente a datos limpios y contaminados")

    # ------------------------------------------------------------------
    # ESCENARIO A: datos limpios -> el gate debe permitir avanzar
    # ------------------------------------------------------------------
    console.print(Panel("[bold]ESCENARIO A · Datos limpios[/]\nerror_rate = 0.0 (sin inyección de errores)", border_style="green"))
    generar_customers(filas=1000, error_rate=0.0, seed=42)
    generar_orders(ordenes=2000, error_rate=0.0, seed=42)

    console.print("Ejecutando gate...")
    exito_a = correr_gate_como_proceso()
    console.print(f"[bold]Exit code escenario A:[/] {exito_a} ({'PASS esperado' if exito_a == 0 else 'INESPERADO'})")
    console.print()

    # ------------------------------------------------------------------
    # ESCENARIO B: datos contaminados -> el gate debe bloquear
    # ------------------------------------------------------------------
    console.print(Panel("[bold]ESCENARIO B · Datos contaminados[/]\nerror_rate = 0.25 (customers) / 0.20 (orders)", border_style="red"))
    generar_customers(filas=1000, error_rate=0.25, seed=42)
    generar_orders(ordenes=2000, error_rate=0.20, seed=42)

    console.print("Ejecutando gate...")
    exito_b = correr_gate_como_proceso()
    console.print(f"[bold]Exit code escenario B:[/] {exito_b} ({'BLOCK esperado' if exito_b == 1 else 'INESPERADO'})")
    console.print()

    # ------------------------------------------------------------------
    # Veredicto de la demo
    # ------------------------------------------------------------------
    demo_correcta = (exito_a == 0) and (exito_b == 1)
    if demo_correcta:
        console.print(
            Panel(
                "[bold green]DEMO EXITOSA[/]\n"
                "El mismo pipeline avanza con datos limpios y se BLOQUEA con datos "
                "contaminados. La diferencia es evidencia verificable, no memoria "
                "del equipo. Inspecciona el reporte HTML:\n"
                f"{gate.RUTA_DATA_DOCS}",
                border_style="green",
            )
        )
    else:
        console.print(
            Panel(
                "[bold red]DEMO CON RESULTADO INESPERADO[/]\n"
                f"Escenario A exit={exito_a} (esperado 0) · Escenario B exit={exito_b} (esperado 1).\n"
                "Revisa los umbrales (mostly) en src/quality/suites.py y vuelve a intentar.",
                border_style="red",
            )
        )

    console.print()
    console.print("[dim]Nota: data/raw quedó con los datos del escenario B para que puedas[/]")
    console.print("[dim]explorar Data Docs y el detalle de las fallas críticas.[/]")

    sys.exit(0 if demo_correcta else 1)


if __name__ == "__main__":
    main()
