clc
clear
close all

%% Target parameters
fpwm = 20e3;
Tpwm = 1/fpwm;
Ts = Tpwm;
Tper = 10*Ts;
Tserial = Tper;
Tref = 100*Ts;
% target = mcb_SetProcessorDetails('F28379D',fpwm);
dataType = 'single';

%% Control parameters
Kp = 0.08;
I = 0.1;
KiTs = Kp*I*Ts;
rate_lim=5;

%% Sensor parameters
ADC.Gain = 3/(2^12-1);

ISEN.Gain = ADC.Gain/(0.007*20);
ISEN.Offset(1) = 2048;
ISEN.Offset(2) = 2048;
ISEN.Offset(3) = 2048;
VSEN.Gain = ADC.Gain * 86.99/4.99;

POS.gain = 75/3.3*3/4095;
POS.offset = (19.32+68.18)/2;

%% Profile treatment
data = readtable('QV-500hz-mm.xlsx');
t = data.Var1;
q = data.Var2;
tint = 0:1/200:t(end);
qint = interp1(t,q,tint);

%% Quarter car model
ms = 400;
mu = 40;
ks = 20e3;     % N/m
ku = 200e3;    % N/m

cs = 5000;
s = tf('s');
Gs = -s^2*(ku*ms)/(s^4*ms*mu+s^3*cs*(ms+mu)+s^2*(ku*ms+ks*(ms+mu))+s*ku*cs+ks*ku);
Gz = c2d(Gs,Tref,'tustin');
[numz,denz] = tfdata(Gz,'v');