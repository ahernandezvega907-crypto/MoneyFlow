# debug_helper.py – El policía de errores (con soporte asíncrono)

import sys
import traceback
import logging
import os
import asyncio
from datetime import datetime
import flet as ft

# ---------- RUTA SEGURA PARA EL LOG ----------
def get_log_path():
    if getattr(sys, 'frozen', False):
        base_dir = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base_dir = os.path.dirname(__file__)
    app_dir = os.path.join(base_dir, "MoneyFlow")
    if not os.path.exists(app_dir):
        os.makedirs(app_dir)
    return os.path.join(app_dir, "flet_errors.log")

error_logger = logging.getLogger("flet_debugger")
error_logger.setLevel(logging.DEBUG)

fh = logging.FileHandler(get_log_path(), encoding="utf-8")
fh.setLevel(logging.ERROR)
formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
fh.setFormatter(formatter)
error_logger.addHandler(fh)

if not os.getenv("MONEYFLOW_PRODUCTION"):
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(formatter)
    error_logger.addHandler(ch)

_flet_page = None

def init_debugger(page: ft.Page):
    global _flet_page
    _flet_page = page

    def atrapar_error(exc_type, exc_value, exc_tb):
        if exc_type == KeyboardInterrupt:
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return

        tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
        tb_text = "".join(tb_lines)
        error_logger.error("Error no capturado:\n%s", tb_text)

        if _flet_page:
            mostrar_aviso(_flet_page, exc_type.__name__, str(exc_value), tb_text)

    sys.excepthook = atrapar_error

    if hasattr(page, "on_error"):
        page.on_error = lambda e: error_logger.error("Error en página Flet: %s", e.data)

def mostrar_aviso(page: ft.Page, tipo_error: str, mensaje: str, traza_completa: str = ""):
    mensaje_corto = mensaje[:200] + ("..." if len(mensaje) > 200 else "")

    dlg = ft.AlertDialog(
        title=ft.Text(f"🚨 Error: {tipo_error}", color=ft.Colors.RED),
        content=ft.Column(
            controls=[
                ft.Text(mensaje_corto, selectable=True),
                ft.Text("Revisa 'flet_errors.log' para más detalles.",
                        size=12, italic=True, color=ft.Colors.GREY),
            ],
            tight=True,
        ),
        actions=[ft.TextButton("Cerrar", on_click=lambda e: cerrar_dialogo(page, dlg))],
    )
    page.dialog = dlg
    dlg.open = True
    page.update()

    if not os.getenv("MONEYFLOW_PRODUCTION"):
        print("\n" + "="*60)
        print(f"❗ ERROR [{datetime.now().strftime('%H:%M:%S')}]: {tipo_error}")
        print("-"*60)
        print(traza_completa)
        print("="*60 + "\n")

def cerrar_dialogo(page, dlg):
    dlg.open = False
    page.update()

def safe_call(func, *args, **kwargs):
    """Envoltorio para funciones síncronas."""
    def wrapper(*inner_args, **inner_kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_logger.error("Excepción en safe_call:", exc_info=True)
            if _flet_page:
                mostrar_aviso(_flet_page, type(e).__name__, str(e),
                              traceback.format_exc())
    return wrapper

def safe_async(coro_func, *args, **kwargs):
    """Ejecuta una corrutina de forma segura y programa la tarea."""
    async def wrapper():
        try:
            await coro_func(*args, **kwargs)
        except Exception as e:
            error_logger.error("Excepción en safe_async:", exc_info=True)
            if _flet_page:
                mostrar_aviso(_flet_page, type(e).__name__, str(e),
                              traceback.format_exc())
    return asyncio.ensure_future(wrapper())