clc
clear
close all

params_NVH;

% Serial setup
% sp = serialport('COM8',12e6);
% sp.DataBits = 8;
% sp.Parity = 'none';
% sp.StopBits = 1;
% sp.ByteOrder = 'little-endian';
% sp.FlowControl = 'none';
% sp.Timeout = 2;

% fopen(sp);

%% State knowledge
% -2 Error
% -1 Ready to enable power
% 0 Power enabled
% 1 Initial positioning
% 2 Testing (Sine)
% 3 Testing (Sweep)
% 4 Testing (QC)
% 5 Testing (Renault)

%% Message parameters
wv_type = 0;            % Waveform type in sine test (0 sine; 1 triangle)
pow_en = 1;             % Enable power (0/1)
pos_en = 0;             % Enable position control (0/1)
test_start = 1;         % Start test (0/1)
test_stop = 0;          % Stop test (0/1)
test_sel = 0;           % Select test (0 Sine; 1 Sweep; 2 QC; 3 Renault)
Gr_sel = 2;             % Select road profile (0 A; 1 B; 2 C; 3 D)
pos_init_mm = 5;        % Initial position (-20/20 mm)
amplitude_mm = 5;       % Waveform or sweep initial amplitude (0/20 mm)
vcar_kmh = 35;          % Vehicle speed (10/200 km/h)
freq_Hz = 1;            % Waveform or sweep initial frequency (0.1/100 Hz)
rate_Hz_s = 1;          % Sweep rate (0.1/10 Hz/s)
fend_Hz = 10;           % Sweep final frequency (0.1/100 Hz)
aend_mm = 10;           % Sweep final amplitude (0/20 mm)
% Quarter car transfer fcn imported from params_NVH

%% Message construction
msghead = [dec2bin(wv_type),dec2bin(pow_en),dec2bin(pos_en),...
    dec2bin(test_start),dec2bin(test_stop),dec2bin(test_sel,2),...
    dec2bin(Gr_sel,2)];

msg = [single(bin2dec(msghead))...
    single(pos_init_mm),...
    single(amplitude_mm),...
    single(vcar_kmh),...
    single(freq_Hz),...
    single(rate_Hz_s),...
    single(numz(1)*1000),...
    single(numz(3)*1000),...
    single(denz(2)),...
    single(denz(3)),...
    single(denz(4)),...
    single(denz(5)),...
    single(fend_Hz),...
    single(aend_mm),...
    single(0),...
    ];



%% TX
write(sp,msg,'single')

%% RX (exit with CTRL-C)
Nd = 0.5*6*1001; % Single frame of 0.5 seconds
Ntot = 10/Tserial;
time = (0:Ntot-1)*Tserial;

pos_ref = zeros([Ntot,1]);
pos_meas = zeros([Ntot,1]);
st = zeros([Ntot,1]);

tic
for kdx = 1:2000 % Loop, can be replaced with a while loop.
    try
        rawdata = read(sp,Nd,'uint16');
        pos = strfind(rawdata,[17733,21331]);
        for idx = length(pos):-1:1
            rawdata(pos(idx):pos(idx)+1) = [];
        end
        istart = (pos(1)-1)-floor((pos(1)-1)/3)*3+1;
        rawdata = rawdata(istart:end);
        iend = floor(length(rawdata)/3)*3;
        rawdata = rawdata(1:iend);
        data = double(reinterpretcast(uint16(rawdata),numerictype(1,16,15-ceil(log2(45)))));
        data = reshape(data',3,[])';
        pos_ref = [pos_ref(length(data)+1:end);data(:,1)];
        pos_meas = [pos_meas(length(data)+1:end);data(:,2)];
        st = [st(length(data)+1:end);data(:,3)];

        figure(1)
        yyaxis right
        plot(time,st)
        ylabel('state')
        yyaxis left
        plot(time,pos_ref)
        hold on
        plot(time,pos_meas)
        hold off
        legend('ref','meas','location','east')
        xlabel('time [s]')
        ylabel('position [mm]')
        xlim([0,10])
        drawnow
    catch
        error('Packet inconsistency!')
        toc
    end
end