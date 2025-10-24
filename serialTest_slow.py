import numpy as np
import matplotlib.pyplot as plt
import serial.tools.list_ports
import serial
import struct
import time
import openpyxl
from params_NVH import params_NVH

def run_test():
    # Import parameters
    p = params_NVH()

    # Mostra le porte disponibili e chiedi all'utente quale usare
    ports = list(serial.tools.list_ports.comports())
    print("Porte seriali disponibili:")
    for idx, port in enumerate(ports):
        print(f"{idx+1}: {port.device} ({port.description})")
    if not ports:
        print("Nessuna porta seriale trovata.")
        return
    selection = input("Seleziona il numero della porta a cui collegarti: ")
    try:
        port_idx = int(selection) - 1
        port_name = ports[port_idx].device
    except (ValueError, IndexError):
        print("Selezione non valida.")
        return

    # Serial setup
    sp = serial.Serial(
        port=port_name,
        baudrate=12_000_000,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=2
    )

    if not sp.is_open:
        sp.open()

    # Message parameters
    wv_type = 0         # Waveform type in sine test (0 sine; 1 triangle)
    pow_en = 0          # Enable power (0/1)
    pos_en = 1          # Enable position control (0/1)
    test_start = 1      # Start test (0/1)
    test_stop = 0       # Stop test (0/1)
    test_sel = 0        # Select test (0 Sine; 1 Sweep; 2 QC; 3 Renault)
    Gr_sel = 2          # Select road profile (0 A; 1 B; 2 C; 3 D)
    pos_init_mm = 5    # Initial position (-20/20 mm)
    amplitude_mm = 5    # Waveform or sweep initial amplitude (0/20 mm)
    vcar_kmh = 35       # Vehicle speed (10/200 km/h)
    freq_Hz = 1         # Waveform or sweep initial frequency (0.1/100 Hz)
    rate_Hz_s = 1       # Sweep rate (0.1/10 Hz/s)
    fend_Hz = 10        # Sweep final frequency (0.1/100 Hz)
    aend_mm = 10        # Sweep final amplitude (0/20 mm)

    # Header message: 1 bit each except test_sel (2 bits) and Gr_sel (2 bits)
    header_bits = f"{wv_type:01b}{pow_en:01b}{pos_en:01b}{test_start:01b}{test_stop:01b}" + \
                  f"{test_sel:02b}{Gr_sel:02b}"
    msghead = int(header_bits, 2)

    # Construct message (same order as MATLAB)
    msg = [
        np.float32(msghead),
        np.float32(pos_init_mm),
        np.float32(amplitude_mm),
        np.float32(vcar_kmh),
        np.float32(freq_Hz),
        np.float32(rate_Hz_s),
        np.float32(p['numz'][0] * 1000),
        np.float32(p['numz'][2] * 1000),  # numz[2] because in MATLAB is numz(3)
        np.float32(p['denz'][1]),         # denz[2] in MATLAB
        np.float32(p['denz'][2]),
        np.float32(p['denz'][3]),
        np.float32(p['denz'][4]),
        np.float32(fend_Hz),
        np.float32(aend_mm),
        np.float32(0)
    ]

    # Pack and send message as float32
    tx_bytes = b''.join(struct.pack('<f', val) for val in msg)
    sp.write(tx_bytes)

    # Receive and plot
    Tserial = p['Tserial']
    Nd = int(0.5 * 6 * 1001)
    Ntot = int(10 / Tserial)
    time_vect = np.arange(Ntot) * Tserial
    pos_ref = np.zeros(Ntot)
    pos_meas = np.zeros(Ntot)
    st = np.zeros(Ntot)

    try:
        while True:
            # Lettura dei dati seriali (2 byte per ogni uint16)
            rawdata = sp.read(Nd * 2)
            rawdata_uint16 = list(struct.unpack('<' + 'H' * (len(rawdata) // 2), rawdata))

            # Trova gli header (17733, 21331)
            header = [17733, 21331]
            pos = [i for i in range(len(rawdata_uint16) - 1) if rawdata_uint16[i:i + 2] == header]
            for idx in reversed(pos):
                del rawdata_uint16[idx:idx + 2]  # Rimuovi header

            if not pos:
                raise Exception("No packet header found")

            # Riallinea i dati a multipli di 3
            istart = (pos[0] % 3)
            rawdata_aligned = rawdata_uint16[istart:]
            iend = (len(rawdata_aligned) // 3) * 3
            rawdata_aligned = rawdata_aligned[:iend]

            # Converti i dati in fixed-point signed (1,16,9) come in MATLAB
            data = np.array(rawdata_aligned, dtype=np.uint16).reshape(-1, 3)
            data_int16 = data.view(dtype=np.int16)  # Reinterpreta i bit come signed int16
            scale = 2 ** 9  # 9 bit frazionari → numerictype(1,16,9)
            data_float = data_int16.astype(np.float32) / scale

            # Aggiorna i buffer circolari
            L = len(data_float)
            pos_ref = np.roll(pos_ref, -L)
            pos_meas = np.roll(pos_meas, -L)
            st = np.roll(st, -L)
            pos_ref[-L:] = data_float[:, 0]
            pos_meas[-L:] = data_float[:, 1]
            st[-L:] = data_float[:, 2]  # ⚠️ CORRETTO ora, come in MATLAB!

            # Plot
            plt.clf()
            plt.subplot(2, 1, 1)
            plt.plot(time_vect, pos_ref, label='ref')
            plt.plot(time_vect, pos_meas, label='meas')
            plt.legend(loc='upper right')
            plt.ylabel("position [mm]")
            plt.xlim([0, 10])

            plt.subplot(2, 1, 2)
            plt.plot(time_vect, st)
            plt.ylabel("state")
            plt.xlabel("time [s]")
            plt.xlim([0, 10])
            plt.pause(0.01)

    except Exception as e:
        print(f"Packet inconsistency! {e}")
    finally:
        print("Closing serial port...")
        sp.close()
        print("Serial port closed.")

if __name__ == "__main__":
    run_test()