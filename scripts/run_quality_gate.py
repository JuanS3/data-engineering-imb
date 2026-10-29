#!/usr/bin/env python3
"""
Paso 3 del taller: ejecuta el gate de calidad sobre los datasets.

Corre los checkpoints de Great Expectations, imprime el resumen
operativo y devuelve un exit code que expresa la decisión del gate:

    0 -> GATE EN VERDE  : los datos pueden avanzar.
    1 -> GATE BLOQUEADO : hay fallas críticas; los datos NO avanzan.
    2 -> Error operativo (contexto no inicializado, datos ausentes).

Este exit code es el que consumirán Airflow (Unidad 3→5) y el pipeline
CI/CD (Unidad 5) para detener la promoción de datos inválidos.

Uso (desde la raíz del proyecto):
    python scripts/run_quality_gate.py               # ambos datasets
    python scripts/run_quality_gate.py --dataset customers
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Garantiza que `src` sea importable al ejecutar el script directo
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.quality import gate  # noqa: E402


def main() -> None:
    """Ejecuta el gate y propaga el exit code al shell."""
    parser = argparse.ArgumentParser(
        description="Gate de calidad: valida customers y/o orders con Great Expectations."
    )
    parser.add_argument(
        "--dataset",
        choices=["customers", "orders"],
        action="append",
        help="Dataset a validar (repetible). Por defecto se validan ambos.",
    )
    args = parser.parse_args()

    exit_code = gate.ejecutar_gate(datasets=args.dataset)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
