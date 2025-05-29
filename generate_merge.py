# generate_merge.py

import os
import time
from PyPDF2 import PdfMerger

MERGE_DONE_FILE = "done_merge.txt"
UPLOAD_ROOT = "pdf_data"

def merge_pdfs(pdf_paths, output_path):
    print(f"[INFO] Merging PDFs to {output_path}")
    if not pdf_paths:
        print("[WARN] No PDF files found to merge.")
        return
    merger = PdfMerger()
    for path in pdf_paths:
        merger.append(path)
    merger.write(output_path)
    merger.close()

def process_folder(folder):
    folder_path = os.path.join(UPLOAD_ROOT, folder)
    pdf_folder = os.path.join(folder_path, "pdf")
    merged_output_path = os.path.join(folder_path, "merged.pdf")

    if not os.path.exists(pdf_folder):
        print(f"[SKIP] No pdf folder found in {folder}")
        return

    # Get list of .pdf files
    pdf_files = [os.path.join(pdf_folder, f) for f in os.listdir(pdf_folder) if f.endswith(".pdf")]
    if not pdf_files:
        print(f"[SKIP] No PDF files found in {pdf_folder}")
        return

    merge_pdfs(pdf_files, merged_output_path)
    print(f"[SUCCESS] Merged PDF saved in {merged_output_path}")

if __name__ == "__main__":
    print("[START] Starting PDF Merge Processor...")

    while True:
        print("[PROCESSING] Scanning folders for PDF merge...")
        if not os.path.exists(MERGE_DONE_FILE):
            open(MERGE_DONE_FILE, 'w').close()

        with open(MERGE_DONE_FILE, "r") as f:
            done_folders = [line.strip() for line in f.readlines()]

        folders = os.listdir(UPLOAD_ROOT)

        for folder in folders:
            if folder not in done_folders:
                process_folder(folder)
                with open(MERGE_DONE_FILE, "a") as f:
                    f.write(folder + "\n")

        time.sleep(4)
