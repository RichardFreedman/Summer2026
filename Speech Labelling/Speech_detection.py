import webrtcvad
from pydub import AudioSegment
vad=webrtcvad.Vad()
audio=AudioSegment.from_wav("") #Add filepath
audio=audio.set_channels(1)
outp=[]
for i in range(1000):
  audioclip=audio[i*30:i*30+30]
  raw_audio_data = audioclip.export(format="s16le").read()
  outp.append(vad.is_speech(raw_audio_data,48000))
print(outp)