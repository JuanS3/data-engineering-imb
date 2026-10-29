"""
Definición de las suites de expectativas del taller.

Este módulo declara, como código revisable, TODAS las expectativas de
calidad que el proyecto exige para los datasets `customers` y `orders`.
Cada expectativa está anotada con:

- La dimensión de calidad que protege (Módulo 5 · Unidad 1).
- La severidad (`severity`) que define la política del gate:
    * "critical": si falla, el gate BLOQUEA (exit code 1).
    * "info": se reporta en Data Docs como observabilidad, no bloquea.
- El umbral `mostly` cuando corresponde: proporción mínima de filas que
  deben cumplir la regla (ej. mostly=0.98 tolera hasta 2% de violaciones).

Regla del taller: una expectativa sin dueño ni consecuencia es ruido.
Aquí cada regla tiene consecuencia (bloquea o informa) y la evidencia
queda registrada en Data Docs.
"""

from __future__ import annotations

import great_expectations as gx

from src.quality.config import MOSTLY_CRITICO, MOSTLY_INFO

# ---------------------------------------------------------------------------
# Dominios de negocio compartidos con los generadores de datos
# ---------------------------------------------------------------------------
PAISES_VALIDOS: list[str] = ["México", "España", "Argentina", "Colombia", "Chile"]

CATEGORIAS_PRODUCTO: list[str] = [
    "ELECTRONICS",
    "CLOTHING",
    "HOME",
    "BOOKS",
    "SPORTS",
]

METODOS_PAGO: list[str] = [
    "CREDIT_CARD",
    "DEBIT_CARD",
    "PAYPAL",
    "BANK_TRANSFER",
    "CASH_ON_DELIVERY",
    "CRYPTO",
]

METODOS_ENVIO: list[str] = ["STANDARD", "EXPRESS", "SAME_DAY", "ECONOMIC"]

ESTADOS_ORDEN: list[str] = [
    "PENDING",
    "PROCESSING",
    "SHIPPED",
    "IN_TRANSIT",
    "DELIVERED",
    "CANCELLED",
    "REFUNDED",
]

# Umbral del presupuesto de error para reglas críticas con tolerancia
MOSTLY: float = MOSTLY_CRITICO
MOSTLY_INFORMATIVO: float = MOSTLY_INFO


# ---------------------------------------------------------------------------
# SUITE: customers
# ---------------------------------------------------------------------------
CUSTOMERS_COLUMNAS: list[str] = [
    "customer_id",
    "first_name",
    "last_name",
    "email",
    "age",
    "birth_date",
    "country",
    "city",
    "annual_income",
    "credit_score",
    "registration_date",
    "last_update",
]


def expectativas_customers() -> list:
    """
    Suite `customers_critical_suite`: valida el dataset de clientes.

    Protege las 6 dimensiones de calidad vistas en la Unidad 1:
    completitud, unicidad, validez, consistencia, exactitud y oportunidad.

    Returns
    -------
    list
        Objetos Expectation listos para agregarse a la suite.

    """
    return [
        # --- Contrato de esquema: estructura prometida a los consumidores ---
        gx.expectations.ExpectTableColumnsToMatchSet(
            column_set=CUSTOMERS_COLUMNAS,
            exact_match=True,
            severity="critical",
            description="Contrato: las 12 columnas acordadas, ni más ni menos.",
        ),
        # --- Volumen plausible: no validar un archivo truncado ---
        gx.expectations.ExpectTableRowCountToBeBetween(
            min_value=100,
            max_value=1_000_000,
            severity="critical",
            description="Volumen: al menos 100 clientes en la carga.",
        ),
        # --- Unicidad de la clave natural ---
        gx.expectations.ExpectColumnValuesToBeUnique(
            column="customer_id",
            severity="critical",
            description="Unicidad: customer_id es la clave natural.",
        ),
        gx.expectations.ExpectColumnValuesToNotBeNull(
            column="customer_id",
            severity="critical",
            description="Completitud: la clave no puede ser nula.",
        ),
        # --- Completitud con presupuesto de error (1%) ---
        gx.expectations.ExpectColumnValuesToNotBeNull(
            column="email",
            mostly=MOSTLY,
            severity="critical",
            description="Completitud: email nulo bloquea si supera 1%.",
        ),
        gx.expectations.ExpectColumnValuesToNotBeNull(
            column="age",
            mostly=MOSTLY,
            severity="critical",
            description="Completitud: edad nula bloquea si supera 1%.",
        ),
        # --- Validez de formatos y dominios (informativas) ---
        gx.expectations.ExpectColumnValuesToMatchRegex(
            column="email",
            regex=r"^[\w.+-]+@[\w-]+\.[\w.-]+$",
            mostly=MOSTLY_INFORMATIVO,
            severity="info",
            description="Validez: formato de email razonable.",
        ),
        gx.expectations.ExpectColumnValuesToBeDateutilParseable(
            column="birth_date",
            mostly=MOSTLY_INFORMATIVO,
            severity="info",
            description="Validez: birth_date es una fecha parseable.",
        ),
        gx.expectations.ExpectColumnValuesToMatchRegex(
            column="registration_date",
            regex=r"^\d{4}-\d{2}-\d{2}$",
            mostly=MOSTLY_INFORMATIVO,
            severity="info",
            description="Validez: registration_date en formato ISO.",
        ),
        gx.expectations.ExpectColumnValuesToBeInSet(
            column="country",
            value_set=PAISES_VALIDOS,
            severity="critical",
            description="Validez: país dentro del dominio de negocio.",
        ),
        # --- Exactitud de rangos reales ---
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="age",
            min_value=18,
            max_value=85,
            mostly=MOSTLY_INFORMATIVO,
            severity="info",
            description="Exactitud: edad dentro del rango plausible.",
        ),
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="annual_income",
            min_value=0,
            max_value=1_000_000,
            mostly=MOSTLY,
            severity="critical",
            description="Exactitud: ingreso anual fuera de rango bloquea a >1%.",
        ),
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="credit_score",
            min_value=300,
            max_value=850,
            mostly=MOSTLY,
            severity="critical",
            description="Exactitud: score de crédito fuera del dominio bloquea a >1%.",
        ),
        # --- Oportunidad (frescura) del registro ---
        gx.expectations.ExpectColumnValuesToMatchRegex(
            column="last_update",
            regex=r"^202[0-9]-",
            mostly=MOSTLY,
            severity="critical",
            description="Oportunidad: registros con datos de 2019 o anteriores bloquean a >1%.",
        ),
    ]


# ---------------------------------------------------------------------------
# SUITE: orders
# ---------------------------------------------------------------------------
ORDERS_COLUMNAS: list[str] = [
    "order_id",
    "customer_id",
    "customer_country",
    "customer_currency",
    "customer_registration_date",
    "order_date",
    "product_category",
    "product_name",
    "unit_price",
    "quantity",
    "subtotal",
    "discount_percent",
    "discount_amount",
    "tax_rate",
    "tax_amount",
    "shipping_method",
    "shipping_cost",
    "shipping_date",
    "delivery_date",
    "delivery_days",
    "payment_method",
    "total_amount",
    "order_status",
    "is_returned",
    "return_date",
]


def expectativas_orders(pool_clientes: int = 100) -> list:
    """
    Suite `orders_critical_suite`: valida el dataset de órdenes.

    Protege reglas de negocio cross-field: cálculo financiero, jerarquía
    temporal (registro -> compra -> envío -> entrega), estados coherentes
    e integridad referencial con el pool de clientes.

    Parameters
    ----------
    pool_clientes : int, optional
        Tamaño del pool de clientes generado (CUST-00000 .. CUST-<N-1>),
        por defecto 100. Debe coincidir con el parámetro del generador.

    Returns
    -------
    list
        Objetos Expectation listos para agregarse a la suite.

    """
    dominio_clientes: list[str] = [f"CUST-{i:05d}" for i in range(pool_clientes)]

    return [
        # --- Contrato de esquema ---
        gx.expectations.ExpectTableColumnsToMatchSet(
            column_set=ORDERS_COLUMNAS,
            exact_match=True,
            severity="critical",
            description="Contrato: las 25 columnas acordadas del dataset de órdenes.",
        ),
        # --- Volumen plausible ---
        gx.expectations.ExpectTableRowCountToBeBetween(
            min_value=100,
            max_value=1_000_000,
            severity="critical",
            description="Volumen: al menos 100 órdenes en la carga.",
        ),
        # --- Unicidad y completitud de la clave ---
        gx.expectations.ExpectColumnValuesToBeUnique(
            column="order_id",
            severity="critical",
            description="Unicidad: order_id es la clave natural de la orden.",
        ),
        gx.expectations.ExpectColumnValuesToNotBeNull(
            column="order_id",
            severity="critical",
            description="Completitud: la clave no puede ser nula.",
        ),
        gx.expectations.ExpectColumnValuesToNotBeNull(
            column="customer_id",
            severity="critical",
            description="Completitud: toda orden pertenece a un cliente.",
        ),
        # --- Integridad referencial con el pool de clientes ---
        gx.expectations.ExpectColumnValuesToBeInSet(
            column="customer_id",
            value_set=dominio_clientes,
            mostly=MOSTLY,
            severity="critical",
            description="Referencial: el cliente de la orden debe existir en el pool (tolerancia 1%).",
        ),
        # --- Jerarquía temporal (fechas presentes y en orden) ---
        gx.expectations.ExpectColumnValuesToNotBeNull(
            column="order_date",
            mostly=MOSTLY,
            severity="critical",
            description="Temporal: fecha de compra obligatoria (>1% nula bloquea).",
        ),
        gx.expectations.ExpectColumnValuesToNotBeNull(
            column="shipping_date",
            mostly=MOSTLY,
            severity="critical",
            description="Temporal: fecha de envío obligatoria (>1% nula bloquea).",
        ),
        gx.expectations.ExpectColumnPairValuesAToBeGreaterThanB(
            column_A="order_date",
            column_B="customer_registration_date",
            or_equal=True,
            mostly=MOSTLY_INFORMATIVO,
            severity="info",
            description="Temporal: no se compra antes de registrarse.",
        ),
        gx.expectations.ExpectColumnPairValuesAToBeGreaterThanB(
            column_A="delivery_date",
            column_B="shipping_date",
            or_equal=True,
            mostly=MOSTLY_INFORMATIVO,
            severity="info",
            description="Temporal: la entrega no precede al envío.",
        ),
        # --- Lógica de negocio: montos y cantidades ---
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="quantity",
            min_value=1,
            max_value=5,
            mostly=MOSTLY_INFORMATIVO,
            severity="info",
            description="Negocio: cantidad vendida entre 1 y 5 unidades.",
        ),
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="unit_price",
            min_value=0.01,
            max_value=100_000,
            mostly=MOSTLY_INFORMATIVO,
            severity="info",
            description="Negocio: precio unitario positivo.",
        ),
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="discount_percent",
            min_value=0,
            max_value=100,
            mostly=MOSTLY_INFORMATIVO,
            severity="info",
            description="Negocio: descuento entre 0% y 100%.",
        ),
        gx.expectations.ExpectColumnPairValuesAToBeGreaterThanB(
            column_A="subtotal",
            column_B="discount_amount",
            or_equal=True,
            mostly=MOSTLY,
            severity="critical",
            description="Negocio: el descuento no puede superar el subtotal (>1% bloquea).",
        ),
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="total_amount",
            min_value=0,
            max_value=10_000_000,
            mostly=MOSTLY_INFORMATIVO,
            severity="info",
            description="Negocio: total no negativo ni astronómico.",
        ),
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="delivery_days",
            min_value=0,
            max_value=30,
            mostly=MOSTLY_INFORMATIVO,
            severity="info",
            description="Negocio: duración de entrega plausible (0 a 30 días).",
        ),
        # --- Dominios de negocio ---
        gx.expectations.ExpectColumnValuesToBeInSet(
            column="product_category",
            value_set=CATEGORIAS_PRODUCTO,
            severity="critical",
            description="Dominio: categoría de producto válida.",
        ),
        gx.expectations.ExpectColumnValuesToBeInSet(
            column="payment_method",
            value_set=METODOS_PAGO,
            severity="critical",
            description="Dominio: método de pago válido.",
        ),
        gx.expectations.ExpectColumnValuesToBeInSet(
            column="shipping_method",
            value_set=METODOS_ENVIO,
            severity="critical",
            description="Dominio: método de envío válido.",
        ),
        gx.expectations.ExpectColumnValuesToBeInSet(
            column="order_status",
            value_set=ESTADOS_ORDEN,
            severity="critical",
            description="Dominio: estado de la orden válido.",
        ),
    ]
