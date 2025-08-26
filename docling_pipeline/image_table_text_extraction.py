import os
import json
import logging
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt
from PIL import Image

from docling.datamodel.base_models import InputFormat
from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from docling.document_converter import DocumentConverter, ImageFormatOption

logging.basicConfig(level=logging.INFO)
_log = logging.getLogger(__name__)

artifacts_path = Path(r"C:\Users\Ishwari kafle\.cache\docling\models")

doc_converter = DocumentConverter(
    allowed_formats=[InputFormat.IMAGE],
    format_options={
        InputFormat.IMAGE: ImageFormatOption(
            do_ocr=True,
            do_table_structure=True,
            accelerator_options=AcceleratorOptions(
                num_threads=4,
                device=AcceleratorDevice.AUTO
            ),
            artifacts_path=str(artifacts_path)
        )
    }
)

def display_file(file_path: str):
    """Display an image file."""
    file_extension = os.path.splitext(file_path)[1].lower()
    if file_extension in [".jpg", ".jpeg", ".png", ".bmp", ".tiff"]:
        image = Image.open(file_path)
        plt.figure(figsize=(16, 12))
        plt.imshow(image)
        plt.axis("off")
        plt.show()
    else:
        raise ValueError("Unsupported file type. Please provide an image file.")

def extract_data_with_docling(input_data_path: str, output_dir: Path):
    """
    Extracts text and tables from an image file using Docling.
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

if __name__ == "__main__":
    output_dir = Path("output")

    input_img = Path("input_docs/1.jpg")   
    display_file(str(input_img))           
    extract_data_with_docling(str(input_img), output_dir)
