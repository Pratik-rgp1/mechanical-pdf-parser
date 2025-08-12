import os
import re
import json
import pdfplumber

class PDFExtractor:
    def __init__(self, pdf_path, output_dir="output_json"):
        self.pdf_path = pdf_path
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def clean_text(self, text):
        if not text:
            return ""
        text = text.replace("\u2013", "-").replace("\u2014", "-")
        text = re.sub(r"[^\x20-\x7E\n\t]", "", text)
        text = re.sub(r"(\d{2})(?=\d{2}\b)", r"\1–", text)
        lines = [
            line.strip() for line in text.splitlines()
            if not re.search(r"514-1E|A%PXOMPB|CCaammFFoollllo|@\$%", line)
        ]
        return "\n".join(lines).strip()

    def is_valid_table(self, table, char_thresh=30):
        if not table or len(table) < 2:
            return False
        col_counts = [len(row) for row in table if row]
        if len(col_counts) < 2 or min(col_counts) < 2:
            return False
        total_chars = sum(len(str(cell)) for row in table for cell in row if cell)
        return total_chars >= char_thresh

    def clean_table(self, table):
        def clean_cell(cell):
            if not cell:
                return ""
            cell = str(cell)
            cell = cell.replace("", "⌀").replace("\n", " ").replace("\r", " ")
            cell = re.sub(r"\s+", " ", cell).strip()
            cell = re.sub(r"(\d)\s*\.\s*(\d)", r"\1.\2", cell)
            return cell
        return [[clean_cell(cell) for cell in row] for row in table]

    def extract(self):
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    result = {"page_number": i + 1}
                    output_file = os.path.join(self.output_dir, f"page_{i + 1}.json")
                    
                    raw_text = page.extract_text()
                    cleaned_text = self.clean_text(raw_text)
                    if cleaned_text:
                        result["text"] = cleaned_text

                    raw_tables = page.extract_tables()
                    valid_tables = [self.clean_table(t) for t in raw_tables if self.is_valid_table(t)]
                    if valid_tables:
                        result["tables"] = valid_tables

                    if not result.get("text") and not result.get("tables"):
                        continue

                    with open(output_file, "w", encoding="utf-8") as f:
                        json.dump(result, f, ensure_ascii=False, indent=2)

                    print(f"Saved: {output_file}")
        except Exception as e:
            print(f"ERROR: Failed to process PDF: {e}")

if __name__ == "__main__":
    extractor = PDFExtractor("data/camfoll.pdf", "output_json")
    extractor.extract()
