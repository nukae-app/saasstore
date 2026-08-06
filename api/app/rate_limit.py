"""Limiter compartido (slowapi). Vive en su propio módulo para que los routers
puedan importarlo sin crear un import circular con main.py, que es quien lo
registra en la app."""

from slowapi import Limiter
from slowapi.util import get_remote_address

from .config import get_settings

limiter = Limiter(key_func=get_remote_address, enabled=get_settings().rate_limit_enabled)
