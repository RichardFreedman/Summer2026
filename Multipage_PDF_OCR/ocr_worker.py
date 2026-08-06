import os
#Reduces crash potential when multiprocessing
os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"
from paddleocr import PaddleOCR
import gc

#This function does the main extraction task. It will be fed the path to a single image, and run PaddleOCR on it. It returns the extracted text lines (each tagged with a confidence score) tagged with the image's filename.
#Defined in its own module (rather than inline in the notebook) because macOS's multiprocessing "spawn" start method
#re-imports whatever module a worker's target function lives in; a Jupyter kernel's __main__ isn't a real importable
#module, so a function defined in a notebook cell can't be found by spawned worker processes.
def extract_page(path):
    #Initialize PaddleOCR
    ocr = PaddleOCR(use_angle_cls=True, lang='en', enable_mkldnn=False)
    #Extract the text
    result = ocr.predict(path)
    lines = []
    #Pairs each recognized line with PaddleOCR's confidence score for it
    for item in result:
        texts = item.get('rec_texts', [])
        scores = item.get('rec_scores', [])
        lines.extend({"text": t, "confidence": round(float(s), 4)} for t, s in zip(texts, scores))
    #cleans unnessesary local variables to prevent boundless memory usage
    del result
    gc.collect()
    #returns lines, tagged by filename
    return {"filename": os.path.basename(path), "lines": lines}
