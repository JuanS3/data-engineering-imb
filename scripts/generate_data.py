#!/usr/bin/env python3
"""
Paso 1 del taller: genera los datasets sintéticos con errores controlados.

Los generadores provienen del material del curso y crean:

- customers.csv : clientes con violaciones a las 6 dimensiones de calidad.
- orders.csv    : órdenes con errores temporales, financieros y referenciales.

La semilla fija hace el ejercicio reproducible: con la misma semilla y
misma tasa de error, todos los equipos obtienen el mismo dataset.

Uso (desde la raíz del proyecto):
    python scripts/generate_data.py --dataset all
    python scripts/generate_data.py --dataset customers --rows 1000 --error-rate 0.15
    python scripts/generate_data.py --dataset orders --orders 2000 --error-rate 0.20
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Garantiza que `src` sea importable al ejecutar el script directo
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rich.console import Console  # noqa: E402
from rich.panel import Panel  # noqa: E402

from src.generators.data_generator import DataGenerator  # noqa: E402
from src.generators.orders_generator import OrdersGenerator  # noqa: E402
from src.quality import config  # noqa: E402
from src.utils.logger import setup_logger  # noqa: E402

logger = setup_logger(__name__)
console = Console()


def generar_customers(filas: int, error_rate: float, seed: int) -> Path:
    """
    Genera customers.csv con los parámetros indicados.

    Parameters
    ----------
    filas : int
        Número de registros de clientes.
    error_rate : float
        Tasa de errores a inyectar (0.0 = datos limpios).
    seed : int
        Semilla de reproducibilidad.

    Returns
    -------
    Path
        Ruta del CSV generado.

    """
    destino = config.DATA_RAW_DIR / config.CUSTOMERS_CSV
    destino.parent.mkdir(parents=True, exist_ok=True)

    console.print(f"[bold cyan]Generando customers[/] (filas={filas}, error_rate={error_rate}, seed={seed})")
    generador = DataGenerator(seed=seed, error_rate=error_rate)
    df = generador.generate(n_rows=filas)
    df.to_csv(destino, index=False)
    console.print(f"  [green]OK[/] -> {destino} ({len(df)} filas, {len(df.columns)} columnas)")
    return destino


def generar_orders(ordenes: int, error_rate: float, seed: int) -> Path:
    """
    Genera orders.csv con los parámetros indicados.

    Parameters
    ----------
    ordenes : int
        Número de órdenes.
    error_rate : float
        Tasa de errores a inyectar (0.0 = datos limpios).
    seed : int
        Semilla de reproducibilidad.

    Returns
    -------
    Path
        Ruta del CSV generado.

    """
    destino = config.DATA_RAW_DIR / config.ORDERS_CSV
    destino.parent.mkdir(parents=True, exist_ok=True)

    console.print(f"[bold cyan]Generando orders[/] (órdenes={ordenes}, error_rate={error_rate}, seed={seed})")
    generador = OrdersGenerator(
        seed=seed,
        error_rate=error_rate,
        n_customers=config.CUSTOMERS_POOL_SIZE,
    )
    df = generador.generate(n_orders=ordenes)
    df.to_csv(destino, index=False)
    console.print(f"  [green]OK[/] -> {destino} ({len(df)} filas, {len(df.columns)} columnas)")
    return destino


def main() -> None:
    """Parsea argumentos y genera los datasets solicitados."""
    parser = argparse.ArgumentParser(
        description="Genera los datasets sintéticos del taller (customers y orders)."
    )
    parser.add_argument(
        "--dataset",
        choices=["customers", "orders", "all"],
        default="all",
        help="Qué dataset generar (por defecto: all).",
    )
    parser.add_argument("--rows", type=int, default=1000, help="Filas de customers (por defecto: 1000).")
    parser.add_argument("--orders", type=int, default=2000, help="Órdenes de orders (por defecto: 2000).")
    parser.add_argument("--error-rate", type=float, default=0.15, help="Tasa de errores (por defecto: 0.15).")
    parser.add_argument("--seed", type=int, default=42, help="Semilla de reproducibilidad (por defecto: 42).")
    args = parser.parse_args()

    console.rule("[bold cyan]Generación de datos sintéticos con errores controlados")

    if args.dataset in ("customers", "all"):
        generar_customers(args.rows, args.error_rate, args.seed)
    if args.dataset in ("orders", "all"):
        generar_orders(args.orders, args.error_rate, args.seed)

    console.print(
        Panel(
            "Siguiente paso: [bold]python scripts/bootstrap_gx.py[/]\n"
            "(el bootstrap requiere que los CSV ya existan)",
            border_style="cyan",
        )
    )


if __name__ == "__main__":
    main()
