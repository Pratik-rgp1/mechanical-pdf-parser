import os
import time
import json
import logging
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt
from PIL import Image
from pdf2image import convert_from_path
from PyPDF2 import PdfReader, PdfWriter

from docling.datamodel.base_models import InputFormat
from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
from docling.document_converter import DocumentConverter, PdfFormatOption, ImageFormatOption

logging.basicConfig(level=logging.INFO)
_log = logging.getLogger(__name__)

IMAGE_RESOLUTION_SCALE = 1.0  

pipeline_options = PdfPipelineOptions()
pipeline_options.do_ocr = True
pipeline_options.do_table_structure = True
pipeline_options.table_structure_options.mode = TableFormerMode.ACCURATE
pipeline_options.table_structure_options.do_cell_matching = True
pipeline_options.ocr_options.lang = ["en"] 
pipeline_options.images_scale = IMAGE_RESOLUTION_SCALE
pipeline_options.generate_page_images = True

artifacts_path = Path(r"C:\Users\Ishwari kafle\.cache\docling\models")
pipeline_options.artifacts_path = str(artifacts_path)

pipeline_options.accelerator_options = AcceleratorOptions(
    num_threads=4,
    device=AcceleratorDevice.AUTO 
)

doc_converter = DocumentConverter(
    allowed_formats=[InputFormat.PDF, InputFormat.IMAGE],
    format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
        InputFormat.IMAGE: ImageFormatOption(do_ocr=True, do_table_structure=True)
    }
)

def display_file(file_path: str):
    """Display a PDF file (page by page) or an image file."""
    file_extension = os.path.splitext(file_path)[1].lower()
    if file_extension == ".pdf":
        images = convert_from_path(file_path, poppler_path=r"C:\poppler\bin")  # set poppler path
        for i, image in enumerate(images):
            plt.figure(figsize=(16, 12))
            plt.imshow(image)
            plt.axis("off")
            plt.show()
    elif file_extension in [".jpg", ".jpeg", ".png", ".bmp", ".tiff"]:
        image = Image.open(file_path)
        plt.figure(figsize=(16, 12))
        plt.imshow(image)
        plt.axis("off")
        plt.show()
    else:
        raise ValueError("Unsupported file type. Please provide a PDF or image file.")

def extract_data_with_docling(input_data_path: str, output_dir: Path):
    """
    Extracts text and tables from a PDF or image file using Docling.
    Saves tables to CSV and document content to JSON/TXT.
    """
    result = doc_converter.convert(input_data_path)

    output_dir.mkdir(parents=True, exist_ok=True)
    doc_filename = Path(input_data_path).stem

    txt_path = output_dir / f"{doc_filename}.txt"
    with open(txt_path, "w", encoding="utf-8") as fp:
        fp.write(result.document.export_to_text())
    _log.info(f"Saved TXT: {txt_path}")

    json_path = output_dir / f"{doc_filename}.json"
    with open(json_path, "w", encoding="utf-8") as fp:
        json.dump(result.document.export_to_dict(), fp, indent=2, ensure_ascii=False)
    _log.info(f"Saved JSON: {json_path}")

    for table_ix, table in enumerate(result.document.tables):
        table_df: pd.DataFrame = table.export_to_dataframe()
        element_csv_filename = output_dir / f"{doc_filename}-table-{table_ix+1}.csv"
        table_df.to_csv(element_csv_filename, index=False)
        _log.info(f"Saved CSV table: {element_csv_filename}")

def process_pdf_pagewise(pdf_path: Path, output_dir: Path):
    pdf_reader = PdfReader(str(pdf_path))
    total_pages = len(pdf_reader.pages)
    output_dir.mkdir(parents=True, exist_ok=True)

    for page_num in range(total_pages):
        _log.info(f"Processing page {page_num+1}/{total_pages}...")

        pdf_writer = PdfWriter()
        pdf_writer.add_page(pdf_reader.pages[page_num])
        temp_page_path = output_dir / f"temp_page_{page_num+1}.pdf"
        with open(temp_page_path, "wb") as temp_f:
            pdf_writer.write(temp_f)

        start_time = time.time()
        conv_result = doc_converter.convert(temp_page_path)
        elapsed = time.time() - start_time
        _log.info(f"Page {page_num+1} processed in {elapsed:.2f} sec.")

        doc_dict = conv_result.document.export_to_dict()
        json_path = output_dir / f"page_{page_num+1}.json"
        with open(json_path, "w", encoding="utf-8") as fp:
            json.dump(doc_dict, fp, indent=2, ensure_ascii=False)

        txt_path = output_dir / f"page_{page_num+1}.txt"
        with open(txt_path, "w", encoding="utf-8") as fp:
            fp.write(conv_result.document.export_to_text())

        for table_ix, table in enumerate(conv_result.document.tables):
            table_df: pd.DataFrame = table.export_to_dataframe()
            table_path = output_dir / f"page_{page_num+1}-table-{table_ix+1}.csv"
            table_df.to_csv(table_path, index=False)

        temp_page_path.unlink(missing_ok=True)


if __name__ == "__main__":
    input_pdf = Path("../pdf-company/0008.pdf")  
    output_dir = Path("output")

    # Extract whole PDF
    extract_data_with_docling(str(input_pdf), output_dir)

    # Or pagewise extraction
    # process_pdf_pagewise(input_pdf, output_dir)

    # Example with an image
    # input_img = Path("input_docs/1.jpg")
    extract_data_with_docling(str(input_img), output_dir)
