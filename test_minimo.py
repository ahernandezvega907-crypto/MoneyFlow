import flet as ft

def main(page: ft.Page):
    page.title = "Test MoneyFlow"
    page.add(ft.Text("Hola Mundo"))
    page.update()

ft.app(target=main)