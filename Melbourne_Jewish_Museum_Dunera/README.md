# Melbourne Jewish Museum Concert Archive  

## Technical Context  
### The Problem
A persistent topic in modern computing is the necessity of converting historic documents into structured and digitized forms. Centuries of data-rich documents and photographs provide invaluable information about the past, but the physical format limits their ability to be analyzed through modern data science techniques. As such, the process of document digitization has become critical in allowing data scientists to investigate information about the past. Some aspects of digitization have been made trivial with technology: any photograph or document can be scanned and converted into a .jpg file to be visually analyzed, all with minimal effort from a user. The critical task of text extraction (converting text written on a physical document or contained in a photo into computer-parsable unicode), however, remains problematic. The various writing styles, formats, and languages found in books, magazines, and historic documents make finding a purely algorithmic solution to conversion very difficult. Manual transcription of documents by humans, while highly accurate, is prohibitively expensive and time consuming. Modern advancements in AI technology, particularly the development of large language models, provide a useful approach to the issue, combining the speed of algorithmic methods with human-like reasoning and accuracy.  
<img width="481" height="534" alt="image" src="https://github.com/user-attachments/assets/451e6af0-77e9-4c2b-b301-b392ff534f4e" />  
*Transcribing such writing can be difficult for a computer*  

### The Solution: OCR
Optical Character Recognition is the most common system for extracting text from images. Though OCR has been approached using various methods throughout the past century, recent developments in AI technology have highlighted deep learning (neural networks) and large language models as some of the most effective solutions for the task.

## Dunera Dataset
The Jewish_Concert_Archive.ipynb notebook found in this folder explores the Dunera Dataset, a collection of documents at the Jewish Museum of Australia originally collected by Majer 'Ivan' Pietruschka, a Polish-born violinist and orchestra leader. The collection contains concert programs, photographs, and other documents from England and southeastern Australia (predominantly from wartime internment camps) over the period 1939-1944. Its name comes from the HMT Dunera, a ship which transported Pietruschka and other "enemy aliens" from England to Australia in 1940. This notebook focuses on the analysis of concert programs within the dataset. Digital scans of the original dataset can be found here: https://drive.google.com/drive/u/1/folders/1pIVgklhE-BWAUuEbBslLDhX0zOT86P49

### Text Extraction
Before we can analyze the information contained in the documents, it is necessary to extract the text from the documents. Additionally, for the purposes of later analysis, it would be useful to structure such text into a JSON file, which stores text and other data in a hierarchical structure. I chose to approach this task using Anthropic's Claude Opus 5 model, an LLM which contains built in OCR methods. By uploading the above dataset and prompting the model with:
```
I've uploaded a compressed folder containing several folders. In each subfolder are several images, some of which are of concert programs.
Some are not concert programs, and you can ignore them. Some concert programs are split between multiple image files within a single subfolder,
and should be treated as a single, multipart concert program. You are a musicologist attempting to organize the data contained in these files
into a single JSON file. The JSON file should include all concert events contained in the folder. Each concert should have the associated acts,
songs, venue, location, and date contained in the JSON file, with individual song credits listed in addition to overall performance credits
(including but not limited to, the composer, director, musicians, etc.). Some songs are based on the melodies of tunes contemporary to the
performance, and such tunes should be listed if provided. Lyrics to songs should be included if provided. Additionally, include an "Additional notes"
section for each performance and song, if relevant, containing any unsorted trivia about the corresponding song or performance.
```
...the model returned a JSON file reflecting the information contained in the documents. After some further fine tuning of the structure and text through additional prompts, I settled on the following JSON structure, and prompted the model to finalize the JSON as such:
```
-archive overview  
-concerts  
|-title  
|-alternate titles  
|-type  
|-venue  
|-location  
|-date  
|-presented_by  
|-overall_credits  
|-acts  
||-act_name  
||-songs  
|||-number  
|||-title  
|||-type  
|||-credits  
|||-composer  
|||-lyrics  
|||-performers  
|||-arranger  
|||-based_on_tune  
|||-additional_notes  
```
The resulting JSON file can be found here as "jewish_concert_archive.json"  
  
  
<img width="484" height="659" alt="image" src="https://github.com/user-attachments/assets/f0913f7e-2029-4805-909b-d11ebbaf0790" />
  
<img width="1211" height="719" alt="image" src="https://github.com/user-attachments/assets/00a8bd82-a775-4b11-a0a3-d6e6ed8792f3" />

*The original concert program compared to (part of) the extracted text in a JSON file*

## Working through the notebook

### Setup
To begin, ensure that you have Python 3.9+ installed to your device. Additionally, install the following libraries/packages to the correct Python version if you have not already:

- plotly
- networkx
- matplotlib
- pyvis
- pandas
- seaborn
- langchain-openai

These libraries/packages can be installed with the terminal command:
```
$pip install [package name]
```
or 
```
$pip3 install [package name]
```
depending on the pip version you have installed.

### Loading the data  
The first block of code will load the JSON file and isolate the relevant data to be used in the rest of the notebook.
### Asking questions about the data (optional)  
If you have questions about the data, the following two code blocks allow you to prompt an LLM agent about the information contained in the JSON file. The first block of code requires you to input an OpenAI API key in order to access this feature (this code will not be stored). If you do so, you can then run the next block of code to ask a question to the agent. The agent has access to the data contained in the JSON file, and will attempt to respond to your question using such.
<img width="1321" height="441" alt="image" src="https://github.com/user-attachments/assets/c46fd1b8-3754-4cd2-9026-f51cfd97f6d5" />  
*An example question and (partial) response*
### Creating a network
The following code block uses the python package *pyvis* to create a network visualization of the performance data. Each individual performance is assigned to a node (color coded by the location of the performance: Hay Internment Camp, NSW - Blue; Tatura Internment Camp, VIC - Green; Melbourne, VIC - Cyan; Other Locations - Purple) and an edge is created between each performance which shares a song (yellow edge) or performer (white edge). This is done by parsing the data contained in the JSON file to identify duplicate performers or songs between multiple performances. The resulting network graph is saved as "performance_network.html".
<img width="964" height="671" alt="image" src="https://github.com/user-attachments/assets/b10589bd-a92f-408e-ae2c-bea6259d0cde" />  
*Part of the network, highlighting shared performers between two performances*
### Locations over time
The final code block uses the python package *seaborn* to create a heatmap showing the locations of recorded performances over time. This chart is stored as "locations.png".  
<img width="616" height="512" alt="locations" src="https://github.com/user-attachments/assets/e2adfdb0-2155-450a-87e0-ba1b700cf79c" />  
*Graph of performance locations over time*






