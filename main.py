import pyaudio
import ctypes
import webrtcvad
import numpy as np
import os
from scipy.signal import medfilt
import sys
sys.path.append('/home/fokfr/usb_4_mic_array')
from tuning import Tuning
import usb.core
import time

# Find ReSpeaker 4-Mic Array V2
dev = usb.core.find(idVendor=0x2886, idProduct=0x0018)
if not dev:
    raise RuntimeError("ReSpeaker device not found")
mic = Tuning(dev)

#Calibration
mic.write('FREEZEONOFF', 0)
print("Beamformer unfrozen. Please make a short sound in front of the array...")

time.sleep(1.0)

import numpy as np
doa_samples = []
for i in range(5):
    doa_samples.append(mic.direction)
    time.sleep(0.2)

doa_angle = int(np.median(doa_samples))

#Freeze beamformer at calibrated angle
mic.write('FREEZEONOFF', 1)
print(f"Beamformer frozen at {doa_angle}°")

#RNNoise Setup
lib_path = os.path.abspath("./.libs/librnnoise.so")
rnnoise = ctypes.cdll.LoadLibrary(lib_path)
rnnoise.rnnoise_create.argtypes = [ctypes.c_void_p]
rnnoise.rnnoise_create.restype = ctypes.c_void_p
rnnoise.rnnoise_destroy.argtypes = [ctypes.c_void_p]
rnnoise.rnnoise_process_frame.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_float),
    ctypes.POINTER(ctypes.c_float)
]
rnnoise.rnnoise_process_frame.restype = ctypes.c_float

null_ptr = ctypes.c_void_p(0)
denoise_state = rnnoise.rnnoise_create(null_ptr)
if not denoise_state:
    raise RuntimeError("Failed to initialize RNNoise denoise state.")

# Audio setup 
FRAMES_PER_BUFFER = 480      # input frame size 30 ms 16kHz
PYAUDIO_OUT_BUFFER = 960     # output buffer 
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000


INPUT_DEVICE_INDEX = 1
OUTPUT_DEVICE_INDEX = 1

#Voice activity detection setup
vad = webrtcvad.Vad()
vad.set_mode(3)

#PyAudio
p = pyaudio.PyAudio()

stream_input = p.open(format=FORMAT,
                      channels=CHANNELS,
                      rate=RATE,
                      input=True,
                      input_device_index=INPUT_DEVICE_INDEX,
                      frames_per_buffer=FRAMES_PER_BUFFER)
stream_output = p.open(format=FORMAT,
                       channels=CHANNELS,
                       rate=RATE,
                       output=True,
                       output_device_index=OUTPUT_DEVICE_INDEX,
                       frames_per_buffer=PYAUDIO_OUT_BUFFER)

#Prime output buffer avoid initial underrun
prime = (b"\x00\x00") * PYAUDIO_OUT_BUFFER
for _ in range(3):
    stream_output.write(prime, exception_on_underflow=False)

print("STARTING STREAM")
print("Press 'q' to stop recording")

smoothed_value = 0

while True:
    try:
        data = stream_input.read(FRAMES_PER_BUFFER, exception_on_overflow=False)

        #Convert audio to float32
        samples = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
        samples = samples - np.mean(samples)

        if len(samples) != 480:
            continue

        #Denoising
        input_buffer = (ctypes.c_float * 480)(*samples)
        output_buffer = (ctypes.c_float * 480)()
        for i in range(2):
            rnnoise.rnnoise_process_frame(denoise_state, output_buffer, input_buffer)
            input_buffer = output_buffer

        #Convert back to int16
        denoised_sample = np.ctypeslib.as_array(output_buffer)
        filtered_sample = medfilt(denoised_sample, kernel_size=3)
        pcm_sample = np.clip(filtered_sample * 32768, -32768, 32767).astype(np.int16)
        pcm_bytes = pcm_sample.tobytes() 
        #Voice Activity Detection
        root_mean_square = np.sqrt(np.mean(pcm_sample.astype(np.float32) ** 2))
        alpha = 0.2
        smoothed_value = alpha*root_mean_square + (1-alpha)*smoothed_value
        print(f"RMS={root_mean_square:.2f} SRMS={smoothed_value:.2f}")
        is_speech = vad.is_speech(pcm_bytes, RATE)

        if is_speech:
            if smoothed_value > 250 and smoothed_value < 1500:
                stream_output.write(pcm_bytes, exception_on_underflow=False)
                print("speech playing...")
    except IOError as e:
        print(f"Error: {e}")
        break

#End stream
stream_input.stop_stream()
stream_input.close()
stream_output.stop_stream()
stream_output.close()
p.terminate()
rnnoise.rnnoise_destroy(denoise_state)


