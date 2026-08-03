import os
#Reduces crash potential when multiprocessing
os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"
from paddleocr import PaddleOCR
import multiprocessing as mp
import pymupdf
import os
import shutil
import gc

#This function does the main extraction task. It will be fed an image of a single page of text, and run PaddleOCR on the image. It will then return the extracted text as a dictionary entry labelled by page.
def extract_page(path):
    #Get page number
    num=int(path[::-1][4:path[::-1].index("e")][::-1])
    #Initialize PaddleOCR
    ocr = PaddleOCR(use_angle_cls=True, lang='en', enable_mkldnn=False)
    #Extract the text
    result = ocr.predict(path)
    texts = []
    #Formats output text
    for item in result:
        texts.extend(item.get('rec_texts', []))
    #cleans unnessesary local variables to prevent boundless memory usage
    del result
    gc.collect()
    #returns text
    return {"pagenum":num, "text":texts}

#Main program
if __name__ == "__main__":
    #Takes in filepath to PDF and opens file
    pdfpath=input("Path to PDF: ")
    document = pymupdf.open(pdfpath)
    #Creates a temporary directory to store png conversions of the PDF pages
    dump_dir = pdfpath[::-1][pdfpath[::-1].index("/"):][::-1]+"pic_dump"
    res=input(str(dump_dir)+" okay for temporary file storage? Y for yes, otherwise specify new directory path. ")
    if res=="Y" or res=="y":
        pass
    else:
        dump_dir=res
    os.makedirs(dump_dir, exist_ok=True)
    #Converts all pages to images, stored in above directory
    for i, page in enumerate(document):
        img = page.get_pixmap(dpi=85) #Can increase/lower DPI value for better accuracy/speed respectively
        img.save(f"{dump_dir}/page{i}.png")
        
    document.close()
    #Creates a list of the paths to each individual page
    inpaths = [os.path.join(dump_dir, f) for f in os.listdir(dump_dir) if f.endswith(".png")]
    #print(inpaths)
    #Runs the above "extract_page()" for each image filepath using 4 processes (potentially fewer depending on CPU)
    with mp.Pool(processes=min(4, os.cpu_count())) as pool:
        output = pool.map(extract_page, inpaths)
    #Deletes temporary image folder
    shutil.rmtree(dump_dir)
    #Sorts extracted texts by pagenumber
    output.sort(key=lambda x: x["pagenum"])
    print(output)
