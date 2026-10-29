"""
Gate de calidad: ejecuta los checkpoints y decide si los datos avanzan.

La política del gate (inspirada en la diapositiva 26 del material del
módulo) es simple y explícita:

- Si una expectativa `critical` falla  ->  el gate BLOQUEA (exit code 1).
- Si solo fallan expectativas `info`   ->  el gate ADVIERTE pero permite
  avanzar; la evidencia queda en Data Docs para observabilidad.

Este módulo es el único punto del proyecto que decide el exit code, de
modo que cualquier orquestador futuro (Airflow en unidad 5, CI/CD en la
unidad 5) pueda invocarlo y heredar la misma política sin reescribirla.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from great_expectations.data_context import FileDataContext
from great_expectations.expectations.metadata_types import FailureSeverity

from src.quality import config
from src.quality.bootstrap import inicializar_contexto
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

RUTA_DATA_DOCS = (
    config.GX_ROOT / "uncommitted" / "data_docs" / "local_site" / "index.html"
)


@dataclass
class FallaExpectativa:
    """Detalle de una expectativa que no se cumplió."""

    tipo: str
    columna: str
    severidad: str
    descripcion: str
    total_filas: int
    filas_invalidas: int
    porcentaje: float

    def como_fila(self) -> tuple[str, str, str, str, str]:
        """Devuelve la falla como fila legible para tablas de consola."""
        return (
            self.severidad.upper(),
            self.tipo.replace("expect_column_", "").replace("expect_table_", "tabla."),
            self.columna or "-",
            f"{self.filas_invalidas}/{self.total_filas}",
            f"{self.porcentaje:.2f}%",
        )


@dataclass
class ResumenValidacion:
    """Resultado agregado de un checkpoint con la lectura del gate."""

    dataset: str
    checkpoint: str
    run_id: str
    fecha_ejecucion: str
    evaluadas: int = 0
    exitosas: int = 0
    fallidas: int = 0
    fallas: list[FallaExpectativa] = field(default_factory=list)

    @property
    def fallas_criticas(self) -> list[FallaExpectativa]:
        """Expectativas críticas que fallaron (bloquean el pipeline)."""
        return [f for f in self.fallas if f.severidad == "critical"]

    @property
    def fallas_informativas(self) -> list[FallaExpectativa]:
        """Expectativas informativas que fallaron (no bloquean)."""
        return [f for f in self.fallas if f.severidad != "critical"]

    @property
    def decision(self) -> str:
        """Lectura operativa del resultado: AVANZA o BLOQUEA."""
        return "BLOQUEA" if self.fallas_criticas else "AVANZA"

    @property
    def exit_code(self) -> int:
        """Código de salida para shell, CI y orquestadores."""
        return 1 if self.fallas_criticas else 0

    @property
    def porcentaje_exito(self) -> float:
        """Porcentaje de expectativas cumplidas."""
        if self.evaluadas == 0:
            return 0.0
        return 100.0 * self.exitosas / self.evaluadas


def _descripcion(expectation_config) -> str:
    """Extrae la descripción legible de la expectativa (si existe)."""
    desc = getattr(expectation_config, "description", None)
    return desc or "Sin descripción"


def ejecutar_checkpoint(contexto: FileDataContext, checkpoint_name: str, dataset: str) -> ResumenValidacion:
    """
    Ejecuta un checkpoint y traduce su resultado a la política del gate.

    Parameters
    ----------
    contexto : FileDataContext
        Contexto GX activo.
    checkpoint_name : str
        Nombre del checkpoint a ejecutar.
    dataset : str
        Etiqueta legible del dataset (customers / orders).

    Returns
    -------
    ResumenValidacion
        Resumen con la decisión del gate para el dataset.

    """
    checkpoint = contexto.checkpoints.get(checkpoint_name)
    resultado = checkpoint.run()

    resumen = ResumenValidacion(
        dataset=dataset,
        checkpoint=checkpoint_name,
        run_id=str(resultado.run_id),
        fecha_ejecucion=str(getattr(resultado, "created_at", "")),
    )

    for _, val in resultado.run_results.items():
        stats = val["statistics"]
        resumen.evaluadas += stats["evaluated_expectations"]
        resumen.exitosas += stats["successful_expectations"]
        resumen.fallidas += stats["unsuccessful_expectations"]

        for res in val["results"]:
            if res.success:
                continue

            exp_cfg = res.expectation_config
            kwargs = exp_cfg.kwargs
            detalle = res.result if isinstance(res.result, dict) else {}
            severidad = getattr(exp_cfg.severity, "value", str(exp_cfg.severity))

            resumen.fallas.append(
                FallaExpectativa(
                    tipo=str(exp_cfg.type),
                    columna=str(kwargs.get("column") or ""),
                    severidad=severidad,
                    descripcion=_descripcion(exp_cfg),
                    total_filas=int(detalle.get("element_count", 0)),
                    filas_invalidas=int(detalle.get("unexpected_count", 0)),
                    porcentaje=float(detalle.get("unexpected_percent", 0.0) or 0.0),
                )
            )

    return resumen


def ejecutar_gate(datasets: list[str] | None = None) -> int:
    """
    Ejecuta el gate completo e imprime el resumen operativo.

    Parameters
    ----------
    datasets : list[str] | None, optional
        Subconjunto a validar: ["customers"], ["orders"] o None para ambos.

    Returns
    -------
    int
        0 si ningún dataset tuvo fallas críticas; 1 si al menos uno
        debe bloquearse.

    """
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console()

    seleccion = {
        "customers": (config.CUSTOMERS_CHECKPOINT, "Customers"),
        "orders": (config.ORDERS_CHECKPOINT, "Orders"),
    }
    if datasets is None:
        datasets = list(seleccion.keys())

    contexto = inicializar_contexto()

    resumenes: list[ResumenValidacion] = []
    for dataset in datasets:
        checkpoint_name, etiqueta = seleccion[dataset]
        console.print(f"[bold cyan]Validando dataset:[/] {etiqueta}")
        resumenes.append(ejecutar_checkpoint(contexto, checkpoint_name, dataset))

    # ------------------------------------------------------------------
    # Resumen operativo en consola
    # ------------------------------------------------------------------
    tabla = Table(title="Gate de calidad · resumen por dataset", show_lines=True)
    tabla.add_column("Dataset", style="cyan")
    tabla.add_column("Expectativas", justify="right")
    tabla.add_column("Exitosas", justify="right", style="green")
    tabla.add_column("Fallidas", justify="right", style="yellow")
    tabla.add_column("Críticas fallidas", justify="right", style="red")
    tabla.add_column("Decisión", justify="center")

    for r in resumenes:
        tabla.add_row(
            r.dataset,
            str(r.evaluadas),
            str(r.exitosas),
            str(r.fallidas),
            str(len(r.fallas_criticas)),
            r.decision,
        )
    console.print(tabla)

    for r in resumenes:
        if not r.fallas:
            continue
        detalle = Table(title=f"Fallas detectadas · {r.dataset}")
        detalle.add_column("Severidad")
        detalle.add_column("Regla")
        detalle.add_column("Columna")
        detalle.add_column("Filas inválidas", justify="right")
        detalle.add_column("% violado", justify="right")
        for f in r.fallas:
            estilo = "red" if f.severidad == "critical" else "yellow"
            detalle.add_row(*f.como_fila(), style=estilo)
        console.print(detalle)

    bloqueados = [r for r in resumenes if r.fallas_criticas]
    if bloqueados:
        console.print(
            Panel(
                f"[bold red]GATE BLOQUEADO[/] · datasets con fallas críticas: "
                f"{', '.join(r.dataset for r in bloqueados)}\n"
                f"Los datos NO deben avanzar hacia downstream. Revisa Data Docs.",
                border_style="red",
            )
        )
    else:
        console.print(
            Panel(
                "[bold green]GATE EN VERDE[/] · todos los datasets cumplen "
                "sus reglas críticas. Evidencia disponible en Data Docs.",
                border_style="green",
            )
        )

    console.print(f"[dim]Data Docs: {RUTA_DATA_DOCS}[/]")
    console.print(f"[dim]run_id: {resumenes[0].run_id if resumenes else '-'}[/]")

    return max((r.exit_code for r in resumenes), default=0)
