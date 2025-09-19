import fitz 
import cv2
import numpy as np
from pathlib import Path
import shutil


class PDFPagePairMerger:
    def __init__(self, pdf_path: Path, output_dir: Path, dpi: int = 300):
        self.pdf_path = pdf_path
        self.output_dir = output_dir
        self.page_dir = self.output_dir / "page_images"     
        self.merged_dir = self.output_dir / "merged_pages"   

        self.page_dir.mkdir(parents=True, exist_ok=True)
        self.merged_dir.mkdir(parents=True, exist_ok=True)
        self.dpi = dpi

    def pdf_to_images(self):
        print("[INFO] Rendering PDF pages to images...")
        doc = fitz.open(self.pdf_path)
        for i, page in enumerate(doc, start=1):
            zoom = self.dpi / 72
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            output_path = self.page_dir / f"page_{i:04d}.png"
            pix.save(output_path)
            print(f"[INFO] Saved page image: {output_path.name}")
        doc.close()

    def merge_two_pages(self, img1_path: Path, img2_path: Path, output_path: Path):
        """Merge two full-page images horizontally and save the result."""
        img1 = cv2.imread(str(img1_path))
        img2 = cv2.imread(str(img2_path))

        if img1 is None or img2 is None:
            raise ValueError(f"[ERROR] Could not read images: {img1_path}, {img2_path}")

        # Resize to match heights
        h = min(img1.shape[0], img2.shape[0])
        img1_resized = cv2.resize(img1, (int(img1.shape[1] * h / img1.shape[0]), h))
        img2_resized = cv2.resize(img2, (int(img2.shape[1] * h / img2.shape[0]), h))

        merged = np.hstack((img1_resized, img2_resized))
        cv2.imwrite(str(output_path), merged)
        print(f"[INFO] Merged pages → {output_path.name}")

    def merge_pages_pairwise_after_first(self):
        page_files = sorted(self.page_dir.glob("*.png"))

        if not page_files:
            print("[ERROR] No page images found for processing.")
            return

        # Save first page solo
        first_page = page_files[0]
        first_page_output = self.merged_dir / first_page.name
        cv2.imwrite(str(first_page_output), cv2.imread(str(first_page)))
        print(f"[INFO] Saved first page solo: {first_page_output.name}")

        if len(page_files) == 1:
            print("[INFO] Only one page in PDF. Nothing to merge further.")
            return

        # Pages to merge (excluding first page)
        pages_to_merge = page_files[1:]

        # Merge in pairs
        for i in range(0, len(pages_to_merge) - 1, 2):
            page1 = pages_to_merge[i]
            page2 = pages_to_merge[i + 1]
            merged_name = f"merged_{page1.stem}_{page2.stem}.png"
            merged_path = self.merged_dir / merged_name
            self.merge_two_pages(page1, page2, merged_path)

        # If odd number of pages last page stays solo
        if len(pages_to_merge) % 2 != 0:
            last_page = pages_to_merge[-1]
            last_page_output = self.merged_dir / last_page.name
            cv2.imwrite(str(last_page_output), cv2.imread(str(last_page)))
            print(f"[INFO] Saved last unpaired page solo → {last_page_output.name}")

    def cleanup_temp_images(self):
        if self.page_dir.exists():
            shutil.rmtree(self.page_dir)
            print(f"[INFO] Deleted temporary folder: {self.page_dir}")

    def run(self):
        self.pdf_to_images()
        self.merge_pages_pairwise_after_first()
        self.cleanup_temp_images()
        print("[INFO] Processing complete! Final merged images are in:", self.merged_dir)

short 
if __name__ == "__main__":
    PDF_PATH = Path("../pdf-company/[THK_En] LMGuide 2.pdf")
    OUTPUT_DIR = Path("processed_output")

    merger = PDFPagePairMerger(pdf_path=PDF_PATH, output_dir=OUTPUT_DIR)
    merger.run()
