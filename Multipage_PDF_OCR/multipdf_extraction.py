
import os
os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"
from paddleocr import PaddleOCR
import multiprocessing as mp
import pymupdf
import os
import shutil
import gc

def extract_page(path):
    num=int(path[::-1][4:path[::-1].index("e")][::-1])
    ocr = PaddleOCR(use_angle_cls=True, lang='en', enable_mkldnn=False)
    result = ocr.predict(path)
    texts = []
    for item in result:
        texts.extend(item.get('rec_texts', []))
    del result
    gc.collect()
    return {"pagenum":num, "text":texts}


if __name__ == "__main__":
    dirpath=input("Path to folder containing PDFs: ")
    dump_dir = dirpath[::-1][dirpath[::-1].index("/"):][::-1]+"pic_dump"
    output_dir = dirpath[::-1][dirpath[::-1].index("/"):][::-1]+"output"
    res=input(str(output_dir)+" okay for output files? Y for yes, otherwise specify new directory path. ")
    if res=="Y" or res=="y":
        pass
    else:
        output_dir=res
    res=input(str(dump_dir)+" okay for temporary file storage? Y for yes, otherwise specify new directory path. ")
    if res=="Y" or res=="y":
        pass
    else:
        dump_dir=res
    for j in os.listdir(dirpath):
        os.makedirs(dump_dir, exist_ok=True)
        document = pymupdf.open(dirpath+"/"+j)
        os.makedirs(output_dir, exist_ok=True)
        for i, page in enumerate(document):
            img = page.get_pixmap(dpi=85) #Can increase/lower DPI value for better accuracy/speed respectively
            img.save(f"{dump_dir}/page{i}.png")
        document.close()

        inpaths = [os.path.join(dump_dir, f) for f in os.listdir(dump_dir) if f.endswith(".png")]
        #print(inpaths)
    
        with mp.Pool(processes=min(4, os.cpu_count())) as pool:
            output = pool.map(extract_page, inpaths)
    
    
        output.sort(key=lambda x: x["pagenum"])
        with open(output_dir+"/"+j[:-4]+"_output.txt", "w") as f:
            f.write(str(output))
        shutil.rmtree(dump_dir)
        

