"""Límite de uso diario por IP para controlar el gasto en la API de IA.

El contador vive en memoria: no se comparte entre réplicas y se reinicia al reiniciar el servidor.
Es suficiente para la versión 1 y es el punto de extensión para el futuro plan freemium.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from threading import Lock

from app import configuracion


class LimiteSuperado(Exception):
    pass


class LimitadorDiario:
    def __init__(self):
        self._conteo: dict[tuple[str, str, str], int] = defaultdict(int)
        self._candado = Lock()

    def _limite(self, tipo: str) -> int:
        return configuracion.limite_fotos_dia() if tipo == "fotos" else configuracion.limite_agente_dia()

    def registrar(self, ip: str, tipo: str) -> int:
        """Suma un uso. Lanza LimiteSuperado si se pasó del límite del día. Devuelve los usos restantes."""
        hoy = date.today().isoformat()
        with self._candado:
            # limpia días anteriores para no crecer sin fin
            for clave in [k for k in self._conteo if k[2] != hoy]:
                del self._conteo[clave]
            clave = (ip, tipo, hoy)
            if self._conteo[clave] >= self._limite(tipo):
                raise LimiteSuperado(tipo)
            self._conteo[clave] += 1
            return self._limite(tipo) - self._conteo[clave]

    def reiniciar(self):
        with self._candado:
            self._conteo.clear()


limitador = LimitadorDiario()
