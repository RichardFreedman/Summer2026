Multi_Extraction.ipynb is an unsuccessful first attempt at the project. It can be ignored. multipage_extraction.py is the main program. It uses PaddleOCR, pymupdf, and Python's multiprocessing capabilities to extract text. It takes around 4 minutes to extract the text from a 50 page document with high comparative accuracy. I tested several other OCR systems before settling upon PaddleOCR; the results were as follows: 

Feeding images into a ChatGPT API individually seemed to be the most accurate method tested, as this method will also use human-like reasoning to ensure the transcribed text makes sense (for example, even if it is confident in the second and third characters individually being 1's, it can reason that the transcribed phrase will not be "A11s well that ends well"). The only issue with ChatGPT is its (literal) cost, which makes it difficult to recommend on a large scale. Despite its accuracy and speed (at least on the small scale which I tested it) the cost led me to seek other options. 

Tesseract OCR was the most reccomended option for Python integration, and though it worked quite well with typed text, it performed terribly on handwritten text.

Kraken OCR was more powerful than both Tesseract and PaddleOCR, but required far more setup (including either training a model on a corpus of text, or searching the web for a specific pretrained model). This might work best if running an OCR application off of a dedicated server, but isn't great for a "portible" solution.

OCRopus worked quite well running normally, but I ran into issues when attempting to use it with multiprocessing. It might be worth revisiting for someone who is more experienced with multiprocessing.

Other OCR packages I didn't try but might have promise are EasyOCR and Textract, the latter advertises similar performance to an LLM based OCR system, but requires linking to an AWS account and a persistent internet connection.

multipdf_extraction.py is an alteration of multipage_extraction.py made to work with multiple pdf files at once.
