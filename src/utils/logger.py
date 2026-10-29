"""
Configuración de logging estructurado para el proyecto.

Este módulo centraliza la creación de loggers con formato consistente,
de modo que todos los componentes (generadores, bootstrap, gate de
calidad) emitan evidencia operativa legible y correlacionable.

En un pipeline DataOps el log es evidencia: registra quién ejecutó,
qué componente corrió, con qué parámetros y en qué momento. Por eso
el formato incluye timestamp, nivel, módulo y mensaje, y además se
consolida un archivo de log por ejecución en `logs/`.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Formato único para todo el proyecto (evidencia operativa básica)
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Directorio donde se consolidan los logs de ejecución
LOGS_DIR = Path("logs")

# Evita duplicar handlers cuando se llama a setup_logger más de una vez
_LOGGERS_CONFIGURADOS: set[str] = set()


def setup_logger(name: str, log_to_file: bool = True) -> logging.Logger:
    """
    Crea (o recupera) un logger con formato consistente del proyecto.

    Parameters
    ----------
    name : str
        Nombre del logger; por convención se usa ``__name__`` del módulo
        que lo solicita.
    log_to_file : bool, optional
        Si es True, además de la consola escribe en ``logs/ejecucion.log``
        con rotación de 1 MB, por defecto True.

    Returns
    -------
    logging.Logger
        Logger configurado y listo para usar.

    Examples
    --------
    >>> from src.utils.logger import setup_logger
    >>> logger = setup_logger(__name__)
    >>> logger.info("componente inicializado")

    """
    logger = logging.getLogger(name)

    # Logger ya configurado en este proceso: no duplicar handlers
    if name in _LOGGERS_CONFIGURADOS:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # Handler de consola (salida estándar)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Handler de archivo con rotación (evidencia persistente)
    if log_to_file:
        try:
            LOGS_DIR.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                LOGS_DIR / "ejecucion.log",
                maxBytes=1_000_000,
                backupCount=3,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except OSError:
            # Si no se puede escribir el archivo (ej. permisos),
            # el pipeline sigue funcionando solo con consola.
            logger.warning("No se pudo crear el archivo de log; solo consola.")

    logger.propagate = False
    _LOGGERS_CONFIGURADOS.add(name)
    return logger
