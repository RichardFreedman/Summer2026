# Sound Event Detection (for Paradisec)
## Motivation
In analyzing the Paradisec audio catalog, the ability to differentiate between pieces of audio which contain music and pieces of audio which contain speech was deemed to be an important feature for analysis. As such, this notebook seeks to provide a straightforward approach to labeling features of an audio track, as well as detecting locations of speech.
## Background: The Fourier Transform and Librosa
To approach such a task, we must first find a way to identify and categorize various sounds according to their features. Looking at audio in its most fundamental form, any sound can be represented by a wave of varying amplitude over time. Such a wave corresponds to the physical motion of particles which creates such a sound in the real world. As such, representing sound digitally as a wave gives a simple and easy to understand digitization of audio. However, such a representation can be difficult to extract identifying information from directly. To be able to easily distinguish various features of audio, it becomes advantageous to convert audio in the form of a waveform to audio in the form of a spectrogram. A mathematical process known as the Fourier transform allows any signal of varying amplitude over time to instead be represented as amplitude over varying frequencies. This is based of the mathematical principle that any waveform, no matter how complex, can be broken down into the sum of sine waves of varying frequency and amplitude. By splitting up an audio clip into very small (several millisecond) clips, performing a Fourier transform on each of these clips, and then combining each of these amplitude vs. frequency "frames" into a graph to show how they evolve over time, you can convert a two-dimensional graph of amplitude vs. time into a three dimensional graph of amplitude vs. frequency vs. time. This process allows us to convert an audio waveform to an audio spectrograph. Each representation contains the exact same information, but for the purposes of analysis, a spectrograph is easier to extract data from.
<img width="1083" height="652" alt="image" src="https://github.com/user-attachments/assets/9f8e69ba-727d-46e7-9741-d11fd88e4198" />
*Two graphs, the top being amplitude vs. time (audio waveform), the bottom being frequency vs. time with color gradient representing amplitude (audio spectrogram). Both contain the exact same sonic information.*  
  
The python audio analysis library *Librosa* does the conversion between waveform and spectrogram automatically, and also extracts useful information about the resulting spectrogram. Given that the identification of the amplitude of various tones over time is a critical aspect of audio analysis, the information which Librosa provides is quite useful for the identification of audio elements. 
<img width="913" height="610" alt="image" src="https://github.com/user-attachments/assets/ead94de0-579f-4638-9fca-54ec4bc32093" />
*The parameters which Librosa extracts from the audio are data about the spectral representation of audio itself. However, given the form of a spectrogram, these parameters are very useful.*
## PANNs Inference and webrtcVAD
With the extracted audio data we have from Librosa, it is now necessary to determine a way to categorize audio clips using this information. In a future iteration of this project, I hope to train a logistic regression model on data from the PARADESIC catalog to create a PARADESEC-specific speech vs. music identifier. For now, however, the project uses two online audio tagging libraries that have already been developed:
- PANNs Inference is a collection of Pretrained Audio Neural Networks which process data extracted via Librosa and predict a confidence score for 527 separate audio tags. These tags include labels like "speech", "music", "traffic" and are assigned a value from 0 (certainly not present in the audio) to 1 (certainly present in the audio).
- webrtcVAD is a Voice Activity Detection library for Python which processes frequency amplitude information for small slices of an audio spectrogram to predict whether speech is or is not present in an audio clip.  

By combining the information produced by these two libraries, this notebook labels the sonic features present throughout an audio file, and predicts when speech occurs.

## Working through the notebook
### Setup
To begin, ensure that you have Python 3.9+ installed to your device. Additionally, install the following libraries/packages to the correct Python version if you have not already:

- librosa
- matplotlib
- numpy
- panns-inference
- webrtcvad
- pydub

These libraries/packages can be installed with the terminal command:
```
$pip install [package name]
```
or 
```
$pip3 install [package name]
```
depending on the pip version you have installed.

### Loading in Audio/Viewing Spectrogram
The first block of code loads in an audio file from a provided path, and converts it into a Librosa audio object. Additionally, it outputs the spectrogram representation of the audio for reference.
<img width="751" height="690" alt="image" src="https://github.com/user-attachments/assets/d0d9d00c-d9e1-4ad8-9209-a5f38b8574f1" />  
*An example spectrogram output.*
### Extracting Audio Tags by the Second
This block of code splits the full audio file into separate 1 second chunks, and then uses PANNs Inference and webrtcVAD (as described above) to label each individual second with the six highest-confidence audio tags (via PANNs Inference) as well as a prediction as to whether that second contains speech (via webrtcVAD).  
The next block of code allows a user to view this label data by entering a range of seconds, for which the labels will be printed.
<img width="729" height="683" alt="image" src="https://github.com/user-attachments/assets/52c85414-2344-4882-a6a7-a54a023f29ed" />  
*An example output displaying audio tags and predicted speech labels for a range of seconds.*
### Predicting Speech Locations
The next section of code combines the information extracted via PANNs Inference and webrtcVAD to predict whether each individual second of audio contains speech. Each second will first be labelled as 0 (no speech - no high confidence speech labels from PANNs Inference and majority of 10ms clips predicted to have no speech by webrtcVAD), 1 (possible speech - some medium confidence speech labels from PANNs Inference and majority of 10ms clips predicted to have no speech by webrtcVAD), or 2 (likely speech - some high confidence speech labels from PANNs Inference or majority of 10ms clips predicted to have speech by webrtcVAD). The program then does a second pass, categorizing seconds with possible speech that are in between seconds with definite speech as having speech, and labelling all other possible speech seconds as not having speech. This process helps to filter out false positives and negatives in sections which predominantly lack or have speech, respectively. The program then outputs its prediction as to whether each individual second has speech (True or False).  
<img width="87" height="456" alt="image" src="https://github.com/user-attachments/assets/113cf64a-a142-4cf9-9f04-e846f929e257" />  
*Sample (partial) speech prediction output*
### Label Graph Over Time
The next block of code reprocesses the PANNs Inference data at a higher rate (multiple predictions per second), and formats the data in a way which could be plotted. The next (and final) code block plots the confidence of the five most prevalent audio tags over the course of the clip, before finally saving the graph as "output_graph.png".
<img width="1276" height="235" alt="image" src="https://github.com/user-attachments/assets/36acef71-d29d-441a-b86f-8ed07010fe66" />  
*Graph of tag confidence over time for a spoken word song preceded by a speech* 


 
