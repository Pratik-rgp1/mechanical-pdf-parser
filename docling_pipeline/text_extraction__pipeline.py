import os
import time
import logging
import pdfplumber
from pathlib import Path
from PyPDF2 import PdfReader, PdfWriter
from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

logging.basicConfig(level=logging.INFO)
_log = logging.getLogger(__name__)

pipeline_options = PdfPipelineOptions()
pipeline_options.do_ocr = True
pipeline_options.do_table_structure = True
pipeline_options.table_structure_options.do_cell_matching = True
pipeline_options.ocr_options.lang = ["es"]
pipeline_options.accelerator_options = AcceleratorOptions(
    num_threads=4, device=AcceleratorDevice.AUTO
)

doc_converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
    }
)

def process_page(pdf_path: Path):
    return doc_converter.convert(pdf_path)

def process_pdf_pagewise(pdf_path: Path, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
    pdf_reader = PdfReader(str(pdf_path))
    for page_num in range(total_pages):
        _log.info(f"Processing page {page_num + 1}...")
        pdf_writer = PdfWriter()
        pdf_writer.add_page(pdf_reader.pages[page_num])
        temp_page_path = output_dir / f"temp_page_{page_num + 1}.pdf"
        with open(temp_page_path, "wb") as temp_f:
            pdf_writer.write(temp_f)
        start_time = time.time()
        conv_result = process_page(temp_page_path)
        elapsed = time.time() - start_time
        _log.info(f"Page {page_num + 1} processed in {elapsed:.2f} sec.")
        txt_path = output_dir / f"page_{page_num + 1}.txt"
        with open(txt_path, "w", encoding="utf-8") as fp:
            fp.write(conv_result.document.export_to_text())
        _log.info(f"Saved: {txt_path}")
        temp_page_path.unlink(missing_ok=True)

if __name__ == "__main__":
    input_pdf = Path("../data/camfoll.pdf")
    output_dir = Path("output_text_pages")
    process_pdf_pagewise(input_pdf, output_dir)