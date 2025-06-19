import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from backend.mtg_core import buscar_carta, obtener_todas_ediciones
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import os
import requests
from io import BytesIO
from PIL import Image, ImageTk

class MTGValueGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("MTGValueBot - Consulta de Cartas")
        self.root.geometry("900x700")
        self.root.resizable(True, True)

        # Estilo oscuro moderno
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure("TButton", padding=6, relief="flat", background="#2962FF", foreground="white")
        self.style.configure("TEntry", padding=6)
        self.style.configure("TLabel", padding=6, font=("Segoe UI", 12))

        # Frame de entrada
        self.frame_busqueda = ttk.Frame(self.root)
        self.frame_busqueda.pack(pady=10, padx=10, fill=tk.X)

        self.label_nombre = ttk.Label(self.frame_busqueda, text="Nombre de la carta:")
        self.label_nombre.grid(row=0, column=0, sticky="w")

        self.entry_nombre = ttk.Entry(self.frame_busqueda, width=40)
        self.entry_nombre.grid(row=0, column=1, padx=5)

        self.label_edicion = ttk.Label(self.frame_busqueda, text="Edición (opcional):")
        self.label_edicion.grid(row=1, column=0, sticky="w")

        self.entry_edicion = ttk.Entry(self.frame_busqueda, width=40)
        self.entry_edicion.grid(row=1, column=1, padx=5)

        self.btn_buscar = ttk.Button(self.frame_busqueda, text="🔍 Buscar", command=self.realizar_busqueda)
        self.btn_buscar.grid(row=0, column=2, rowspan=2, padx=10)

        # Resultado texto
        self.frame_resultado = ttk.Frame(self.root)
        self.frame_resultado.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        self.resultado_text = tk.Text(self.frame_resultado, wrap=tk.WORD, height=15, width=80, bg="#1e1e1e", fg="white", font=("Arial", 12))
        self.resultado_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.scrollbar = ttk.Scrollbar(self.frame_resultado, orient="vertical", command=self.resultado_text.yview)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.resultado_text.config(yscrollcommand=self.scrollbar.set)

        # Frame de imagen
        self.frame_imagen = ttk.Frame(self.root)
        self.frame_imagen.pack(pady=10, padx=10)

        self.label_imagen = ttk.Label(self.frame_imagen, text="🖼️ Imagen de la carta aparecerá aquí", anchor="center")
        self.label_imagen.pack()

        # Frame del gráfico
        self.frame_grafico = ttk.Frame(self.root)
        self.frame_grafico.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        self.canvas_grafico = None

    def realizar_busqueda(self):
        """Manejar la búsqueda desde la GUI"""
        nombre = self.entry_nombre.get().strip()
        edicion = self.entry_edicion.get().strip() or None

        if not nombre:
            messagebox.showwarning("Campo vacío", "Por favor ingresa el nombre de una carta.")
            return

        resultado = buscar_carta(nombre, edicion)

        # Limpiar resultados anteriores
        self.resultado_text.delete(1.0, tk.END)

        if "error" in resultado or "nombre" not in resultado or resultado["precio"] <= 0.0:
            self.resultado_text.insert(tk.END, f"🚫 No se encontró '{nombre}'\n")
            if "error" in resultado:
                self.resultado_text.insert(tk.END, f"Detalle: {resultado['error']}\n\n")

            todas_ediciones = obtener_todas_ediciones(nombre)
            if todas_ediciones:
                self.resultado_text.insert(tk.END, "📚 Ediciones disponibles:\n")
                for idx, edic in enumerate(todas_ediciones[:15], 1):
                    try:
                        self.resultado_text.insert(tk.END, f"{idx}. {edic['edicion']} | ${float(edic['precio']):.2f}\n")
                    except:
                        continue
            else:
                self.resultado_text.insert(tk.END, "❌ No se encontraron ediciones.")
            return

        # Mostrar resultados en pantalla
        self.resultado_text.insert(tk.END, f"🎴 Nombre: {resultado['nombre']}\n")
        self.resultado_text.insert(tk.END, f"📦 Edición: {resultado['edicion']}\n")
        self.resultado_text.insert(tk.END, f"💰 Precio Actual: ${round(float(resultado['precio']), 2):.2f}\n")

        if "rsi" in resultado and resultado["rsi"] is not None:
            self.resultado_text.insert(tk.END, f"📊 RSI: {resultado['rsi']}\n")

        if "predicciones" in resultado and isinstance(resultado["predicciones"], list) and len(resultado["predicciones"]) >= 6:
            self.resultado_text.insert(tk.END, "\n🔮 Predicción de Precios Futuros (6 meses):\n")
            for i, p in enumerate(resultado["predicciones"][:6], 1):
                fecha_pred = datetime.now() + timedelta(days=i*30)
                try:
                    self.resultado_text.insert(tk.END, f"{fecha_pred.strftime('%Y-%m-%d')}: ${float(p):.2f}\n")
                except:
                    continue
        else:
            self.resultado_text.insert(tk.END, "\n📉 Datos insuficientes para predicción.")

        # Mostrar imagen si hay
        image_url = resultado.get("image_url")
        if image_url:
            try:
                response = requests.get(image_url)
                img_data = BytesIO(response.content)
                img_pil = Image.open(img_data).resize((200, 280), Image.LANCZOS)
                self.photo = ImageTk.PhotoImage(img_pil)
                self.label_imagen.config(image=self.photo, text="")
            except Exception as e:
                self.label_imagen.config(text=f"⚠️ No se pudo cargar la imagen:\n{str(e)}")
        else:
            self.label_imagen.config(text="🖼️ Sin imagen disponible")

        # Graficar evolución del precio
        if "fechas" in resultado and "precios" in resultado and len(resultado["precios"]) >= 2:
            if self.canvas_grafico:
                self.canvas_grafico.get_tk_widget().destroy()

            x = range(len(resultado["precios"]))
            y = [float(p) for p in resultado["precios"]]

            fig, ax = plt.subplots(figsize=(6, 3))
            ax.plot(x, y, label="Precio Real", marker='o', color="#00ffcc")
            ax.set_title(f"Evolución de Precios - {resultado['nombre']}", fontsize=12, color="white")
            ax.set_xlabel("Fecha", color="white")
            ax.set_ylabel("Precio USD", color="white")
            ax.tick_params(axis='x', colors="white")
            ax.tick_params(axis='y', colors="white")
            ax.legend(loc="upper left")
            ax.grid(True, linestyle="--", alpha=0.3)
            ax.set_facecolor("#1e1e1e")
            fig.patch.set_facecolor("#1e1e1e")

            self.canvas_grafico = FigureCanvasTkAgg(fig, master=self.frame_grafico)
            self.canvas_grafico.draw()
            self.canvas_grafico.get_tk_widget().pack()

        else:
            if self.canvas_grafico:
                self.canvas_grafico.get_tk_widget().destroy()
            ttk.Label(self.frame_grafico, text="📉 No hay suficiente historial para mostrar").pack()

# Iniciar aplicación
if __name__ == "__main__":
    from datetime import datetime
    import numpy as np
    from backend.mtg_core import buscar_carta, obtener_todas_ediciones
    import requests
    from io import BytesIO
    from PIL import Image, ImageTk

    root = tk.Tk()
    app = MTGValueGUI(root)
    root.mainloop()
