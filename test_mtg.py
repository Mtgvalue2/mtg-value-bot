import sys
from backend.mtg_core import buscar_carta

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python test_mtg.py <nombre_carta> [edicion]")
        sys.exit(1)

    nombre = sys.argv[1]
    edicion = sys.argv[2] if len(sys.argv) > 2 else None

    resultado = buscar_carta(nombre, edicion)
    print("\n🔍 Resultado completo:", resultado)

    if "error" in resultado:
        print("\n❌ Error:", resultado["error"])
    else:
        print("\n✅ Carta encontrada:")
        print(f"Nombre: {resultado['nombre']}")
        print(f"Edición: {resultado['edicion']}")
        print(f"Precio: ${resultado['precio']:.2f} USD")
        print(f"RSI: {resultado['rsi']}")
        print(f"Predicciones futuras: {resultado['predicciones']}")
