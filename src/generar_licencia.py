import hashlib
import uuid

def hash_code(code):
    return hashlib.sha256(code.encode()).hexdigest()

print("=== Generador de licencias MoneyFlow ===\n")
email = input("Email del comprador: ").strip().lower()

opcion = input("¿Generar código automático? (s/n): ").lower()
if opcion == 'n':
    codigo = input("Código personalizado (ej. REGALO-2026): ").strip().upper()
else:
    codigo = str(uuid.uuid4()).upper()

hash_val = hash_code(codigo)

print("\n--- Copia y ejecuta esto en el SQL Editor de Supabase ---")
print(f"INSERT INTO licencias (email, codigo_hash) VALUES ('{email}', '{hash_val}');")
print("\n--- Entrega este código al comprador ---")
print(f"Código de activación: {codigo}")