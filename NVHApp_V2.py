import sys
import os
import control as ctrl
import tkinter as tk
from tkinter import ttk, messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
from scipy import signal
from PIL import Image, ImageTk
import serial
import serial.tools.list_ports
import struct
import threading
from params_NVH import params_NVH


class NVHApp:
    def __init__(self, root):
        self.style = ttk.Style()
        self.root = root
        self.root.title("Controllo Posizione")
        self.root.geometry("1200x700")
        self.root.minsize(800, 500)

        self.screen_width = root.winfo_screenwidth()
        self.screen_height = root.winfo_screenheight()

        # Parametri NVH
        try:
            self.params = params_NVH()
        except Exception as e:
            print(f"Errore caricamento parametri NVH: {e}")
            self.params = {'Tserial': 0.001, 'numz': [0, 0, 0, 0, 0], 'denz': [0, 0, 0, 0, 0]}

        # Variabili per i controlli
        self.power_on = tk.BooleanVar()
        self.posizione_iniziale = tk.StringVar(value="0")
        self.wave_type = tk.StringVar(value="Sine")
        # sine variables
        self.sine_test_type = tk.StringVar(value="Frequenza e Ampiezza")
        self.frequenza = tk.StringVar(value="1")
        self.ampiezza = tk.StringVar(value="5")
        self.velocita = tk.StringVar(value="50")
        # triangular variables
        self.tr_test_type = tk.StringVar(value="Frequenza e Ampiezza")
        # sweep variables
        self.sweep_amplitude = tk.StringVar(value="5")
        self.sweep_init_freq = tk.StringVar(value="1")
        self.sweep_final_freq = tk.StringVar(value="10")
        # quarter cars variables
        self.QC_car_velocity = tk.StringVar(value="35")
        self.QC_wheel_stiff = tk.StringVar(value="200")
        self.QC_spring_stiff = tk.StringVar(value="20")
        self.QC_wheel_mass = tk.StringVar(value="30")
        self.QC_vehicle_mass = tk.StringVar(value="400")
        self.QC_damping = tk.StringVar(value="5000")
        self.Gr_selection = tk.StringVar(value="0")  # Select road profile (0 A; 1 B; 2 C, 3 D)
        self.numz = [-0.0227, 0, 0.0453, 0, -0.0227]
        self.denz = [1, -3.3967, 4.2994, -2.4028, 0.5002]
        # Renault test - just for displaying
        self.tint = self.params.get('tint', np.zeros(2000))
        self.qint = self.params.get('qint', np.zeros(2000))
        # print("Loaded tint and qint for Renault test.")
        # print(f"tint length: {len(self.tint)}, qint length: {len(self.qint)}")

        # Flag per evitare loop infiniti nei calcoli
        self._updating = False

        # Variabili seriali
        self.serial_port = None
        self.test_running = False
        self.readSerialOn = False
        self.read_thread = None

        # Buffer dati per plotting
        self.Tserial = self.params.get('Tserial', 0.001)
        self.Ntot = int(10 / self.Tserial)
        self.time_vect = np.arange(self.Ntot) * self.Tserial
        self.pos_ref = np.zeros(self.Ntot)
        self.pos_meas = np.zeros(self.Ntot)
        self.st = np.zeros(self.Ntot)

        # Stili personalizzati
        self.style.configure('headerFrame.TFrame', background='#ffe0b3')
        self.style.configure('headerLabel.TLabel', background='#ffe0b3', foreground='black')

        # Connessione seriale all'avvio
        self.setup_serial_connection()

        self.setup_ui()
        self.setup_plot()

        # Aggiungi trace alle variabili per aggiornamenti automatici
        self.frequenza.trace_add('write', lambda *args: self.on_param_change())
        self.ampiezza.trace_add('write', lambda *args: self.on_param_change())
        self.velocita.trace_add('write', lambda *args: self.on_param_change())

        # Avvia thread di lettura
        self.readSerialOn = True
    
        self.read_thread = threading.Thread(target=self.read_serial_data, daemon=True)
        self.read_thread.start()

        # Protocol per chiusura finestra
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    """Funzioni per setuppare l'interfaccia grafica"""

    def setup_serial_connection(self):
        """Mostra dialogo per selezione porta seriale"""
        ports = list(serial.tools.list_ports.comports())
        
        if not ports:
            messagebox.showwarning("Attenzione", "Nessuna porta seriale trovata!")
            return

        # Crea finestra di dialogo
        dialog = tk.Toplevel(self.root)
        dialog.title("Selezione Porta Seriale")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Seleziona la porta seriale:", font=("Inter", 12)).pack(pady=10)

        listbox = tk.Listbox(dialog, font=("Inter", 10))
        listbox.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        for port in ports:
            listbox.insert(tk.END, f"{port.device} - {port.description}")

        def on_select():
            selection = listbox.curselection()
            if selection:
                port_idx = selection[0]
                port_name = ports[port_idx].device
                try:
                    self.serial_port = serial.Serial(
                        port=port_name,
                        baudrate=12_000_000,
                        bytesize=serial.EIGHTBITS,
                        parity=serial.PARITY_NONE,
                        stopbits=serial.STOPBITS_ONE,
                        timeout=2
                    )
                    messagebox.showinfo("Successo", f"Connesso a {port_name}")
                    dialog.destroy()
                except Exception as e:
                    messagebox.showerror("Errore", f"Impossibile aprire la porta:\n{str(e)}")
            else:
                messagebox.showwarning("Attenzione", "Seleziona una porta!")

        def on_skip():
            dialog.destroy()

        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="Connetti", command=on_select).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Salta", command=on_skip).pack(side=tk.LEFT, padx=5)

        self.root.wait_window(dialog)

    def setup_ui(self):
        # Stili
        self.style.configure("Big.TLabelframe.Label", font=("Inter", 11)) 
        self.style.configure("bigTextButton.TButton", font=("Inter", 12))
        self.style.configure("bigText.TRadiobutton", font=("Inter", 11))


        # Configurazione grid principale
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=0, minsize=50)
        self.root.rowconfigure(1, weight=1)

        # Header
        self.headerFrame = ttk.Frame(self.root, padding=(10, 5), style='headerFrame.TFrame')
        self.headerFrame.grid(row=0, column=0, sticky="ew")

        self.headerFrame.grid_rowconfigure(0, weight=1)
        self.headerFrame.grid_columnconfigure(0, weight=0)
        self.headerFrame.grid_columnconfigure(1, weight=1)
        self.headerFrame.grid_columnconfigure(2, weight=0)

        self.setup_header()

        # PanedWindow principale
        self.main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.main_paned.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

        # Frame controlli (sinistra)
        self.controls_frame = ttk.Frame(self.main_paned)
        self.main_paned.add(self.controls_frame, weight=1)

        # Frame grafico (destra)
        self.plot_frame = ttk.Frame(self.main_paned)
        self.main_paned.add(self.plot_frame, weight=1)

        self.controls_frame.columnconfigure(0, weight=1)
        self.controls_frame.rowconfigure(1, weight=1)

        self.setup_controls()

    def setup_header(self):
        try:
            self.original_image = Image.open(self.resource_path("img/logo_waya-removebg.png"))
            original_width, original_height = self.original_image.size
            self.new_height = 30
            self.aspect_ratio = original_height / original_width
            self.new_width = int(self.new_height / self.aspect_ratio)
            image_resized = self.original_image.resize((self.new_width, self.new_height))
            self.logo = ImageTk.PhotoImage(image_resized)

            self.logo_label = ttk.Label(self.headerFrame, image=self.logo, style="headerLabel.TLabel")
            self.logo_label.grid(column=0, row=0, sticky="w", padx=(0, 15))

            title_label = ttk.Label(
                self.headerFrame,
                text="WayAssauto - Banco prova rumorosità",
                anchor="w",
                style="headerLabel.TLabel",
                font=("Arial", 14, "bold")
            )
            title_label.grid(column=1, row=0, sticky="w")

        except Exception as e:
            print(f"Errore nel caricamento del logo: {e}")
            ttk.Label(
                self.headerFrame,
                text="WayAssauto - Banco prova rumorosità",
                font=("Arial", 14, "bold"),
                style="headerLabel.TLabel"
            ).grid(column=1, row=0, sticky="w")

        self.create_header_border()

    def create_header_border(self):
        border_canvas = tk.Canvas(self.root, height=3, highlightthickness=0)
        border_canvas.grid(row=0, column=0, sticky="sew", pady=(0, 0))
        
        def draw_border(event=None):
            border_canvas.delete("all")
            width = border_canvas.winfo_width()
            border_canvas.create_rectangle(0, 0, width, 1, fill="#ff9900", outline="#ff9900")
        
        border_canvas.bind("<Configure>", draw_border)
        self.root.after(1, draw_border)

    def setup_controls(self):
        # Sezione Power e LED
        power_frame = ttk.LabelFrame(self.controls_frame, text="Controllo", style="Big.TLabelframe", padding="10")
        power_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N), padx=5, pady=(0, 5))
        power_frame.columnconfigure(1, weight=1)

        self.led_canvas = tk.Canvas(power_frame, width=60, height=60)
        self.led_canvas.grid(row=0, column=0, rowspan=3, padx=(0, 10), sticky=tk.N)
        self.update_led()

        power_container = ttk.Frame(power_frame)
        power_container.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2)
        power_container.columnconfigure(1, weight=1)

        ttk.Label(power_container, text="Power").grid(row=0, column=0, sticky=tk.W)
        power_switch = ttk.Checkbutton(power_container, variable=self.power_on, command=self.toggle_power)
        power_switch.grid(row=0, column=2, sticky=tk.E)

        pos_container = ttk.Frame(power_frame)
        pos_container.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=2)
        pos_container.columnconfigure(1, weight=1)

        ttk.Label(pos_container, text="Posizione Iniziale [mm]").grid(row=0, column=0, sticky=tk.W)
        pos_entry = ttk.Entry(pos_container, textvariable=self.posizione_iniziale, width=10)
        pos_entry.grid(row=0, column=2, sticky=tk.E)

        self.pos_button = ttk.Button(power_frame, text="Posizionamento", style="bigTextButton.TButton", command=self.posizionamento)
        self.pos_button.grid(row=2, column=1, pady=10, sticky=(tk.W, tk.E))

        # Test controls
        test_frame = ttk.LabelFrame(self.controls_frame, text="Controlli Test", style="Big.TLabelframe", padding="10")
        test_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        test_frame.columnconfigure(0, weight=1)
        test_frame.rowconfigure(0, weight=1)

        notebook_container = ttk.Frame(test_frame)
        notebook_container.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        notebook_container.columnconfigure(0, weight=1)
        notebook_container.rowconfigure(0, weight=1)

        self.notebook = ttk.Notebook(notebook_container)
        self.notebook.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Quando cambio tab lancio la funzione di aggiornamento
        self.notebook.bind('<<NotebookTabChanged>>', self.on_tab_change)

        self.tabs = {}
        
        # Setup Sine Tab
        self.setup_sine_tab()
        self.setup_triangular_tab()
        self.setup_sweep_tab()
        self.setup_ISO_road_tab()
        self.setup_timeHistory_tab()

        # Bottoni Start/Stop
        button_frame = ttk.Frame(test_frame)
        button_frame.grid(row=1, column=0, pady=(10, 0))

        self.start_button = ttk.Button(button_frame, text="Test Start", style="bigTextButton.TButton", command=self.start_test)
        self.start_button.grid(row=0, column=0, padx=(0, 10))
        
        self.stop_button = ttk.Button(button_frame, text="Test Stop", style="bigTextButton.TButton", command=self.stop_test, state='disabled')
        self.stop_button.grid(row=0, column=1)

        self.start_button.config(state='disabled')
        self.stop_button.config(state='disabled')
        self.pos_button.config(state='disabled')

    def setup_sine_tab(self):
        sine_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(sine_frame, text="Sinusoide")
        self.tabs["Sine"] = sine_frame
        
        sine_frame.columnconfigure(0, weight=1)
        sine_frame.columnconfigure(1, weight=1)
        
        # Frame sinistra - Selezione tipo di prova
        prova_frame = ttk.LabelFrame(sine_frame, text="Selezione tipo di prova", style="Big.TLabelframe", padding="10")
        prova_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N), padx=(0, 5), pady=(0, 5))
        
        ttk.Radiobutton(prova_frame, text="Frequenza e Ampiezza", style="bigText.TRadiobutton",
                        variable=self.sine_test_type, value="Frequenza e Ampiezza",
                        command=self.update_sine_labels).grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Radiobutton(prova_frame, text="Velocità e Ampiezza", style="bigText.TRadiobutton",
                        variable=self.sine_test_type, value="Velocità e Ampiezza",
                        command=self.update_sine_labels).grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Radiobutton(prova_frame, text="Frequenza e Velocità", style="bigText.TRadiobutton",
                        variable=self.sine_test_type, value="Frequenza e Velocità",
                        command=self.update_sine_labels).grid(row=2, column=0, sticky=tk.W, pady=2)
        
        # Frame destra - Parametri
        params_frame = ttk.LabelFrame(sine_frame, text="Parametri - Sinusoide", style="Big.TLabelframe", padding="10")
        params_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N), padx=(5, 0), pady=(0, 5))
        params_frame.columnconfigure(1, weight=1)
        
        self.param1_label = ttk.Label(params_frame, text="Frequenza [Hz]:")
        self.param1_label.grid(row=0, column=0, sticky=tk.W, pady=5)
        self.param1_entry = ttk.Entry(params_frame, textvariable=self.frequenza, width=15)
        self.param1_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)
        
        self.param2_label = ttk.Label(params_frame, text="Ampiezza [mm]:")
        self.param2_label.grid(row=1, column=0, sticky=tk.W, pady=5)
        self.param2_entry = ttk.Entry(params_frame, textvariable=self.ampiezza, width=15)
        self.param2_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)
        
        # Campo velocità (usato solo per "Velocità e Ampiezza")
        self.param3_label = ttk.Label(params_frame, text="Velocità [mm/s]:")
        self.param3_entry = ttk.Entry(params_frame, textvariable=self.velocita, width=15)

    def update_sine_labels(self):
        test_type = self.sine_test_type.get()
        print(f"Updating sine labels for test type: {test_type}")
        
        # Nascondi tutti i campi extra
        self.param3_label.grid_remove()
        self.param3_entry.grid_remove()
        
        if test_type == "Frequenza e Ampiezza":
            print(f"Caso 1: Frequenza e Ampiezza")
            self.param1_label.config(text="Frequenza [Hz]:")
            self.param2_label.config(text="Ampiezza [mm]:")
            self.param1_entry.config(textvariable=self.frequenza)
            self.param2_entry.config(textvariable=self.ampiezza)
            
        elif test_type == "Velocità e Ampiezza":
            print(f"Caso 2: Velocità e Ampiezza")
            self.param1_label.config(text="Velocità [mm/s]:")
            self.param2_label.config(text="Ampiezza [mm]:")
            self.param1_entry.config(textvariable=self.velocita)
            self.param2_entry.config(textvariable=self.ampiezza)
            
        elif test_type == "Frequenza e Velocità":
            print(f"Caso 3: Frequenza e Velocità")
            self.param1_label.config(text="Frequenza [Hz]:")
            self.param2_label.config(text="Velocità [mm/s]:")
            self.param1_entry.config(textvariable=self.frequenza)
            self.param2_entry.config(textvariable=self.velocita)

    def on_param_change(self):
        """Chiamato automaticamente quando cambiano i parametri"""
        if self._updating:
            return
        
        self._updating = True
        prova = self.wave_type.get()

        if prova == "Sinusoide":
            test_type = self.sine_test_type.get()
        elif prova == "Triangolare":
            test_type = self.tr_test_type.get()
        
        try:
            if test_type == "Velocità e Ampiezza":
                self.calculate_frequency()
            elif test_type == "Frequenza e Velocità":
                self.calculate_amplitude()
            elif test_type == "Frequenza e Ampiezza":
                self.calculate_velocity()
        finally:
            self._updating = False

    def calculate_frequency(self):
        """Calcola frequenza da velocità e ampiezza
        Formula: f = v / (2π * A)
        dove v è la velocità [mm/s] e A è l'ampiezza [mm]
        """
        try:
            vel = float(self.velocita.get())
            amp = float(self.ampiezza.get())
            if amp > 0:
                freq = vel / (2 * np.pi * amp)
                self.frequenza.set(f"{freq:.2f}")
                # print(f"[FREQ] Calcolato: freq={freq}, salvato={self.frequenza.get()}")
        except (ValueError, ZeroDivisionError):
            pass

    def calculate_amplitude(self):
        """Calcola ampiezza da frequenza e velocità
        Formula: A = v / (2π * f)
        dove v è la velocità [mm/s] e f è la frequenza [Hz]
        """
        try:
            vel = float(self.velocita.get())
            freq = float(self.frequenza.get())
            if freq > 0:
                amp = vel / (2 * np.pi * freq)
                self.ampiezza.set(f"{amp:.2f}")
        except (ValueError, ZeroDivisionError):
            pass

    def calculate_velocity(self):
            """Calcola velocità da frequenza e ampiezza
            Formula: v = f * (2π * A)
            dove v è la velocità [mm/s] e A è l'ampiezza [mm] e f è la frequenza [Hz]
            """
            try:
                freq = float(self.frequenza.get())
                amp = float(self.ampiezza.get())
                if amp > 0:
                    vel = freq * (2 * np.pi * amp)
                    self.velocita.set(f"{vel:.2f}")
            except (ValueError, ZeroDivisionError):
                pass

    def setup_triangular_tab(self):
            trian_frame = ttk.Frame(self.notebook, padding="10")
            self.notebook.add(trian_frame, text="Triangolare")
            self.tabs["Triangular"] = trian_frame
            
            trian_frame.columnconfigure(0, weight=1)
            trian_frame.columnconfigure(1, weight=1)
            
            # Frame sinistra - Selezione tipo di prova
            prova_frame = ttk.LabelFrame(trian_frame, text="Selezione tipo di prova", style="Big.TLabelframe", padding="10")
            prova_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N), padx=(0, 5), pady=(0, 5))
            
            ttk.Radiobutton(prova_frame, text="Frequenza e Ampiezza", style="bigText.TRadiobutton",
                            variable=self.tr_test_type, value="Frequenza e Ampiezza",
                            command=self.update_tr_labels).grid(row=0, column=0, sticky=tk.W, pady=2)
            ttk.Radiobutton(prova_frame, text="Velocità e Ampiezza", style="bigText.TRadiobutton",
                            variable=self.tr_test_type, value="Velocità e Ampiezza",
                            command=self.update_tr_labels).grid(row=1, column=0, sticky=tk.W, pady=2)
            ttk.Radiobutton(prova_frame, text="Frequenza e Velocità", style="bigText.TRadiobutton",
                            variable=self.tr_test_type, value="Frequenza e Velocità",
                            command=self.update_tr_labels).grid(row=2, column=0, sticky=tk.W, pady=2)
            
            # Frame destra - Parametri
            params_frame = ttk.LabelFrame(trian_frame, text="Parametri - Triangolare", style="Big.TLabelframe", padding="10")
            params_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N), padx=(5, 0), pady=(0, 5))
            params_frame.columnconfigure(1, weight=1)
            
            self.tr_param1_label = ttk.Label(params_frame, text="Frequenza [Hz]:")
            self.tr_param1_label.grid(row=0, column=0, sticky=tk.W, pady=5)
            self.tr_param1_entry = ttk.Entry(params_frame, textvariable=self.frequenza, width=15)
            self.tr_param1_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)
            
            self.tr_param2_label = ttk.Label(params_frame, text="Ampiezza [mm]:")
            self.tr_param2_label.grid(row=1, column=0, sticky=tk.W, pady=5)
            self.tr_param2_entry = ttk.Entry(params_frame, textvariable=self.ampiezza, width=15)
            self.tr_param2_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)
            
            # Campo velocità (usato solo per "Velocità e Ampiezza")
            self.tr_param3_label = ttk.Label(params_frame, text="Velocità [mm/s]:")
            self.tr_param3_entry = ttk.Entry(params_frame, textvariable=self.velocita, width=15)

    def update_tr_labels(self):
        test_type = self.tr_test_type.get()
        print(f"Updating triangular labels for test type: {test_type}")
        
        # Nascondi tutti i campi extra
        self.tr_param3_label.grid_remove()
        self.tr_param3_entry.grid_remove()
        
        if test_type == "Frequenza e Ampiezza":
            self.tr_param1_label.config(text="Frequenza [Hz]:")
            self.tr_param2_label.config(text="Ampiezza [mm]:")
            self.tr_param1_entry.config(textvariable=self.frequenza)
            self.tr_param2_entry.config(textvariable=self.ampiezza)
            
        elif test_type == "Velocità e Ampiezza":
            self.tr_param1_label.config(text="Velocità [mm/s]:")
            self.tr_param2_label.config(text="Ampiezza [mm]:")
            self.tr_param1_entry.config(textvariable=self.velocita)
            self.tr_param2_entry.config(textvariable=self.ampiezza)
            
        elif test_type == "Frequenza e Velocità":
            self.tr_param1_label.config(text="Frequenza [Hz]:")
            self.tr_param2_label.config(text="Velocità [mm/s]:")
            self.tr_param1_entry.config(textvariable=self.frequenza)
            self.tr_param2_entry.config(textvariable=self.velocita)

    def setup_sweep_tab(self):
        sweep_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(sweep_frame, text="Sweep")
        self.tabs["Sweep"] = sweep_frame
        
        sweep_frame.columnconfigure(0, weight=1)
        
        # Frame sinistra - Parametri
        params_frame = ttk.LabelFrame(sweep_frame, text="Parametri - Sweep", style="Big.TLabelframe", padding="10")
        params_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N), padx=(5, 0), pady=(0, 5))
        params_frame.columnconfigure(1, weight=1)
        
        param1_label = ttk.Label(params_frame, text="Frequenza Iniziale [Hz]:")
        param1_label.grid(row=1, column=0, sticky=tk.W, pady=5)
        param1_entry = ttk.Entry(params_frame, textvariable=self.sweep_init_freq, width=15)
        param1_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)

        param1_label = ttk.Label(params_frame, text="Frequenza Finale [Hz]:")
        param1_label.grid(row=2, column=0, sticky=tk.W, pady=5)
        param1_entry = ttk.Entry(params_frame, textvariable=self.sweep_final_freq, width=15)
        param1_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)
        
        param2_label = ttk.Label(params_frame, text="Ampiezza [mm]:")
        param2_label.grid(row=0, column=0, sticky=tk.W, pady=5)
        param2_entry = ttk.Entry(params_frame, textvariable=self.sweep_amplitude, width=15)
        param2_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)

    def setup_ISO_road_tab(self):
        ISO_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(ISO_frame, text="Profili ISO")
        self.tabs["ISO"] = ISO_frame
        
        ISO_frame.columnconfigure(0, weight=1)
        ISO_frame.columnconfigure(1, weight=1)
        
        # Frame sinistra - Selezione tipo profilo ISO
        prova_frame = ttk.LabelFrame(ISO_frame, text="Seleziona profilo ISO", style="Big.TLabelframe", padding="10")
        prova_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N), padx=(0, 5), pady=(0, 5))

        isoPrint = lambda: print(f'Actual selection: {self.Gr_selection.get()}')
        
        ttk.Radiobutton(prova_frame, text="ISO A - Asfalto liscio", style="bigText.TRadiobutton",
                        variable=self.Gr_selection, value="0").grid(row=0, column=0, sticky=tk.W, pady=2)
        
        ttk.Radiobutton(prova_frame, text="ISO B - Asfalto buono", style="bigText.TRadiobutton",
                        variable=self.Gr_selection, value="1").grid(row=1, column=0, sticky=tk.W, pady=2)
        
        ttk.Radiobutton(prova_frame, text="ISO C - Asfalto medio", style="bigText.TRadiobutton",
                        variable=self.Gr_selection, value="2").grid(row=2, column=0, sticky=tk.W, pady=2)
        
        ttk.Radiobutton(prova_frame, text="ISO D - Asfalto rovinato", style="bigText.TRadiobutton",
                        variable=self.Gr_selection, value="3").grid(row=3, column=0, sticky=tk.W, pady=2)
        
        # Frame destra - Parametri
        ISO_params_frame = ttk.LabelFrame(ISO_frame, text="Parametri - Quarter Car", style="Big.TLabelframe", padding="10")
        ISO_params_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N), padx=(5, 0), pady=(0, 5))
        ISO_params_frame.columnconfigure(1, weight=1)

        ISO_param0_label = ttk.Label(ISO_params_frame, text="Velocità veicolo [km/h]:")
        ISO_param0_label.grid(row=0, column=0, sticky=tk.W, pady=5)
        ISO_param0_entry = ttk.Entry(ISO_params_frame, textvariable=self.QC_car_velocity, width=15)
        ISO_param0_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)
        
        ISO_param1_label = ttk.Label(ISO_params_frame, text="Rigidezza ruota [N/mm]:")
        ISO_param1_label.grid(row=1, column=0, sticky=tk.W, pady=5)
        ISO_param1_entry = ttk.Entry(ISO_params_frame, textvariable=self.QC_wheel_stiff, width=15)
        ISO_param1_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)
        
        ISO_param2_label = ttk.Label(ISO_params_frame, text="Rigidezza sospensione [N/mm]:")
        ISO_param2_label.grid(row=2, column=0, sticky=tk.W, pady=5)
        ISO_param2_entry = ttk.Entry(ISO_params_frame, textvariable=self.QC_spring_stiff, width=15)
        ISO_param2_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)

        ISO_param3_label = ttk.Label(ISO_params_frame, text="Massa pneumatico [kg]:")
        ISO_param3_label.grid(row=3, column=0, sticky=tk.W, pady=5)
        ISO_param3_entry = ttk.Entry(ISO_params_frame, textvariable=self.QC_wheel_mass, width=15)
        ISO_param3_entry.grid(row=3, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)

        ISO_param4_label = ttk.Label(ISO_params_frame, text="Massa 'quarter car' [kg]:")
        ISO_param4_label.grid(row=4, column=0, sticky=tk.W, pady=5)
        ISO_param4_entry = ttk.Entry(ISO_params_frame, textvariable=self.QC_vehicle_mass, width=15)
        ISO_param4_entry.grid(row=4, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)

        ISO_param5_label = ttk.Label(ISO_params_frame, text="Smorzamento [Ns/m]:")
        ISO_param5_label.grid(row=5, column=0, sticky=tk.W, pady=5)
        ISO_param5_entry = ttk.Entry(ISO_params_frame, textvariable=self.QC_damping, width=15)
        ISO_param5_entry.grid(row=5, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)

    def setup_timeHistory_tab(self):
        time_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(time_frame, text="Time History")
        self.tabs["timeHistory"] = time_frame
        
        time_frame.columnconfigure(0, weight=1)
        time_frame.rowconfigure(0, weight=1)
        
        # Frame for parameters
        params_frame = ttk.LabelFrame(time_frame, text="Renault Test", style="Big.TLabelframe", padding="10")
        params_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0), pady=(0, 5))
        params_frame.columnconfigure(0, weight=1)
        params_frame.rowconfigure(0, weight=1)

        # Plot frame
        plot_frame = ttk.Frame(params_frame)
        plot_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        plot_frame.columnconfigure(0, weight=1)
        plot_frame.rowconfigure(0, weight=1)

        # Create figure with 1 subplot
        fig, ax = plt.subplots(1, 1, figsize=(8, 6))
        fig.tight_layout(pad=3.0)

        # Configure plot
        ax.set_xlim(0, 61)
        ax.set_ylim(-25, 25)
        ax.set_xlabel('Tempo [s]')
        ax.set_ylabel('Posizione [mm]')
        ax.set_title('Renault Test')
        ax.grid(True, alpha=0.3)
        
        # Create lines for qint and tint
        line_qint, = ax.plot(self.tint, self.qint, 'b-', label='qint (Target)', linewidth=1.5)
        ax.legend(loc='upper right')

        # Canvas
        canvas = FigureCanvasTkAgg(fig, plot_frame)
        canvas.draw()
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

        # Toolbar
        toolbar_frame = ttk.Frame(plot_frame)
        toolbar_frame.grid(row=1, column=0, sticky=(tk.W, tk.E))

        from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk
        toolbar = NavigationToolbar2Tk(canvas, toolbar_frame)
        toolbar.update()

    def on_tab_change(self, event):
        """Gestisce il cambio di tab"""
        current_tab = self.notebook.select()  # Get the widget name of current tab
        tab_text = self.notebook.tab(current_tab, "text")  # Get the tab text
        # print(f"Prev text: {self.wave_type.get()}")
        self.wave_type.set(tab_text)
        # print(f"Updated to: {self.wave_type.get()}")
        
    def update_led(self):
        self.led_canvas.delete("all")
        color = "green" if self.power_on.get() else "gray"
        self.led_canvas.create_oval(5, 5, 55, 55, fill=color, outline="black", width=2)

    def newThread(self):
        # Avvia thread di lettura
        if not self.readSerialOn:
            self.readSerialOn = True
            self.read_thread = threading.Thread(target=self.read_serial_data, daemon=True)
            self.read_thread.start()
    
    def toggle_power(self):
        self.update_led()
        if self.power_on.get():
            print("Sistema acceso")
            self.send_power_command(1)

            # Avvia thread di lettura
            if not self.readSerialOn:
                self.readSerialOn = True
                self.read_thread = threading.Thread(target=self.read_serial_data, daemon=True)
                self.read_thread.start()

            self.start_button.config(state='normal')
            self.pos_button.config(state='normal')
            self.stop_button.config(state='disabled')

        else:
            print("Sistema spento")
            self.send_power_command(0)
            # Ferma thread
            self.readSerialOn = False
            if self.read_thread:
                self.read_thread.join(timeout=2)

            self.start_button.config(state='disabled')
            self.stop_button.config(state='disabled')
            self.pos_button.config(state='disabled')

    def setup_plot(self):
        self.plot_frame.columnconfigure(0, weight=1)
        self.plot_frame.rowconfigure(0, weight=1)

        self.fig, (self.ax1, self.ax2) = plt.subplots(2, 1, figsize=(8, 6))
        self.fig.tight_layout(pad=3.0)

        # Subplot 1: Posizioni
        self.ax1.set_xlim(0, 10)
        self.ax1.set_ylim(-25, 25)
        self.ax1.set_ylabel('Posizione [mm]')
        self.ax1.set_title('Posizione Target vs Rilevata')
        self.ax1.grid(True, alpha=0.3)
        self.line_ref, = self.ax1.plot([], [], 'b-', label='Target', linewidth=1.5)
        self.line_meas, = self.ax1.plot([], [], 'r-', label='Rilevata', linewidth=1.5)
        self.ax1.legend(loc='upper right')

        # Subplot 2: Stato
        self.ax2.set_xlim(0, 10)
        self.ax2.set_ylim(-1, 10)
        self.ax2.set_xlabel('Tempo [s]')
        self.ax2.set_ylabel('Stato')
        self.ax2.set_title('Stato Sistema')
        self.ax2.grid(True, alpha=0.3)
        self.line_state, = self.ax2.plot([], [], 'g-', linewidth=1.5)

        self.canvas = FigureCanvasTkAgg(self.fig, self.plot_frame)
        self.canvas.draw()
        canvas_widget = self.canvas.get_tk_widget()
        canvas_widget.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

        toolbar_frame = ttk.Frame(self.plot_frame)
        toolbar_frame.grid(row=1, column=0, sticky=(tk.W, tk.E))

        from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk
        self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
        self.toolbar.update()

    def update_plot(self):
        """Aggiorna il grafico con i dati correnti"""
        try:
            self.line_ref.set_data(self.time_vect, self.pos_ref)
            self.line_meas.set_data(self.time_vect, self.pos_meas)
            self.line_state.set_data(self.time_vect, self.st)
            
            # Auto-scale y-axis per le posizioni
            if np.any(self.pos_ref != 0) or np.any(self.pos_meas != 0):
                y_min = min(np.min(self.pos_ref), np.min(self.pos_meas)) - 2
                y_max = max(np.max(self.pos_ref), np.max(self.pos_meas)) + 2
                self.ax1.set_ylim(y_min, y_max)
            
            self.canvas.draw_idle()
        except Exception as e:
            print(f"Errore aggiornamento grafico: {e}")

    def QC_transf_func(self):

        # Target parameters
        fpwm = 20e3
        Tpwm = 1 / fpwm
        Ts = Tpwm
        Tref = 100 * Ts
        
        # Quando servono i numeri:
        try:
            ms = float(self.QC_vehicle_mass.get())
            mu = float(self.QC_wheel_mass.get())
            ks = float(self.QC_spring_stiff.get()) * 1000.0
            ku = float(self.QC_wheel_stiff.get()) * 1000.0
            cs = float(self.QC_damping.get())
        except ValueError:
            messagebox.showerror("Errore", "Inserire valori numerici validi per i parametri QC")
            return

        # Variabile s
        s = ctrl.TransferFunction.s

        # Funzione di trasferimento continua
        Gs = -s**2*(ku*ms) / ( s**4*ms*mu
                            + s**3*cs*(ms+mu)
                            + s**2*(ku*ms + ks*(ms+mu))
                            + s*ku*cs
                            + ks*ku )

        # Discretizzazione con Tustin
        Gz = ctrl.sample_system(Gs, Tref, method='tustin')

        # Estrazione numerator & denominator
        numz = np.squeeze(Gz.num[0][0])
        denz = np.squeeze(Gz.den[0][0])

        self.numz = numz
        self.denz = denz
        # print(f"updated transfer function\n numz: {self.numz}\n, denz: {self.denz}")

    """Logiche di gestione test e seriale"""

    def read_serial_data(self):
        """Thread per lettura continua dati seriali"""
        Nd = int(1 * 6 * 1001)
        
        while self.readSerialOn and self.serial_port and self.serial_port.is_open:
        # while self.serial_port and self.serial_port.is_open:
            # print("Provo a leggere da seriale...")
            try:
                rawdata = self.serial_port.read(Nd * 2)
                # print(f"Bytes letti: {len(rawdata)}")
                if len(rawdata) < 4:
                    print("Dati insufficienti ricevuti, rawdata.length < 4")
                    continue

                rawdata_uint16 = list(struct.unpack('<' + 'H' * (len(rawdata) // 2), rawdata))

                # Trova header
                header = [17733, 21331]
                self.headPos = [i for i in range(len(rawdata_uint16) - 1) if rawdata_uint16[i:i + 2] == header]

                # print(f"pos number: {len(self.headPos)}")
                # print(f"Rawdata: {rawdata_uint16[:20]}")
                
                for idx in reversed(self.headPos):
                    del rawdata_uint16[idx:idx + 2]

                if not self.headPos:
                    # Avvia thread di lettura
                    print(f"No pos found")
                    # Ferma thread
                    self.readSerialOn = False
                    print(f"Stopping read thread")
                    # if self.read_thread:
                    #     self.read_thread.join(timeout=2)
                    #     print(f"Thread joined and closed")

                    self.root.after(1000, self.newThread)
                    print(f"Scheduled thread restarting after 1000ms")
                    
                    

                # Riallinea i dati a multipli di 3
                istart = (self.headPos[0] % 3)
                rawdata_aligned = rawdata_uint16[istart:]
                iend = (len(rawdata_aligned) // 3) * 3
                rawdata_aligned = rawdata_aligned[:iend]

                # print(f"Rawdata aligned: {rawdata_aligned[:20]}")

                if len(rawdata_aligned) < 3:
                    print(f"Rawdata aligned too short, rawdata_aligned.length < 3")
                    continue

                # Converti fixed-point signed (1,16,9)
                data = np.array(rawdata_aligned, dtype=np.uint16).reshape(-1, 3)
                data_int16 = data.view(dtype=np.int16)
                scale = 2 ** 9
                data_float = data_int16.astype(np.float32) / scale
                # print(f"Data: {data[:5, :]}")
                # print(f"Data float: {data_float[:5, :]}")

                # Aggiorna buffer circolari
                L = len(data_float)
                self.pos_ref = np.roll(self.pos_ref, -L)
                self.pos_meas = np.roll(self.pos_meas, -L)
                self.st = np.roll(self.st, -L)
                self.pos_ref[-L:] = data_float[:, 0]
                self.pos_meas[-L:] = data_float[:, 1]
                self.st[-L:] = data_float[:, 2]

                # # Aggiorna scale
                # if L > 0:
                #     current_pos = data_float[-1, 1]
                #     self.root.after(0, lambda p=current_pos: self.scale_attuale.set(p))

                # print(f"Lettura seriale: {L} campioni ricevuti")

                # Aggiorna grafico
                if self.headPos:
                    self.root.after(0, self.update_plot)

            except Exception as e:
                print(f"Errore lettura seriale: {e}")
                continue

    def send_power_command(self, power_state):
        """Invia comando di accensione/spegnimento"""
        if not self.serial_port or not self.serial_port.is_open:
            messagebox.showwarning("Attenzione", "Porta seriale non connessa!")
            return

        try:
            pos_init = float(self.posizione_iniziale.get())
        except ValueError:
            pos_init = 0

        # Costruisci messaggio
        header_bits = f"{0:01b}{power_state:01b}{1:01b}{0:01b}{0:01b}{0:02b}{2:02b}"
        msghead = int(header_bits, 2)

        msg = [
            np.float32(msghead),
            np.float32(pos_init),
            np.float32(0), np.float32(0), np.float32(0), np.float32(0),
            np.float32(self.params.get('numz', [0, 0, 0])[0] * 1000),
            np.float32(self.params.get('numz', [0, 0, 0])[2] * 1000),
            np.float32(self.params.get('denz', [0, 0, 0, 0, 0])[1]),
            np.float32(self.params.get('denz', [0, 0, 0, 0, 0])[2]),
            np.float32(self.params.get('denz', [0, 0, 0, 0, 0])[3]),
            np.float32(self.params.get('denz', [0, 0, 0, 0, 0])[4]),
            np.float32(0), np.float32(0), np.float32(0)
        ]

        tx_bytes = b''.join(struct.pack('<f', val) for val in msg)
        self.serial_port.write(tx_bytes)
        print(f"Comando power {'ON' if power_state else 'OFF'} inviato")

    def posizionamento(self):
        if not self.serial_port or not self.serial_port.is_open:
            messagebox.showwarning("Attenzione", "Porta seriale non connessa!")
            return

        try:
            pos = float(self.posizione_iniziale.get())
            if pos < -20 or pos > 20:
                messagebox.showwarning("Attenzione", "Posizione deve essere tra -20 e 20 mm")
                return

            # Invia comando di posizionamento
            header_bits = f"{0:01b}{1:01b}{1:01b}{0:01b}{0:01b}{0:02b}{2:02b}"
            msghead = int(header_bits, 2)

            msg = [
                np.float32(msghead),
                np.float32(pos),
                np.float32(0), np.float32(0), np.float32(0), np.float32(0),
                np.float32(self.params.get('numz', [0, 0, 0])[0] * 1000),
                np.float32(self.params.get('numz', [0, 0, 0])[2] * 1000),
                np.float32(self.params.get('denz', [0, 0, 0, 0, 0])[1]),
                np.float32(self.params.get('denz', [0, 0, 0, 0, 0])[2]),
                np.float32(self.params.get('denz', [0, 0, 0, 0, 0])[3]),
                np.float32(self.params.get('denz', [0, 0, 0, 0, 0])[4]),
                np.float32(0), np.float32(0), np.float32(0)
            ]

            tx_bytes = b''.join(struct.pack('<f', val) for val in msg)
            self.serial_port.write(tx_bytes)
            
            # self.scale_target.set(pos)
            print(f"Posizionamento a: {pos} mm")

        except ValueError:
            messagebox.showerror("Errore", "Inserire un valore numerico valido")

    def start_test(self):
        if not self.serial_port or not self.serial_port.is_open:
            messagebox.showwarning("Attenzione", "Porta seriale non connessa!")
            return

        if not self.power_on.get():
            messagebox.showwarning("Attenzione", "Accendere prima il sistema!")
            return

        try:
            pos_init = float(self.posizione_iniziale.get())
            amplitude = float(self.ampiezza.get())
            freq = float(self.frequenza.get())
            vcar = float(self.QC_car_velocity.get())

            # Validazione
            if pos_init < -20 or pos_init > 20:
                raise ValueError("Posizione iniziale fuori range (-20/20 mm)")
            if amplitude < 0 or amplitude > 20:
                raise ValueError("Ampiezza fuori range (0/20 mm)")
            if freq < 0.1 or freq > 100:
                raise ValueError("Frequenza fuori range (0.1/100 Hz)")

        except ValueError as e:
            messagebox.showerror("Errore", str(e))
            return
        
        numz = self.numz
        denz = self.denz

        if  self.wave_type.get() == "Sinusoide":
            # Costruisci messaggio per test Sine
            test_sel = 0  # Sine
            wv_type = 0  # 0 Sine, 1 triangular
            header_bits = f"{wv_type:01b}{1:01b}{1:01b}{1:01b}{0:01b}{test_sel:02b}{0:02b}"
            msghead = int(header_bits, 2)
            msg = [
                np.float32(msghead),
                np.float32(pos_init),
                np.float32(amplitude),
                np.float32(vcar),
                np.float32(freq),
                np.float32(1),   # rate_Hz_s (non usato per sine)
                np.float32(numz[0] * 1000),
                np.float32(numz[2] * 1000),
                np.float32(denz[1]),
                np.float32(denz[2]),
                np.float32(denz[3]),
                np.float32(denz[4]),
                np.float32(10),  # fend_Hz
                np.float32(amplitude),  # aend_mm
                np.float32(0)
            ]
            tx_bytes = b''.join(struct.pack('<f', val) for val in msg)
            self.serial_port.write(tx_bytes)
            print(f"Test Sine avviato: freq={freq} Hz, amp={amplitude} mm")
        
        elif  self.wave_type.get() == "Triangolare":
            # Costruisci messaggio per test Triangolare
            test_sel = 0  # Sine
            wv_type = 1   # 0 Sine, 1 Triangular
            header_bits = f"{wv_type:01b}{1:01b}{1:01b}{1:01b}{0:01b}{test_sel:02b}{0:02b}"
            msghead = int(header_bits, 2)
            msg = [
                np.float32(msghead),
                np.float32(pos_init),
                np.float32(amplitude),
                np.float32(vcar),
                np.float32(freq),
                np.float32(1),  # rate_Hz_s (non usato per trinagular)
                np.float32(numz[0] * 1000),
                np.float32(numz[2] * 1000),
                np.float32(denz[1]),
                np.float32(denz[2]),
                np.float32(denz[3]),
                np.float32(denz[4]),
                np.float32(10),  # fend_Hz
                np.float32(amplitude),  # aend_mm
                np.float32(0)
            ]
            tx_bytes = b''.join(struct.pack('<f', val) for val in msg)
            self.serial_port.write(tx_bytes)
            print(f"Test Triangolare avviato: freq={freq} Hz, amp={amplitude} mm")

        elif self.wave_type.get() == "Sweep":
            # Test 1 - Sweep Frequency
            fInit_Hz = float(self.sweep_init_freq.get())
            fEnd_Hz = float(self.sweep_final_freq.get())
            amplitude = float(self.sweep_amplitude.get())
            wv_type = 0
            test_sel = 1   # Sweep
            rate_Hz_s = 1  # Rateo di variazione frequenza [Hz/s] (0.1/10 Hz/s)
            header_bits = f"{wv_type:01b}{1:01b}{1:01b}{1:01b}{0:01b}{test_sel:02b}{0:02b}"
            msghead = int(header_bits, 2)
            msg = [
                np.float32(msghead),
                np.float32(pos_init),
                np.float32(amplitude),
                np.float32(vcar),
                np.float32(fInit_Hz),      # Frequenza iniziale
                np.float32(rate_Hz_s),     # Rateo di variazione frequenza [Hz/s]
                np.float32(numz[0] * 1000),
                np.float32(numz[2] * 1000),
                np.float32(denz[1]),
                np.float32(denz[2]),
                np.float32(denz[3]),
                np.float32(denz[4]),
                np.float32(fEnd_Hz),       # Frequenza finale
                np.float32(amplitude),     # Ampiezza finale (se usata)
                np.float32(0)
            ]
            tx_bytes = b''.join(struct.pack('<f', val) for val in msg)
            self.serial_port.write(tx_bytes)
            print(f"Test Sweep avviato: f_start={fInit_Hz} Hz → f_end={fEnd_Hz} Hz, amp={amplitude} mm")

        elif self.wave_type.get() == "Profili ISO":

            # Test 2 - Quarter Car / Random
            test_sel = 2  # Quarter car / Random
            vcar = float(self.QC_car_velocity.get())

            # Aggiorna self.numz e self.denz usando la funzione che calcola la TF del quarter-car
            self.QC_transf_func()

            # Leggi la selezione strada (assicurati sia un intero)
            try:
                gr_sel_val = int(self.Gr_selection.get())
            except Exception:
                gr_sel_val = 0
                messagebox.showwarning("Attenzione", "Selezione profilo ISO non valida, impostato su 0 (Asfalto liscio)")

            # Preleva numz/denz calcolate; fallback su params se non disponibili
            numz = self.numz
            denz = self.denz
            if numz is None or len(numz) < 5:
                numz = self.params.get('numz', [1, 1, 1, 1, 1])
            if denz is None or len(denz) < 5:
                denz = self.params.get('denz', [1, 1, 1, 1, 1])

            header_bits = f"{0:01b}{1:01b}{1:01b}{1:01b}{0:01b}{test_sel:02b}{gr_sel_val:02b}"
            msghead = int(header_bits, 2)

            msg = [
                np.float32(msghead),
                np.float32(pos_init),
                np.float32(amplitude),
                np.float32(vcar),
                np.float32(freq),
                np.float32(1),  # rate_Hz_s (non usato per quarter car)
                np.float32(numz[0] * 1000),
                np.float32(numz[2] * 1000),
                np.float32(denz[1]),
                np.float32(denz[2]),
                np.float32(denz[3]),
                np.float32(denz[4]),
                np.float32(10),  # fend_Hz (placeholder)
                np.float32(amplitude),  # aend_mm (placeholder)
                np.float32(0)
            ]

            tx_bytes = b''.join(struct.pack('<f', val) for val in msg)
            self.serial_port.write(tx_bytes)
            print(f"Test Random/Quarter Car avviato: strada={gr_sel_val}, vcar={vcar} km/h")

        elif self.wave_type.get() == "Time History":
            # Test 3 - Renault / Time History
            print("Time history test")
            test_sel = 3
            header_bits = f"{0:01b}{1:01b}{1:01b}{1:01b}{0:01b}{test_sel:02b}{0:02b}"
            msghead = int(header_bits, 2)
            msg = [
                np.float32(msghead),
                np.float32(pos_init),
                np.float32(amplitude),
                np.float32(vcar),
                np.float32(freq),
                np.float32(1),
                np.float32(numz[0] * 1000),
                np.float32(numz[2] * 1000),
                np.float32(denz[1]),
                np.float32(denz[2]),
                np.float32(denz[3]),
                np.float32(denz[4]),
                np.float32(freq),
                np.float32(amplitude),
                np.float32(0)
            ]
            tx_bytes = b''.join(struct.pack('<f', val) for val in msg)
            self.serial_port.write(tx_bytes)
            print(f"Test Time History avviato: vcar={vcar} km/h")

        #Avvia thread di lettura
        self.test_running = True
        self.start_button.config(state='disabled')
        self.stop_button.config(state='normal')
        
        # self.read_thread = threading.Thread(target=self.read_serial_data, daemon=True)
        # self.read_thread.start()

    def stop_test(self):
        if not self.serial_port or not self.serial_port.is_open:
            return
        
        # Invia comando di posizionamento
        header_bits = f"{0:01b}{1:01b}{1:01b}{0:01b}{0:01b}{0:02b}{2:02b}"
        msghead = int(header_bits, 2)

        # Invia comando di stop
        header_bits = f"{0:01b}{1:01b}{1:01b}{0:01b}{1:01b}{0:02b}{2:02b}"
        msghead = int(header_bits, 2)

        msg = [
            np.float32(msghead),
            np.float32(float(self.posizione_iniziale.get())),
            np.float32(0), np.float32(0), np.float32(0), np.float32(0),
            np.float32(self.params.get('numz', [0, 0, 0])[0] * 1000),
            np.float32(self.params.get('numz', [0, 0, 0])[2] * 1000),
            np.float32(self.params.get('denz', [0, 0, 0, 0, 0])[1]),
            np.float32(self.params.get('denz', [0, 0, 0, 0, 0])[2]),
            np.float32(self.params.get('denz', [0, 0, 0, 0, 0])[3]),
            np.float32(self.params.get('denz', [0, 0, 0, 0, 0])[4]),
            np.float32(0), np.float32(0), np.float32(0)
        ]

        tx_bytes = b''.join(struct.pack('<f', val) for val in msg)
        self.serial_port.write(tx_bytes)

        # # Ferma thread
        self.test_running = False
        # if self.read_thread:
        #     self.read_thread.join(timeout=2)

        self.start_button.config(state='normal')
        self.stop_button.config(state='disabled')
        
        print("Test fermato")

    def on_closing(self):
        """Gestisce la chiusura della finestra"""
        self.readSerialOn = False
        
        if self.read_thread and self.read_thread.is_alive():
            self.read_thread.join(timeout=2)
        
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.close()
                print("Porta seriale chiusa")
            except:
                pass
        
        self.root.destroy()

    def resource_path(self, relative_path):
        try:
            base_path = sys._MEIPASS
        except AttributeError:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)


# Avvio applicazione
def main():
    root = tk.Tk()
    root.option_add("*Font", "Inter 12")
    app = NVHApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()