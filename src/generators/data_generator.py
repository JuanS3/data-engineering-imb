"""
Generador de datos sintéticos con errores intencionales.

Este módulo genera datasets de prueba que contienen violaciones controladas
a las 6 dimensiones de calidad de datos. Es fundamental para el taller,
ya que permite demostrar cómo el pipeline detecta y reporta cada tipo
de problema.

Los errores se inyectan de forma determinística (usando semilla) para
que los resultados del taller sean reproducibles.
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path
from typing import Final

import pandas as pd
from rich.console import Console
from rich.progress import Progress

from src.utils.logger import setup_logger

logger = setup_logger(__name__)
console = Console()

# Constantes del generador
VALID_COUNTRIES: Final[dict[str, list[str]]] = {
    "México": ["CDMX", "Guadalajara", "Monterrey", "Puebla"],
    "España": ["Madrid", "Barcelona", "Valencia", "Sevilla"],
    "Argentina": ["Buenos Aires", "Córdoba", "Rosario", "Mendoza"],
    "Colombia": ["Bogotá", "Medellín", "Cali", "Barranquilla"],
    "Chile": ["Santiago", "Valparaíso", "Concepción", "Antofagasta"],
}

FIRST_NAMES: Final[list[str]] = [
    "Juan",
    "María",
    "Carlos",
    "Ana",
    "Luis",
    "Carmen",
    "Pedro",
    "Laura",
    "Miguel",
    "Sofía",
    "Diego",
    "Valentina",
    "Javier",
    "Isabella",
    "Andrés",
]

LAST_NAMES: Final[list[str]] = [
    "García",
    "Rodríguez",
    "Martínez",
    "López",
    "González",
    "Hernández",
    "Pérez",
    "Sánchez",
    "Ramírez",
    "Torres",
    "Flores",
    "Rivera",
    "Gómez",
]


class DataGenerator:
    """
    Generador de datos de clientes con errores controlados.

    Parameters
    ----------
    seed : int, optional
        Semilla para reproducibilidad, por defecto 42.
    error_rate : float, optional
        Tasa de errores a inyectar (0.0 a 1.0), por defecto 0.15.

    Attributes
    ----------
    rng : random.Random
        Generador de números aleatorios con semilla fija.

    Examples
    --------
    >>> gen = DataGenerator(seed=42, error_rate=0.1)
    >>> df = gen.generate(n_rows=100)
    >>> df.shape
    (100, 12)

    """

    def __init__(self, seed: int = 42, error_rate: float = 0.15) -> None:
        self.rng = random.Random(seed)
        self.error_rate = error_rate

    def _should_inject_error(self) -> bool:
        """
        Determina si se debe inyectar un error en el registro actual.

        Returns
        -------
        bool
            True si se debe inyectar un error según la tasa configurada.

        """
        return self.rng.random() < self.error_rate

    def _generate_valid_record(self, idx: int) -> dict[str, object]:
        """
        Genera un registro válido de cliente.

        Parameters
        ----------
        idx : int
            Índice del registro (usado para generar IDs únicos).

        Returns
        -------
        dict[str, object]
            Diccionario con los campos del cliente.

        """
        country = self.rng.choice(list(VALID_COUNTRIES.keys()))
        city = self.rng.choice(VALID_COUNTRIES[country])
        age = self.rng.randint(18, 85)
        birth_year = 2026 - age
        birth_month = self.rng.randint(1, 12)
        birth_day = self.rng.randint(1, 28)

        return {
            "customer_id": f"CUST-{idx:06d}",
            "first_name": self.rng.choice(FIRST_NAMES),
            "last_name": self.rng.choice(LAST_NAMES),
            "email": f"cliente{idx}@example.com",
            "age": age,
            "birth_date": f"{birth_year}-{birth_month:02d}-{birth_day:02d}",
            "country": country,
            "city": city,
            "annual_income": round(self.rng.uniform(15000, 250000), 2),
            "credit_score": self.rng.randint(300, 850),
            "registration_date": f"202{self.rng.randint(0, 5)}-{self.rng.randint(1, 12):02d}-{self.rng.randint(1, 28):02d}",
            "last_update": "2026-09-15",
        }

    def _inject_completeness_error(self, record: dict[str, object]) -> None:
        """
        Inyecta error de completitud (valores nulos).

        Parameters
        ----------
        record : dict[str, object]
            Registro a modificar. Se muta in-place.

        """
        field = self.rng.choice(["email", "first_name", "last_name", "age"])
        record[field] = None  # type: ignore[assignment]

    def _inject_uniqueness_error(
        self,
        record: dict[str, object],
        duplicate_of: dict[str, object],
    ) -> None:
        """
        Inyecta error de unicidad (duplicados).

        Parameters
        ----------
        record : dict[str, object]
            Registro a modificar. Se muta in-place.
        duplicate_of : dict[str, object]
            Registro del cual copiar los valores únicos.
        """
        record["email"] = duplicate_of["email"]

    def _inject_validity_error(self, record: dict[str, object]) -> None:
        """
        Inyecta error de validez (formato incorrecto).

        Parameters
        ----------
        record : dict[str, object]
            Registro a modificar. Se muta in-place.

        """
        error_type = self.rng.choice(["email", "age", "date"])
        if error_type == "email":
            record["email"] = "email-invalido-sin-arroba"
        elif error_type == "age":
            record["age"] = self.rng.choice([-5, 200, 999])
        else:
            record["registration_date"] = "fecha-invalida"

    def _inject_consistency_error(self, record: dict[str, object]) -> None:
        """
        Inyecta error de consistencia (campos inconsistentes).

        Parameters
        ----------
        record : dict[str, object]
            Registro a modificar. Se muta in-place.

        """
        error_type = self.rng.choice(["country_city", "age_birthdate"])
        if error_type == "country_city":
            # Ciudad que no pertenece al país
            other_country = self.rng.choice([c for c in VALID_COUNTRIES if c != record["country"]])
            record["city"] = self.rng.choice(VALID_COUNTRIES[other_country])
        else:
            # Edad no coincide con fecha de nacimiento
            record["age"] = self.rng.randint(18, 85)
            # birth_date se mantiene → inconsistencia

    def _inject_accuracy_error(self, record: dict[str, object]) -> None:
        """
        Inyecta error de exactitud (valores fuera de rango real).

        Parameters
        ----------
        record : dict[str, object]
            Registro a modificar. Se muta in-place.

        """
        field = self.rng.choice(["annual_income", "credit_score"])
        if field == "annual_income":
            record["annual_income"] = self.rng.choice([-1000, 50_000_000])
        else:
            record["credit_score"] = self.rng.choice([100, 950, 1500])

    def _inject_timeliness_error(self, record: dict[str, object]) -> None:
        """
        Inyecta error de oportunidad (datos desactualizados).

        Parameters
        ----------
        record : dict[str, object]
            Registro a modificar. Se muta in-place.

        """
        old_year = self.rng.randint(2010, 2018)
        record["last_update"] = (
            f"{old_year}-{self.rng.randint(1, 12):02d}-{self.rng.randint(1, 28):02d}"
        )

    def generate(self, n_rows: int) -> pd.DataFrame:
        """
        Genera un dataset con errores controlados.

        Parameters
        ----------
        n_rows : int
            Número de registros a generar.

        Returns
        -------
        pd.DataFrame
            DataFrame con los datos generados, incluyendo errores
            inyectados según la tasa configurada.

        Raises
        ------
        ValueError
            Si n_rows es menor o igual a 0.

        Examples
        --------
        >>> gen = DataGenerator(seed=42, error_rate=0.2)
        >>> df = gen.generate(n_rows=500)
        >>> len(df)
        500

        """
        if n_rows <= 0:
            raise ValueError(f"n_rows debe ser positivo, recibido: {n_rows}")

        records: list[dict[str, object]] = []

        with Progress() as progress:
            task = progress.add_task("[cyan]Generando datos...", total=n_rows)
            for idx in range(n_rows):
                record = self._generate_valid_record(idx)

                if self._should_inject_error():
                    error_type = self.rng.choice(
                        [
                            "completeness",
                            "uniqueness",
                            "validity",
                            "consistency",
                            "accuracy",
                            "timeliness",
                        ]
                    )
                    if error_type == "completeness":
                        self._inject_completeness_error(record)
                    elif error_type == "uniqueness" and records:
                        ref = self.rng.choice(records[-min(50, len(records)) :])
                        self._inject_uniqueness_error(record, ref)
                    elif error_type == "validity":
                        self._inject_validity_error(record)
                    elif error_type == "consistency":
                        self._inject_consistency_error(record)
                    elif error_type == "accuracy":
                        self._inject_accuracy_error(record)
                    elif error_type == "timeliness":
                        self._inject_timeliness_error(record)

                records.append(record)
                progress.update(task, advance=1)

        return pd.DataFrame(records)


def main() -> None:
    """
    Punto de entrada CLI para el generador de datos.

    Parses arguments de línea de comandos y ejecuta la generación
    del dataset, guardándolo en la ruta especificada.

    """
    parser = argparse.ArgumentParser(description="Genera datos sintéticos con errores controlados")
    parser.add_argument("--rows", type=int, default=1000, help="Número de filas a generar")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/raw/customers.csv"),
        help="Ruta del archivo CSV de salida",
    )
    parser.add_argument("--seed", type=int, default=42, help="Semilla para reproducibilidad")
    parser.add_argument(
        "--error-rate",
        type=float,
        default=0.15,
        help="Tasa de errores a inyectar (0.0 a 1.0)",
    )
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)

    console.print(f"[bold cyan]🔧 Generando {args.rows} registros...[/]")
    generator = DataGenerator(seed=args.seed, error_rate=args.error_rate)
    df = generator.generate(n_rows=args.rows)
    df.to_csv(args.output, index=False)

    console.print(f"[bold green]✅ Datos guardados en:[/] {args.output}")
    console.print(f"[dim]Filas: {len(df)} | Columnas: {len(df.columns)}[/]")


if __name__ == "__main__":
    main()
