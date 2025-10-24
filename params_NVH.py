import numpy as np
import pandas as pd
from scipy import signal
import control as ctrl

def params_NVH():
    # Target parameters
    fpwm = 20e3
    Tpwm = 1 / fpwm
    Ts = Tpwm
    Tper = 10 * Ts
    Tserial = Tper
    Tref = 100 * Ts
    dataType = 'float32'  # equivalente di 'single' in Python

    # Control parameters
    Kp = 0.08
    I = 0.1
    KiTs = Kp * I * Ts
    rate_lim = 5

    # Sensor parameters
    ADC_Gain = 3 / (2**12 - 1)

    ISEN_Gain = ADC_Gain / (0.007 * 20)
    ISEN_Offset = [2048, 2048, 2048]

    VSEN_Gain = ADC_Gain * 86.99 / 4.99

    POS_gain = 75 / 3.3 * 3 / 4095
    POS_offset = (19.32 + 68.18) / 2

    # Profile treatment
    data = pd.read_excel('QV-500hz-mm.xlsx')
    t = data.iloc[:, 0].values
    q = data.iloc[:, 1].values

    tint = np.arange(0, t[-1], 1 / 200)
    qint = np.interp(tint, t, q)

    # Quarter car model
    ms = 400
    mu = 40
    ks = 20e3
    ku = 200e3
    cs = 5000

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

    # # Continuous transfer function
    # num = [-ku * ms, 0, 0, 0, 0]
    # den = [
    #     ms * mu,
    #     cs * (ms + mu),
    #     ku * ms + ks * (ms + mu),
    #     ku * cs,
    #     ks * ku
    # ]
    # Gs = signal.TransferFunction(num, den)

    # # Discretize using Tustin (bilinear)
    # Gz = Gs.to_discrete(Tref, method='bilinear')

    # numz = Gz.num
    # denz = Gz.den

    # print("Parameters for NVH test:")
    # print(f"numz = {numz} ")
    # print(f"denz = {denz} ")

    return {
        'Ts': Ts,
        'Tper': Tper,
        'Tserial': Tserial,
        'Tref': Tref,
        'Kp': Kp,
        'KiTs': KiTs,
        'rate_lim': rate_lim,
        'ISEN_Gain': ISEN_Gain,
        'ISEN_Offset': ISEN_Offset,
        'VSEN_Gain': VSEN_Gain,
        'POS_gain': POS_gain,
        'POS_offset': POS_offset,
        'tint': tint,
        'qint': qint,
        'numz': numz,
        'denz': denz
    }
