import os
import ssl
import urllib.request
import flet as ft
import flet_charts as charts  

# Bypass de seguridad SSL
ssl._create_default_https_context = ssl._create_unverified_context

def main(page: ft.Page):
    page.title = "Prueba de Gráficos"
    
    # Usamos charts para el gráfico y ft.Colors con C MAYÚSCULA para el color
    page.add(
        charts.PieChart(
            sections=[
                charts.PieChartSection(
                    value=50, 
                    title='Test', 
                    color=ft.Colors.BLUE  # <-- ¡C mayúscula arreglada aquí!
                )
            ]
        )
    )

if __name__ == "__main__":
    ft.run(main)