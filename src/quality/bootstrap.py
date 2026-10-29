"""
Bootstrap del Data Context de Great Expectations (mode=file).

Este módulo crea y sincroniza, de forma IDEMPOTENTE, todos los
artefactos que el gate de calidad necesita:

1. Data Context basado en archivos (`gx/` versionado en Git).
2. Datasource de filesystem sobre `data/raw/` + assets CSV + batch
   definitions (una por dataset).
3. Suites de expectativas (`customers` y `orders`) reconciliadas contra
   `src/quality/suites.py`.
4. Validation Definitions (qué suite corre sobre qué batch).
5. Checkpoints con acción de Data Docs (evidencia HTML).

Idempotencia: ejecutar este módulo varias veces NO duplica entidades.
Si una suite cambió en el código, se reconcilia (se agregan/eliminan
expectativas) en lugar de recrear todo. Esto permite tratar la calidad
como código: se edita `suites.py`, se corre bootstrap y el contexto
queda sincronizado.
"""

from __future__ import annotations

import json
from typing import Any

import great_expectations as gx
import yaml
from great_expectations.data_context import FileDataContext

from src.quality import config
from src.quality.suites import expectativas_customers, expectativas_orders
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

# Claves del dict de una expectativa que no definen su semántica
# (metadatos de runtime que cambian entre ejecuciones).
_CLAVES_VOLATILES = {
    "id",
    "batch_id",
    "meta",
    "notes",
    "result_format",
    "catch_exceptions",
    "rendered_content",
    "description",
    "windows",
    "success_on_last_run",
    "_expectation_context",
    "_rendered_content",
}


class ErrorBootstrap(Exception):
    """Error controlado de bootstrap con mensaje accionable."""


def _preflight_datos() -> None:
    """
    Verifica que los CSV existan antes de registrar el datasource.

    Raises
    ------
    ErrorBootstrap
        Si falta alguno de los archivos de datos, con instrucciones
        claras para el participante.

    """
    faltantes = [
        archivo
        for archivo in (config.CUSTOMERS_CSV, config.ORDERS_CSV)
        if not (config.DATA_RAW_DIR / archivo).exists()
    ]
    if faltantes:
        raise ErrorBootstrap(
            "No se encontraron los archivos de datos: "
            + ", ".join(faltantes)
            + ". Ejecuta primero: python scripts/generate_data.py --dataset all"
        )


def _firma_expectativa(expectation: Any) -> str:
    """
    Construye una firma canónica de una expectativa.

    La firma ignora metadatos volátiles (ids, notas, formato de
    resultado) y conserva la semántica: tipo, columna, umbrales,
    severidad y demás kwargs de configuración.

    Parameters
    ----------
    expectation : Any
        Objeto Expectation de GX.

    Returns
    -------
    str
        Cadena estable que identifica de forma única la semántica de
        la expectativa.

    """
    config_dict = expectation.dict()
    kwargs = {
        clave: valor
        for clave, valor in config_dict.items()
        if clave not in _CLAVES_VOLATILES and valor is not None
    }
    tipo = type(expectation).__name__
    return f"{tipo}::{json.dumps(kwargs, sort_keys=True, default=str)}"


def _asegurar_salida_limpia() -> None:
    """
    Desactiva las barras de progreso de GX en el YAML del contexto.

    Las barras de métricas ensucian la salida del gate y de los logs de
    CI. La configuración queda persistida en gx/great_expectations.yml
    (versionado), así que solo se escribe la primera vez.
    """
    ruta_yaml = config.GX_ROOT / "great_expectations.yml"
    if not ruta_yaml.exists():
        return

    with ruta_yaml.open("r", encoding="utf-8") as handle:
        contenido = yaml.safe_load(handle) or {}

    if contenido.get("progress_bars") == {"globally": False, "metric_calculations": False}:
        return

    contenido["progress_bars"] = {"globally": False, "metric_calculations": False}
    with ruta_yaml.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(contenido, handle, sort_keys=False, allow_unicode=True)
    logger.info("Barras de progreso de GX desactivadas en great_expectations.yml")


def inicializar_contexto() -> FileDataContext:
    """
    Carga (o crea) el FileDataContext del proyecto.

    El contexto vive en la carpeta `gx/` de la raíz del repositorio y
    se versiona en Git: ese es el corazón de `mode=file`.

    Returns
    -------
    FileDataContext
        Contexto listo para operar.

    """
    _preflight_datos()
    contexto = gx.get_context(mode="file", project_root_dir=str(config.PROJECT_ROOT))
    _asegurar_salida_limpia()
    _desactivar_barras_en_memoria(contexto)
    logger.info("Contexto GX (mode=file) cargado desde %s", config.GX_ROOT)
    return contexto


def _desactivar_barras_en_memoria(contexto: FileDataContext) -> None:
    """
    Aplica la desactivación de barras también al contexto cargado.

    Necesaria en la primera ejecución (cuando el YAML se acaba de
    editar después de crear el contexto) para que la salida del gate
    sea limpia desde el primer run.

    Parameters
    ----------
    contexto : FileDataContext
        Contexto activo.

    """
    from great_expectations.data_context.types.base import ProgressBarsConfig

    barras = contexto.config.progress_bars
    if barras is not None and not bool(barras.get("metric_calculations", True)):
        return

    contexto.config.progress_bars = ProgressBarsConfig(
        globally=False, metric_calculations=False
    )


def _obtener_o_crear_datasource(contexto: FileDataContext):
    """
    Recupera el datasource de filesystem o lo registra si no existe.

    Parameters
    ----------
    contexto : FileDataContext
        Contexto activo.

    Returns
    -------
    PandasFilesystemDatasource
        Datasource apuntando a `data/raw/`.

    """
    nombres = list(contexto.data_sources.all())
    if config.DATASOURCE_NAME in nombres:
        return contexto.data_sources.get(config.DATASOURCE_NAME)

    datasource = contexto.data_sources.add_pandas_filesystem(
        name=config.DATASOURCE_NAME,
        base_directory="data/raw",
    )
    logger.info("Datasource creado: %s (base_directory=data/raw)", config.DATASOURCE_NAME)
    return datasource


def _obtener_o_crear_batch(datasource, asset_name: str, batch_name: str, csv_name: str):
    """
    Recupera o crea el asset CSV y su batch definition.

    Parameters
    ----------
    datasource :
        Datasource de filesystem activo.
    asset_name : str
        Nombre del asset (ej. orders_csv).
    batch_name : str
        Nombre del batch definition.
    csv_name : str
        Archivo CSV relativo a data/raw/.

    Returns
    -------
    BatchDefinition
        Batch definition que apunta al CSV completo.

    """
    assets = {asset.name: asset for asset in datasource.assets}
    asset = assets.get(asset_name)
    if asset is None:
        asset = datasource.add_csv_asset(name=asset_name)
        logger.info("Asset creado: %s", asset_name)

    batch_defs = {bd.name: bd for bd in asset.batch_definitions}
    batch = batch_defs.get(batch_name)
    if batch is None:
        batch = asset.add_batch_definition_path(name=batch_name, path=csv_name)
        logger.info("Batch definition creada: %s -> %s", batch_name, csv_name)
    return batch


def _reconciliar_suite(contexto: FileDataContext, suite_name: str, expectativas: list):
    """
    Crea la suite o la sincroniza con las expectativas deseadas.

    Parameters
    ----------
    contexto : FileDataContext
        Contexto activo.
    suite_name : str
        Nombre de la suite.
    expectativas : list
        Expectativas deseadas (definidas en src/quality/suites.py).

    Returns
    -------
    ExpectationSuite
        Suite sincronizada (persistida en gx/expectations/).

    """
    try:
        suite = contexto.suites.get(suite_name)
    except Exception:
        suite = contexto.suites.add(gx.ExpectationSuite(name=suite_name))
        logger.info("Suite creada: %s", suite_name)

    firmas_deseadas = {_firma_expectativa(e) for e in expectativas}
    firmas_actuales = {_firma_expectativa(e) for e in suite.expectations}

    if firmas_deseadas == firmas_actuales:
        logger.info("Suite '%s' ya sincronizada (%d expectativas).", suite_name, len(suite.expectations))
        return suite

    # Eliminar las que ya no deben existir
    for existente in list(suite.expectations):
        if _firma_expectativa(existente) not in firmas_deseadas:
            suite.delete_expectation(existente)

    # Agregar las faltantes
    firmas_actuales = {_firma_expectativa(e) for e in suite.expectations}
    for deseada in expectativas:
        if _firma_expectativa(deseada) not in firmas_actuales:
            suite.add_expectation(deseada)

    logger.info(
        "Suite '%s' reconciliada: %d expectativas activas.",
        suite_name,
        len(suite.expectations),
    )
    return suite


def _obtener_o_crear_validation_definition(
    contexto: FileDataContext, nombre: str, batch, suite
):
    """
    Recupera o crea la Validation Definition (suite + batch).

    Parameters
    ----------
    contexto : FileDataContext
        Contexto activo.
    nombre : str
        Nombre de la validation definition.
    batch :
        Batch definition (los datos a validar).
    suite :
        Expectation suite (las reglas a aplicar).

    Returns
    -------
    ValidationDefinition
        Vínculo versionado entre datos y reglas.

    """
    try:
        vd = contexto.validation_definitions.get(nombre)
        return vd
    except Exception:
        vd = gx.ValidationDefinition(name=nombre, data=batch, suite=suite)
        vd = contexto.validation_definitions.add(vd)
        logger.info("Validation definition creada: %s", nombre)
        return vd


def _obtener_o_crear_checkpoint(contexto: FileDataContext, nombre: str, vd):
    """
    Recupera o crea el checkpoint con acción de Data Docs.

    Parameters
    ----------
    contexto : FileDataContext
        Contexto activo.
    nombre : str
        Nombre del checkpoint.
    vd :
        Validation definition a ejecutar.

    Returns
    -------
    Checkpoint
        Checkpoint listo para `run()`.

    """
    try:
        return contexto.checkpoints.get(nombre)
    except Exception:
        checkpoint = gx.Checkpoint(
            name=nombre,
            validation_definitions=[vd],
            actions=[
                gx.checkpoint.UpdateDataDocsAction(name="update_data_docs")
            ],
            result_format=config.RESULT_FORMAT,
        )
        checkpoint = contexto.checkpoints.add(checkpoint)
        logger.info("Checkpoint creado: %s", nombre)
        return checkpoint


def ejecutar_bootstrap() -> FileDataContext:
    """
    Ejecuta el bootstrap completo del contexto GX.

    Orden de creación: contexto -> datasource -> assets/batches ->
    suites reconciliadas -> validation definitions -> checkpoints.

    Returns
    -------
    FileDataContext
        Contexto completamente sincronizado.

    """
    contexto = inicializar_contexto()

    datasource = _obtener_o_crear_datasource(contexto)

    # --- customers ---
    batch_customers = _obtener_o_crear_batch(
        datasource,
        config.CUSTOMERS_ASSET,
        config.CUSTOMERS_BATCH_DEF,
        config.CUSTOMERS_CSV,
    )
    suite_customers = _reconciliar_suite(
        contexto, config.CUSTOMERS_SUITE, expectativas_customers()
    )
    vd_customers = _obtener_o_crear_validation_definition(
        contexto, config.CUSTOMERS_VALIDATION_DEF, batch_customers, suite_customers
    )
    _obtener_o_crear_checkpoint(contexto, config.CUSTOMERS_CHECKPOINT, vd_customers)

    # --- orders ---
    batch_orders = _obtener_o_crear_batch(
        datasource,
        config.ORDERS_ASSET,
        config.ORDERS_BATCH_DEF,
        config.ORDERS_CSV,
    )
    suite_orders = _reconciliar_suite(
        contexto, config.ORDERS_SUITE, expectativas_orders(pool_clientes=config.CUSTOMERS_POOL_SIZE)
    )
    vd_orders = _obtener_o_crear_validation_definition(
        contexto, config.ORDERS_VALIDATION_DEF, batch_orders, suite_orders
    )
    _obtener_o_crear_checkpoint(contexto, config.ORDERS_CHECKPOINT, vd_orders)

    logger.info("Bootstrap completado: contexto GX sincronizado y versionado.")
    return contexto


if __name__ == "__main__":  # pragma: no cover
    ejecutar_bootstrap()
