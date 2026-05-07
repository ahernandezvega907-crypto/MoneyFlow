from PIL import Image
import os

# Ruta de tu icono actual (con el nombre que ya tienes)
ruta_original = "assets/moneyflow.ico"

# Verificar si el archivo existe
if not os.path.exists(ruta_original):
    print(f"❌ No se encontró el archivo: {ruta_original}")
    print("Verifica que el archivo esté en la carpeta assets/")
    exit(1)

# Abrir la imagen
img = Image.open(ruta_original)
print(f"✅ Tamaño original: {img.size}")

# Redimensionar a 512x512
img_redimensionada = img.resize((512, 512), Image.Resampling.LANCZOS)

# Guardar como PNG (mejor para Android)
img_redimensionada.save("assets/icon.png", "PNG")
print(f"✅ Icono redimensionado guardado en: assets/icon.png")
print(f"📐 Nuevo tamaño: 512x512 píxeles")