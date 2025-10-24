class MyApp:
    def __init__(self, root):
        self.root = root
        self.serial_port = None
        self.read_thread = None
        self.readSerialOn = False

        # Pulsante o evento che avvia la lettura
        self.start_button = tk.Button(root, text="Start", command=self.start_test)
        self.start_button.pack()

        self.stop_button = tk.Button(root, text="Stop", command=self.stop_test)
        self.stop_button.pack()

    def start_test(self):
        print("Test avviato")
        if not self.serial_port:
            self.open_serial()

        self.readSerialOn = True
        self.start_serial_thread()

    def stop_test(self):
        print("Test fermato")
        self.readSerialOn = False

    def open_serial(self):
        import serial
        self.serial_port = serial.Serial('COM3', 115200, timeout=0.5)

    def start_serial_thread(self):
        """Lancia il thread di lettura"""
        if self.read_thread and self.read_thread.is_alive():
            print("Thread già attivo")
            return

        print("Avvio thread lettura seriale...")
        self.read_thread = threading.Thread(target=self.read_serial_data, daemon=True)
        self.read_thread.start()

    def read_serial_data(self):
        """Thread di lettura seriale"""
        Nd = int(1 * 6 * 1001)
        header = [17733, 21331]

        while self.readSerialOn and self.serial_port and self.serial_port.is_open:
            try:
                rawdata = self.serial_port.read(Nd * 2)
                if len(rawdata) < 4:
                    continue

                rawdata_uint16 = list(struct.unpack('<' + 'H' * (len(rawdata)//2), rawdata))
                pos = [i for i in range(len(rawdata_uint16)-1) if rawdata_uint16[i:i+2] == header]

                if not pos:
                    print("No header found — scheduling restart")
                    self.readSerialOn = False
                    # Riavvia thread dopo 500ms, MA nel main thread
                    self.root.after(500, self.restart_serial_thread)
                    break

                # ... elaborazione dati qui ...
                print(f"{len(pos)} header trovati")
                self.root.after(0, self.update_plot)

            except Exception as e:
                print(f"Errore lettura seriale: {e}")
                continue

    def restart_serial_thread(self):
        """Richiamata da Tkinter (main thread)"""
        if not self.readSerialOn:
            print("Restarting serial thread...")
            self.serial_port.reset_input_buffer()
            self.serial_port.reset_output_buffer()
            self.readSerialOn = True
            self.start_serial_thread()

    def update_plot(self):
        # aggiornamento grafico
        pass
