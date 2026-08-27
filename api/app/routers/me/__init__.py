"""Endpoints per a l'usuari autenticat (perfil propi + comandes).

Cada dominio vive en su propio módulo (uno por bloque de endpoints bajo el
mismo prefijo de URL); este paquete solo los agrega bajo un único `router`.
"""

from fastapi import APIRouter

from . import addresses, orders, peticiones, profile, subscripcio

router = APIRouter()
for _modulo in (profile, orders, addresses, peticiones, subscripcio):
    router.include_router(_modulo.router)
