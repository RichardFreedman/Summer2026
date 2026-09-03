import os
#Reduces crash potential when multiprocessing
os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"
from paddleocr import PaddleOCR
import multiprocessing as mp
import pymupdf
import os
import shutil
import gc
import json

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
    #DPI for PDF page to image conversion. Higher values improve OCR accuracy at the cost
    #of slower processing and more memory per page; 300 is the typical OCR sweet spot.
    DPI = 200
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
        img = page.get_pixmap(dpi=DPI)
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

    #Derives output basename from the input PDF path (strips directory and extension)
    base = os.path.splitext(os.path.basename(pdfpath))[0]
    out_dir = os.path.dirname(pdfpath) or "."

    #Writes the structured output as JSON
    json_path = os.path.join(out_dir, f"{base}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    #Writes the same output as a single TXT file, with a "===Page N===" header per page.
    #Fragments are joined with spaces rather than newlines, since PaddleOCR's rec_texts
    #are per detected text box, not per line, so newline-joining would introduce
    #artificial line breaks that don't correspond to real sentence/line structure.
    txt_path = os.path.join(out_dir, f"{base}.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        for entry in output:
            f.write(f"===Page {entry['pagenum']}===\n")
            f.write(" ".join(entry["text"]))
            f.write("\n\n")

    print(f"Wrote {json_path} and {txt_path}")
