"""Probabilidades 1X2: cuotas sin margen y modelo Poisson propio (tarea 5; design.md D3-D4).

Python puro, sin ORM: el servicio de pronóstico construye los ``PartidoModelo``.

Modelo (Maher / Dixon-Coles con decaimiento temporal):
    λ_local     = exp(μ_div + h + ataque_local     + defensa_visitante)
    λ_visitante = exp(μ_div +     ataque_visitante + defensa_local)
``defensa`` mide cuánto encaja un equipo (más alto = peor defensa). ``μ_div``
separa el nivel goleador de Primera y Segunda; los equipos que cambian de
división enlazan ambas escalas. Ajuste por máxima verosimilitud ponderada con
pesos ``exp(-ξ·días)`` mediante actualizaciones coordenada a coordenada en forma
cerrada, que convergen de forma monótona en este modelo log-lineal.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

MAX_GOLES = 10
CATEGORIAS_PLENO = ("0", "1", "2", "M")


# --------------------------------------------------------------------------- #
# Cuotas → probabilidades
# --------------------------------------------------------------------------- #


def probs_desde_cuotas(o1: float, ox: float, o2: float, metodo: str = "proporcional") -> tuple[float, float, float]:
    """Probabilidades implícitas sin margen. ``metodo``: ``proporcional`` o ``shin``."""
    cuotas = [float(o1), float(ox), float(o2)]
    if any(c <= 1 for c in cuotas):
        raise ValueError(f"Cuotas inválidas: {cuotas}")
    inversas = [1 / c for c in cuotas]
    total = sum(inversas)
    if metodo == "proporcional" or total <= 1:
        return tuple(x / total for x in inversas)  # type: ignore[return-value]
    if metodo != "shin":
        raise ValueError(f"Método desconocido: {metodo}")

    def shin(z: float) -> list[float]:
        return [
            (math.sqrt(z * z + 4 * (1 - z) * x * x / total) - z) / (2 * (1 - z))
            for x in inversas
        ]

    bajo, alto = 0.0, 0.4
    for _ in range(100):  # bisección: suma(shin(z)) decrece con z
        medio = (bajo + alto) / 2
        if sum(shin(medio)) > 1:
            bajo = medio
        else:
            alto = medio
    probs = shin((bajo + alto) / 2)
    suma = sum(probs)
    return tuple(p / suma for p in probs)  # type: ignore[return-value]


# --------------------------------------------------------------------------- #
# Modelo Poisson
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class PartidoModelo:
    fecha: date
    division: str
    local: int
    visitante: int
    goles_local: int
    goles_visitante: int


@dataclass
class ModeloPoisson:
    ataque: dict[int, float]
    defensa: dict[int, float]
    mu: dict[str, float]
    h: float
    partidos_por_equipo: dict[int, int]
    division_actual: dict[int, str]
    rho: float = 0.0
    iteraciones: int = 0

    def conoce(self, equipo: int, minimo: int) -> bool:
        return self.partidos_por_equipo.get(equipo, 0) >= minimo

    def lambdas(self, local: int, visitante: int, division: str | None = None) -> tuple[float, float]:
        """Goles esperados. La división por defecto es la más reciente del local."""
        div = division or self.division_actual.get(local) or next(iter(self.mu))
        mu = self.mu.get(div, sum(self.mu.values()) / len(self.mu))
        lam_l = math.exp(mu + self.h + self.ataque[local] + self.defensa[visitante])
        lam_v = math.exp(mu + self.ataque[visitante] + self.defensa[local])
        return lam_l, lam_v

    def matriz_goles(self, local: int, visitante: int, division: str | None = None) -> list[list[float]]:
        lam_l, lam_v = self.lambdas(local, visitante, division)
        return matriz_goles(lam_l, lam_v, self.rho)

    def predecir(self, local: int, visitante: int, division: str | None = None) -> tuple[float, float, float]:
        return probs_1x2(self.matriz_goles(local, visitante, division))


def _poisson(k: int, lam: float) -> float:
    return math.exp(-lam) * lam**k / math.factorial(k)


def matriz_goles(lam_l: float, lam_v: float, rho: float = 0.0) -> list[list[float]]:
    """P(goles_local=i, goles_visitante=j) para i, j ∈ [0, MAX_GOLES], normalizada.

    ``rho`` es la corrección de Dixon-Coles en marcadores bajos (0 = Poisson
    independiente; negativo = más empates 0-0 y 1-1).
    """
    pl = [_poisson(i, lam_l) for i in range(MAX_GOLES + 1)]
    pv = [_poisson(j, lam_v) for j in range(MAX_GOLES + 1)]
    m = [[pl[i] * pv[j] for j in range(MAX_GOLES + 1)] for i in range(MAX_GOLES + 1)]
    if rho:
        m[0][0] *= max(0.0, 1 - lam_l * lam_v * rho)
        m[0][1] *= max(0.0, 1 + lam_l * rho)
        m[1][0] *= max(0.0, 1 + lam_v * rho)
        m[1][1] *= max(0.0, 1 - rho)
    total = sum(sum(fila) for fila in m)
    return [[v / total for v in fila] for fila in m]


def probs_1x2(m: list[list[float]]) -> tuple[float, float, float]:
    n = len(m)
    p1 = sum(m[i][j] for i in range(n) for j in range(n) if i > j)
    px = sum(m[i][i] for i in range(n))
    p2 = sum(m[i][j] for i in range(n) for j in range(n) if i < j)
    return p1, px, p2


def distribucion_pleno(m: list[list[float]]) -> dict[str, float]:
    """Agrega la matriz de goles a las 16 combinaciones del Pleno al 15 ("0-0" … "M-M")."""

    def cat(goles: int) -> str:
        return "M" if goles >= 3 else str(goles)

    dist = {f"{a}-{b}": 0.0 for a in CATEGORIAS_PLENO for b in CATEGORIAS_PLENO}
    for i, fila in enumerate(m):
        for j, p in enumerate(fila):
            dist[f"{cat(i)}-{cat(j)}"] += p
    return dist


def ajustar_modelo(
    partidos: list[PartidoModelo],
    fecha_corte: date,
    xi: float = 0.0019,
    rho: float = 0.0,
    max_iter: int = 200,
    tol: float = 1e-7,
) -> ModeloPoisson:
    """Ajusta el modelo con los partidos **estrictamente anteriores** a ``fecha_corte``."""
    datos = [p for p in partidos if p.fecha < fecha_corte]
    if not datos:
        raise ValueError("No hay partidos anteriores a la fecha de corte.")
    pesos = [math.exp(-xi * (fecha_corte - p.fecha).days) for p in datos]

    equipos = sorted({p.local for p in datos} | {p.visitante for p in datos})
    divisiones = sorted({p.division for p in datos})
    ataque = dict.fromkeys(equipos, 0.0)
    defensa = dict.fromkeys(equipos, 0.0)
    total_goles = sum(w * (p.goles_local + p.goles_visitante) for w, p in zip(pesos, datos, strict=True))
    total_partidos = sum(pesos)
    mu = dict.fromkeys(divisiones, math.log(max(total_goles / (2 * total_partidos), 1e-6)))
    h = 0.0

    # Sumas fijas (numeradores) por parámetro.
    marcados: dict[int, float] = defaultdict(float)
    encajados: dict[int, float] = defaultdict(float)
    goles_div: dict[str, float] = defaultdict(float)
    goles_casa = 0.0
    for w, p in zip(pesos, datos, strict=True):
        marcados[p.local] += w * p.goles_local
        marcados[p.visitante] += w * p.goles_visitante
        encajados[p.local] += w * p.goles_visitante
        encajados[p.visitante] += w * p.goles_local
        goles_div[p.division] += w * (p.goles_local + p.goles_visitante)
        goles_casa += w * p.goles_local

    def log_ratio(num: float, den: float) -> float:
        return math.log(max(num, 1e-9) / max(den, 1e-12))

    iteraciones = 0
    for iteraciones in range(1, max_iter + 1):  # noqa: B007 (se usa tras el bucle)
        cambio = 0.0

        den: dict[int, float] = defaultdict(float)
        for w, p in zip(pesos, datos, strict=True):
            den[p.local] += w * math.exp(mu[p.division] + h + defensa[p.visitante])
            den[p.visitante] += w * math.exp(mu[p.division] + defensa[p.local])
        for e in equipos:
            nuevo = log_ratio(marcados[e], den[e])
            cambio = max(cambio, abs(nuevo - ataque[e]))
            ataque[e] = nuevo

        den = defaultdict(float)
        for w, p in zip(pesos, datos, strict=True):
            den[p.visitante] += w * math.exp(mu[p.division] + h + ataque[p.local])
            den[p.local] += w * math.exp(mu[p.division] + ataque[p.visitante])
        for e in equipos:
            nuevo = log_ratio(encajados[e], den[e])
            cambio = max(cambio, abs(nuevo - defensa[e]))
            defensa[e] = nuevo

        den_h = sum(
            w * math.exp(mu[p.division] + ataque[p.local] + defensa[p.visitante])
            for w, p in zip(pesos, datos, strict=True)
        )
        nuevo_h = log_ratio(goles_casa, den_h)
        cambio = max(cambio, abs(nuevo_h - h))
        h = nuevo_h

        den_div: dict[str, float] = defaultdict(float)
        for w, p in zip(pesos, datos, strict=True):
            den_div[p.division] += w * (
                math.exp(h + ataque[p.local] + defensa[p.visitante])
                + math.exp(ataque[p.visitante] + defensa[p.local])
            )
        for d in divisiones:
            nuevo = log_ratio(goles_div[d], den_div[d])
            cambio = max(cambio, abs(nuevo - mu[d]))
            mu[d] = nuevo

        # Identificabilidad: ataque y defensa centrados en 0; el desplazamiento pasa a μ.
        media_a = sum(ataque.values()) / len(equipos)
        media_d = sum(defensa.values()) / len(equipos)
        for e in equipos:
            ataque[e] -= media_a
            defensa[e] -= media_d
        for d in divisiones:
            mu[d] += media_a + media_d

        if cambio < tol:
            break

    conteo: dict[int, int] = defaultdict(int)
    ultima: dict[int, tuple[date, str]] = {}
    for p in datos:
        for e in (p.local, p.visitante):
            conteo[e] += 1
            if e not in ultima or p.fecha >= ultima[e][0]:
                ultima[e] = (p.fecha, p.division)

    return ModeloPoisson(
        ataque=ataque,
        defensa=defensa,
        mu=mu,
        h=h,
        partidos_por_equipo=dict(conteo),
        division_actual={e: d for e, (_, d) in ultima.items()},
        rho=rho,
        iteraciones=iteraciones,
    )
