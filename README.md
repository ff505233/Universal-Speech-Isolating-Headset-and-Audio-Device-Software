A real-time audio processing system designed for individuals with auditory hypersensitivity. The software isolates human speech from environmental noise using a hardware beamformer 
and a neural network-based noise suppression engine.

Hardware Requirements: Rapsberry Pi 4B, Respeaker 4 microphone array V2.0, buck converter/voltage regulator, high fedility noise cancelling headphones (3.5mm audio).

Logic: Script allows a 2 second period for the user to calibrate the direction of the fixed beam before it locks in place. Once the beam is locked, it samples audio input from that direction, denoises it using rnnoise, detects samples containing speech by using googles voice activity detection(VAD) WebRTC, and then passes speech frames through for playback if they fall within a Smoothed Root Mean Square (SRMS) window (250 < SRMS < 1500 units). This ignored background whispers and supresses sudden and painfully loud impulses.

Note: tuning.py was developed by Seeed Studio for the 
ReSpeaker 4-Mic Array V2.0. It is used here to interface with the 
on-board XMOS microphone array and hardware beamformer.

Credits: 

tuning.py -> https://github.com/respeaker/usb_4_mic_array
rnnoise (nueral network used for denoising) -> https://github.com/xiph/rnnoise
WebRTCVAD (Voice activity detection) -> https://github.com/wiseman/py-webrtcvad
