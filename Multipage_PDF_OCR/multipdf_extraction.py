import os
#Reduces crash potential when multiprocessing
os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"
from paddleocr import PaddleOCR
import multiprocessing as mp
import pymupdf
import shutil
import gc
import json
import csv

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
    #Folders holding the source PDFs and the extracted output, relative to the working directory.
    INPUT_DIR = "input"
    OUTPUT_DIR = "output"

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    dump_dir = os.path.join(OUTPUT_DIR, "_tmp_pages")

    #Only picks up actual PDFs, ignoring stray files like .DS_Store
    pdf_names = sorted(f for f in os.listdir(INPUT_DIR) if f.lower().endswith(".pdf"))

    manifest_rows = []
    for pdf_name in pdf_names:
        base = os.path.splitext(pdf_name)[0]
        txt_name = f"{base}.txt"
        json_name = f"{base}.json"
        print(f"Processing {pdf_name}...")

        try:
            #Converts all pages of this PDF to images, stored in a temporary directory
            os.makedirs(dump_dir, exist_ok=True)
            document = pymupdf.open(os.path.join(INPUT_DIR, pdf_name))
            for i, page in enumerate(document):
                img = page.get_pixmap(dpi=DPI)
                img.save(f"{dump_dir}/page{i}.png")
            num_pages = document.page_count
            document.close()

            #Creates a list of the paths to each individual page
            inpaths = [os.path.join(dump_dir, f) for f in os.listdir(dump_dir) if f.endswith(".png")]
            #Runs "extract_page()" for each image filepath using 4 processes (potentially fewer depending on CPU)
            with mp.Pool(processes=min(4, os.cpu_count())) as pool:
                output = pool.map(extract_page, inpaths)
            #Sorts extracted texts by pagenumber
            output.sort(key=lambda x: x["pagenum"])

            #Writes the structured output as JSON
            with open(os.path.join(OUTPUT_DIR, json_name), "w", encoding="utf-8") as f:
                json.dump(output, f, indent=2, ensure_ascii=False)

            #Writes the same output as a single TXT file, with a "===Page N===" header per page.
            #Fragments are joined with spaces rather than newlines, since PaddleOCR's rec_texts
            #are per detected text box, not per line, so newline-joining would introduce
            #artificial line breaks that don't correspond to real sentence/line structure.
            with open(os.path.join(OUTPUT_DIR, txt_name), "w", encoding="utf-8") as f:
                for entry in output:
                    f.write(f"===Page {entry['pagenum']}===\n")
                    f.write(" ".join(entry["text"]))
                    f.write("\n\n")

            manifest_rows.append({
                "pdf_filename": pdf_name,
                "txt_filename": txt_name,
                "json_filename": json_name,
                "num_pages": num_pages,
                "status": "success",
            })
        except Exception as e:
            manifest_rows.append({
                "pdf_filename": pdf_name,
                "txt_filename": txt_name,
                "json_filename": json_name,
                "num_pages": "",
                "status": f"error: {e}",
            })
        finally:
            #Deletes temporary image folder before moving to the next PDF
            shutil.rmtree(dump_dir, ignore_errors=True)

    #Writes manifest.csv mapping each source PDF to its output txt/json filenames
    manifest_path = os.path.join(OUTPUT_DIR, "manifest.csv")
    with open(manifest_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["pdf_filename", "txt_filename", "json_filename", "num_pages", "status"])
        writer.writeheader()
        writer.writerows(manifest_rows)

    print(f"Processed {len(pdf_names)} PDF(s). Wrote {manifest_path}")
