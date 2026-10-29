"""
Configuración centralizada del gate de calidad.

Este módulo concentra los nombres, rutas y umbrales que usan el
bootstrap del contexto GX y la ejecución del gate. Centralizarlos
aquí (en lugar de repartirlos por el código) es una práctica DataOps:
cualquier cambio de parámetro queda registrado en un único commit y
es revisable en un pull request.

La distinción CRÍTICO vs INFORMATIVO es la base de la política del gate:

- Expectativa CRÍTICA: su violación BLOQUEA el pipeline (exit code 1).
- Expectativa INFORMATIVA: se reporta en Data Docs pero no bloquea;
  sirve para observar deriva antes de que se vuelva un incidente.

En GX 1.x una expectativa con ``mostly`` exige que el porcentaje de
valores correctos supere ese umbral. Combinamos ``mostly`` con la
clasificación crítico/informativa para expresar severidad.
"""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# Rutas del proyecto (todas relativas a la raíz del repositorio)
# ---------------------------------------------------------------------------
PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
DATA_RAW_DIR: Path = PROJECT_ROOT / "data" / "raw"
GX_ROOT: Path = PROJECT_ROOT / "gx"

CUSTOMERS_CSV: str = "customers.csv"
ORDERS_CSV: str = "orders.csv"

# ---------------------------------------------------------------------------
# Identificadores del contexto GX (mode=file)
# ---------------------------------------------------------------------------
DATASOURCE_NAME: str = "local_filesystem"
CUSTOMERS_ASSET: str = "customers_csv"
ORDERS_ASSET: str = "orders_csv"

CUSTOMERS_BATCH_DEF: str = "customers_batch_completo"
ORDERS_BATCH_DEF: str = "orders_batch_completo"

CUSTOMERS_SUITE: str = "customers_critical_suite"
ORDERS_SUITE: str = "orders_critical_suite"

CUSTOMERS_VALIDATION_DEF: str = "customers_validation_def"
ORDERS_VALIDATION_DEF: str = "orders_validation_def"

CUSTOMERS_CHECKPOINT: str = "customers_checkpoint"
ORDERS_CHECKPOINT: str = "orders_checkpoint"

# ---------------------------------------------------------------------------
# Parámetros de negocio usados por las validaciones
# ---------------------------------------------------------------------------
# El generador de clientes crea un pool de CUST-00000 .. CUST-00099.
# Cualquier customer_id fuera de ese dominio es una violación referencial.
CUSTOMERS_POOL_SIZE: int = 100

# Presupuesto de error tolerado (proporción de filas que pueden fallar)
# antes de considerar violada una expectativa con `mostly`.
#
# MOSTLY_CRITICO = 0.99 -> las reglas críticas tolerantes admiten hasta
#                          un 1% de filas problemáticas antes de bloquear.
# MOSTLY_INFO    = 0.97 -> las reglas informativas (no bloquean) admiten
#                          hasta un 3%: son señal de deriva, no bloqueo.
#
# Estos umbrales son DECISIONES DE NEGOCIO: en un caso real los fija el
# data owner junto al gate de calidad (diapositiva 26 del módulo).
MOSTLY_CRITICO: float = 0.99
MOSTLY_INFO: float = 0.97

# Número mínimo de filas para considerar la ejecución plausible
# (control de volumen; evita validar un archivo truncado).
ROW_COUNT_MIN_CUSTOMERS: int = 100
ROW_COUNT_MIN_ORDERS: int = 100

# ---------------------------------------------------------------------------
# Formato de resultados del checkpoint
# ---------------------------------------------------------------------------
RESULT_FORMAT: dict = {"result_format": "SUMMARY"}
