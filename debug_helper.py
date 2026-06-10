# debug_helper.py – El policía de errores

import sys
import traceback
import logging
from datetime import datetime
import flet as ft

# Preparamos el diario donde se guardan los errores
error_logger = logging.getLogger("flet_debugger")
error_logger.setLevel(logging.DEBUG)

# Guardamos los errores en un archivo "flet_errors.log"
fh = logging.FileHandler("flet_errors.log", encoding="utf-8")
fh.setLevel(logging.ERROR)
formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
fh.setFormatter(formatter)
error_logger.addHandler(fh)

# También mostramos los errores en la consola (para que los veas mientras programas)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(formatter)
error_logger.addHandler(ch)

# Aquí guardaremos la ventana principal de tu app
_flet_page = None

def init_debugger(page: ft.Page):
    """
    ¡Activa el escudo protector! Llama a esto al principio de tu app.
    page = la página principal de Flet.
    """
    global _flet_page
    _flet_page = page

    # Esta función atrapa cualquier error que nadie haya visto
    def atrapar_error(exc_type, exc_value, exc_tb):
        # Si presionas Ctrl+C no lo atrapamos, dejamos que cierre
        if exc_type == KeyboardInterrupt:
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return

        # Construimos el mensaje detallado del error
        tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
        tb_text = "".join(tb_lines)

        # Lo escribimos en el diario
        error_logger.error("Error no capturado:\n%s", tb_text)

        # Si la app sigue abierta, mostramos una ventanita roja
        if _flet_page:
            mostrar_aviso(_flet_page, exc_type.__name__, str(exc_value), tb_text)

    # Le decimos a Python: "usa mi función para cualquier error"
    sys.excepthook = atrapar_error

    # También atrapamos errores que vengan de la propia Flet
    if hasattr(page, "on_error"):
        page.on_error = lambda e: error_logger.error("Error en página Flet: %s", e.data)

def mostrar_aviso(page: ft.Page, tipo_error: str, mensaje: str, traza_completa: str = ""):
    """
    Dibuja un diálogo rojo con el error.
    """
    # Cortamos el mensaje si es muy largo para que no ocupe toda la pantalla
    mensaje_corto = mensaje[:200] + ("..." if len(mensaje) > 200 else "")

    # Cuadro de diálogo
    dlg = ft.AlertDialog(
        title=ft.Text(f"🚨 Error: {tipo_error}", color=ft.colors.RED),
        content=ft.Column(
            controls=[
                ft.Text(mensaje_corto, selectable=True),
                ft.Text("Revisa 'flet_errors.log' para más detalles.",
                        size=12, italic=True, color=ft.colors.GREY),
            ],
            tight=True,
        ),
        actions=[
            ft.TextButton("Cerrar", on_click=lambda e: cerrar_dialogo(page, dlg)),
        ],
    )
    page.dialog = dlg
    dlg.open = True
    page.update()

    # También lo imprimimos en la consola con un cartel grande
    print("\n" + "="*60)
    print(f"❗ ERROR [{datetime.now().strftime('%H:%M:%S')}]: {tipo_error}")
    print("-"*60)
    print(traza_completa)
    print("="*60 + "\n")

def cerrar_dialogo(page, dlg):
    dlg.open = False
    page.update()

def safe_call(func, *args, **kwargs):
    """
    Envuelve un botón o acción peligrosa para que, si falla,
    no se rompa todo el castillo.
    Uso:
        btn.on_click = safe_call(mi_funcion, argumento1, argumento2)
    """
    def wrapper(*inner_args, **inner_kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_logger.error("Excepción en safe_call:", exc_info=True)
            if _flet_page:
                mostrar_aviso(_flet_page, type(e).__name__, str(e),
                              traceback.format_exc())
    return wrapper