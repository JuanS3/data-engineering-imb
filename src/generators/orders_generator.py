"""
Generador de órdenes de e-commerce con relaciones temporales complejas.

Genera un dataset realista de órdenes que incluye relaciones entre fechas
(compra, envío, entrega), cálculos cross-field (total = precio * cantidad),
y errores intencionales para demostrar validaciones avanzadas.

Dominios cubiertos:
- Relación cliente-orden (1:N)
- Relación orden-items (1:N)
- Relación orden-pago (1:1)
- Jerarquía temporal: registro → compra → envío → entrega
- Cálculos financieros: subtotal, impuestos, descuentos, total

Los errores se inyectan en 7 categorías:
1. Temporal inversion (fechas fuera de orden)
2. Cálculo incorrecto (total ≠ precio * cantidad)
3. Lógica de negocio (descuento > 100%)
4. Referencial (cliente inexistente)
5. Estado inválido (entregado sin envío)
6. Montos negativos o cero
7. Duraciones imposibles (envío en 0 días)
"""

from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Final

import pandas as pd
from rich.console import Console
from rich.progress import Progress

from src.utils.logger import setup_logger

logger = setup_logger(__name__)
console = Console()

# ============================================================================
# Catálogos de referencia
# ============================================================================
PRODUCT_CATALOG: Final[dict[str, dict[str, Any]]] = {
    "ELECTRONICS": {
        "products": ["Laptop", "Smartphone", "Tablet", "Audífonos", "Smartwatch"],
        "price_range": (150.0, 2500.0),
    },
    "CLOTHING": {
        "products": ["Camisa", "Pantalón", "Zapatos", "Chamarra", "Vestido"],
        "price_range": (20.0, 300.0),
    },
    "HOME": {
        "products": ["Lámpara", "Cojín", "Alfombra", "Cortinas", "Espejo"],
        "price_range": (15.0, 500.0),
    },
    "BOOKS": {
        "products": ["Novela", "Texto", "Comic", "Revista", "Enciclopedia"],
        "price_range": (5.0, 80.0),
    },
    "SPORTS": {
        "products": ["Balón", "Raqueta", "Bicicleta", "Pesas", "YogaMat"],
        "price_range": (10.0, 1200.0),
    },
}

PAYMENT_METHODS: Final[list[str]] = [
    "CREDIT_CARD",
    "DEBIT_CARD",
    "PAYPAL",
    "BANK_TRANSFER",
    "CASH_ON_DELIVERY",
    "CRYPTO",
]

ORDER_STATUS: Final[list[str]] = [
    "PENDING",
    "PROCESSING",
    "SHIPPED",
    "IN_TRANSIT",
    "DELIVERED",
    "CANCELLED",
    "REFUNDED",
]

SHIPPING_METHODS: Final[dict[str, dict[str, Any]]] = {
    "STANDARD": {"min_days": 5, "max_days": 10, "cost": 5.99},
    "EXPRESS": {"min_days": 2, "max_days": 4, "cost": 14.99},
    "SAME_DAY": {"min_days": 0, "max_days": 1, "cost": 29.99},
    "ECONOMIC": {"min_days": 10, "max_days": 20, "cost": 2.99},
}

COUNTRIES: Final[list[str]] = [
    "México",
    "España",
    "Argentina",
    "Colombia",
    "Chile",
    "Perú",
]

CURRENCIES_BY_COUNTRY: Final[dict[str, str]] = {
    "México": "MXN",
    "España": "EUR",
    "Argentina": "ARS",
    "Colombia": "COP",
    "Chile": "CLP",
    "Perú": "PEN",
}


class OrdersGenerator:
    """
    Generador de dataset de órdenes con errores controlados.

    Parameters
    ----------
    seed : int, optional
        Semilla para reproducibilidad, por defecto 42.
    error_rate : float, optional
        Tasa de errores a inyectar (0.0 a 1.0), por defecto 0.20.
    n_customers : int, optional
        Número de clientes únicos en el pool, por defecto 100.

    Attributes
    ----------
    rng : random.Random
        Generador de números aleatorios con semilla fija.
    customers_pool : list[dict[str, Any]]
        Pool de clientes pre-generados para referenciar.

    Examples
    --------
    >>> gen = OrdersGenerator(seed=42, error_rate=0.15)
    >>> df = gen.generate(n_orders=500)
    >>> df.shape[0]
    500

    """

    def __init__(
        self,
        seed: int = 42,
        error_rate: float = 0.20,
        n_customers: int = 100,
    ) -> None:
        self.rng = random.Random(seed)
        self.error_rate = error_rate
        self.customers_pool = self._generate_customers_pool(n_customers)

    def _generate_customers_pool(self, n: int) -> list[dict[str, Any]]:
        """
        Genera un pool de clientes de referencia.

        Parameters
        ----------
        n : int
            Número de clientes a generar.

        Returns
        -------
        list[dict[str, Any]]
            Lista de diccionarios con datos de clientes.

        """
        pool: list[dict[str, Any]] = []
        base_date = datetime(2020, 1, 1)
        for i in range(n):
            reg_date = base_date + timedelta(days=self.rng.randint(0, 1500))
            country = self.rng.choice(COUNTRIES)
            pool.append(
                {
                    "customer_id": f"CUST-{i:05d}",
                    "registration_date": reg_date.date(),
                    "country": country,
                    "currency": CURRENCIES_BY_COUNTRY[country],
                    "customer_since_days": (datetime(2026, 10, 8) - reg_date).days,
                }
            )
        return pool

    def _should_inject_error(self, error_type: str | None = None) -> bool:
        """
        Determina si se inyecta un error.

        Parameters
        ----------
        error_type : str | None, optional
            Tipo específico de error (para distribución controlada).

        Returns
        -------
        bool
            True si se debe inyectar error.

        """
        return self.rng.random() < self.error_rate

    def _random_date_between(self, start: datetime, end: datetime) -> datetime:
        """
        Genera una fecha aleatoria entre start y end.

        Parameters
        ----------
        start : datetime
            Fecha inicial.
        end : datetime
            Fecha final.

        Returns
        -------
        datetime
            Fecha aleatoria en el rango.

        """
        delta = (end - start).days
        if delta <= 0:
            return start
        return start + timedelta(days=self.rng.randint(0, delta))

    def _generate_valid_order(self, idx: int) -> dict[str, Any]:
        """
        Genera una orden válida con todas las relaciones correctas.

        Parameters
        ----------
        idx : int
            Índice de la orden.

        Returns
        -------
        dict[str, Any]
            Diccionario con todos los campos de la orden.

        """
        customer = self.rng.choice(self.customers_pool)
        category = self.rng.choice(list(PRODUCT_CATALOG.keys()))
        product_info = PRODUCT_CATALOG[category]
        product = self.rng.choice(product_info["products"])
        unit_price = round(self.rng.uniform(*product_info["price_range"]), 2)
        quantity = self.rng.randint(1, 5)
        subtotal = round(unit_price * quantity, 2)
        discount_pct = self.rng.choice([0, 0, 0, 5, 10, 15, 20, 25])
        discount_amount = round(subtotal * discount_pct / 100, 2)
        tax_rate = 0.16  # IVA
        taxable = subtotal - discount_amount
        tax_amount = round(taxable * tax_rate, 2)
        shipping_method = self.rng.choice(list(SHIPPING_METHODS.keys()))
        shipping_cost = SHIPPING_METHODS[shipping_method]["cost"]
        total = round(taxable + tax_amount + shipping_cost, 2)

        # Jerarquía temporal correcta
        reg_date = customer["registration_date"]
        order_date = self._random_date_between(
            datetime.combine(reg_date, datetime.min.time()),
            datetime(2026, 10, 1),
        )
        ship_min = SHIPPING_METHODS[shipping_method]["min_days"]
        ship_max = SHIPPING_METHODS[shipping_method]["max_days"]
        shipping_date = order_date + timedelta(
            days=self.rng.randint(max(1, ship_min), max(2, ship_max))
        )
        delivery_date = shipping_date + timedelta(days=self.rng.randint(1, 5))

        payment_method = self.rng.choice(PAYMENT_METHODS)
        status = self._derive_status(order_date, shipping_date, delivery_date)

        return {
            "order_id": f"ORD-{idx:07d}",
            "customer_id": customer["customer_id"],
            "customer_country": customer["country"],
            "customer_currency": customer["currency"],
            "customer_registration_date": reg_date.isoformat(),
            "order_date": order_date.date().isoformat(),
            "product_category": category,
            "product_name": product,
            "unit_price": unit_price,
            "quantity": quantity,
            "subtotal": subtotal,
            "discount_percent": discount_pct,
            "discount_amount": discount_amount,
            "tax_rate": tax_rate,
            "tax_amount": tax_amount,
            "shipping_method": shipping_method,
            "shipping_cost": shipping_cost,
            "shipping_date": shipping_date.date().isoformat(),
            "delivery_date": delivery_date.date().isoformat(),
            "delivery_days": (delivery_date - shipping_date).days,
            "payment_method": payment_method,
            "total_amount": total,
            "order_status": status,
            "is_returned": False,
            "return_date": None,
        }

    def _derive_status(
        self,
        order_date: datetime,
        shipping_date: datetime,
        delivery_date: datetime,
    ) -> str:
        """
        Deriva el estado de la orden según las fechas.

        Parameters
        ----------
        order_date : datetime
            Fecha de la orden.
        shipping_date : datetime
            Fecha de envío.
        delivery_date : datetime
            Fecha de entrega.

        Returns
        -------
        str
            Estado derivado.

        """
        today = datetime(2026, 10, 8)
        if delivery_date <= today:
            return "DELIVERED"
        if shipping_date <= today:
            return "IN_TRANSIT"
        return "PROCESSING"

    # ========================================================================
    # Inyectores de errores
    # ========================================================================
    def _inject_temporal_inversion(self, order: dict[str, Any]) -> None:
        """
        Invierte el orden temporal de las fechas.

        Parameters
        ----------
        order : dict[str, Any]
            Orden a modificar. Se muta in-place.

        """
        error_type = self.rng.choice(
            ["order_before_reg", "ship_before_order", "deliver_before_ship"]
        )
        if error_type == "order_before_reg":
            # Orden antes del registro del cliente
            reg = datetime.fromisoformat(order["customer_registration_date"])
            order["order_date"] = (
                (reg - timedelta(days=self.rng.randint(10, 365))).date().isoformat()
            )
        elif error_type == "ship_before_order":
            order["shipping_date"] = order["order_date"]  # mismo día o antes
        else:
            order["delivery_date"] = order["shipping_date"]

    def _inject_calculation_error(self, order: dict[str, Any]) -> None:
        """
        Rompe la relación de cálculo total = subtotal - descuento + impuestos + envío.

        Parameters
        ----------
        order : dict[str, Any]
            Orden a modificar. Se muta in-place.

        """
        error_type = self.rng.choice(["wrong_total", "wrong_subtotal", "wrong_discount"])
        if error_type == "wrong_total":
            order["total_amount"] = round(order["total_amount"] * self.rng.uniform(0.5, 2.0), 2)
        elif error_type == "wrong_subtotal":
            order["subtotal"] = round(order["unit_price"] * order["quantity"] * 1.5, 2)
        else:
            order["discount_amount"] = round(order["subtotal"] * 1.5, 2)  # > 100%

    def _inject_business_logic_error(self, order: dict[str, Any]) -> None:
        """
        Inyecta errores de lógica de negocio.

        Parameters
        ----------
        order : dict[str, Any]
            Orden a modificar. Se muta in-place.

        """
        error_type = self.rng.choice(
            ["negative_qty", "zero_price", "huge_discount", "impossible_days"]
        )
        if error_type == "negative_qty":
            order["quantity"] = -self.rng.randint(1, 5)
        elif error_type == "zero_price":
            order["unit_price"] = 0.0
        elif error_type == "huge_discount":
            order["discount_percent"] = self.rng.choice([110, 150, 200])
        else:
            order["delivery_days"] = -self.rng.randint(1, 10)

    def _inject_referential_error(self, order: dict[str, Any]) -> None:
        """
        Referencia un cliente inexistente.

        Parameters
        ----------
        order : dict[str, Any]
            Orden a modificar. Se muta in-place.

        """
        order["customer_id"] = f"CUST-{self.rng.randint(99990, 99999):05d}"

    def _inject_status_error(self, order: dict[str, Any]) -> None:
        """
        Estado inconsistente con las fechas.

        Parameters
        ----------
        order : dict[str, Any]
            Orden a modificar. Se muta in-place.

        """
        error_type = self.rng.choice(
            ["delivered_no_ship", "shipped_no_order", "cancelled_delivered"]
        )
        if error_type == "delivered_no_ship":
            order["order_status"] = "DELIVERED"
            order["shipping_date"] = None
        elif error_type == "shipped_no_order":
            order["order_status"] = "SHIPPED"
            order["order_date"] = None
        else:
            order["order_status"] = "CANCELLED"
            order["delivery_date"] = (
                (datetime.fromisoformat(order["order_date"]) + timedelta(days=5)).date().isoformat()
            )

    def _inject_amount_error(self, order: dict[str, Any]) -> None:
        """
        Montos negativos o cero donde no deberían.

        Parameters
        ----------
        order : dict[str, Any]
            Orden a modificar. Se muta in-place.

        """
        field = self.rng.choice(["total_amount", "tax_amount", "shipping_cost"])
        order[field] = -abs(order[field]) if order[field] != 0 else -100.0

    def _inject_currency_mismatch(self, order: dict[str, Any]) -> None:
        """
        Moneda inconsistente con el país del cliente.

        Parameters
        ----------
        order : dict[str, Any]
            Orden a modificar. Se muta in-place.

        """
        wrong_currencies = [
            c for c in CURRENCIES_BY_COUNTRY.values() if c != order["customer_currency"]
        ]
        order["customer_currency"] = self.rng.choice(wrong_currencies)

    def generate(self, n_orders: int) -> pd.DataFrame:
        """
        Genera un dataset de órdenes con errores controlados.

        Parameters
        ----------
        n_orders : int
            Número de órdenes a generar.

        Returns
        -------
        pd.DataFrame
            DataFrame con las órdenes generadas.

        Raises
        ------
        ValueError
            Si n_orders es menor o igual a 0.

        Examples
        --------
        >>> gen = OrdersGenerator(seed=42, error_rate=0.2)
        >>> df = gen.generate(n_orders=100)
        >>> len(df)
        100

        """
        if n_orders <= 0:
            raise ValueError(f"n_orders debe ser positivo, recibido: {n_orders}")

        records: list[dict[str, Any]] = []

        with Progress() as progress:
            task = progress.add_task("[cyan]Generando órdenes...", total=n_orders)
            for idx in range(n_orders):
                order = self._generate_valid_order(idx)

                if self._should_inject_error():
                    error_type = self.rng.choice(
                        [
                            "temporal",
                            "calculation",
                            "business_logic",
                            "referential",
                            "status",
                            "amount",
                            "currency",
                        ]
                    )
                    if error_type == "temporal":
                        self._inject_temporal_inversion(order)
                    elif error_type == "calculation":
                        self._inject_calculation_error(order)
                    elif error_type == "business_logic":
                        self._inject_business_logic_error(order)
                    elif error_type == "referential":
                        self._inject_referential_error(order)
                    elif error_type == "status":
                        self._inject_status_error(order)
                    elif error_type == "amount":
                        self._inject_amount_error(order)
                    elif error_type == "currency":
                        self._inject_currency_mismatch(order)

                records.append(order)
                progress.update(task, advance=1)

        return pd.DataFrame(records)


def main() -> None:
    """Punto de entrada CLI para el generador de órdenes."""
    parser = argparse.ArgumentParser(
        description="Genera dataset de órdenes con errores controlados"
    )
    parser.add_argument("--orders", type=int, default=2000, help="Número de órdenes")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/raw/orders.csv"),
        help="Ruta del CSV de salida",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--error-rate", type=float, default=0.20, help="Tasa de errores")
    parser.add_argument("--customers", type=int, default=100, help="Pool de clientes")
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)

    console.print(f"[bold cyan]🛒 Generando {args.orders} órdenes...[/]")
    generator = OrdersGenerator(
        seed=args.seed,
        error_rate=args.error_rate,
        n_customers=args.customers,
    )
    df = generator.generate(n_orders=args.orders)
    df.to_csv(args.output, index=False)

    console.print(f"[bold green]✅ Órdenes guardadas en:[/] {args.output}")
    console.print(f"[dim]Filas: {len(df)} | Columnas: {len(df.columns)}[/]")
    console.print(f"[dim]Columnas: {', '.join(df.columns.tolist())}[/]")


if __name__ == "__main__":
    main()
