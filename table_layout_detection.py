import time
from pathlib import Path
import cv2
import numpy as np
import fitz
from PIL import Image
import torch
from transformers import RTDetrImageProcessor, RTDetrForObjectDetection


class TableDetector:
    def __init__(self, thr: float = 0.23, dpi: int = 450, expand: int = 10):
        """
        Table detector to crop and save only inner tables,
        excluding the large parent table that contains smaller tables.
        """
        self.processor = RTDetrImageProcessor.from_pretrained("HuggingPanda/docling-layout")
        self.model = RTDetrForObjectDetection.from_pretrained("HuggingPanda/docling-layout")
        self.model.eval()
        self.id2label = self.model.config.id2label

        self.thr = thr
        self.dpi = dpi
        self.expand = expand

    def _render_pdf(self, pdf_path: Path):
        """Render PDF pages at high resolution for better detection of small tables."""
        doc = fitz.open(pdf_path)
        zoom = self.dpi / 72.0
        pages = []

        for i in range(len(doc)):
            page = doc.load_page(i)
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            pages.append(img)
        doc.close()
        return pages

    @torch.no_grad()
    def _detect_tables(self, img: Image.Image):
        """Run table detection using RTDetr model."""
        inputs = self.processor(images=img, return_tensors="pt")
        outputs = self.model(**inputs)

        results = self.processor.post_process_object_detection(
            outputs,
            target_sizes=torch.tensor([[img.height, img.width]]),
            threshold=self.thr,
        )

        detections = []
        for res in results:
            for s, lid, box in zip(res["scores"], res["labels"], res["boxes"]):
                label = self.id2label.get(int(lid.item()) + 1, "").lower()
                if "table" not in label:
                    continue
                x1, y1, x2, y2 = map(int, box.tolist())
                detections.append((x1, y1, x2, y2, float(s)))
        return detections

    def _filter_outer_tables(self, detections, iou_threshold=0.8):
        """
        Remove the large parent table that completely contains smaller tables.
        Keeps only inner tables.
        """
        filtered = []
        n = len(detections)

        # Compare every pair of tables
        for i in range(n):
            x1_a, y1_a, x2_a, y2_a, score_a = detections[i]
            area_a = (x2_a - x1_a) * (y2_a - y1_a)
            is_outer = False

            for j in range(n):
                if i == j:
                    continue
                x1_b, y1_b, x2_b, y2_b, score_b = detections[j]

                # Check if A fully contains B (B is inside A)
                if x1_a <= x1_b and y1_a <= y1_b and x2_a >= x2_b and y2_a >= y2_b:
                    is_outer = True
                    break

            if not is_outer:
                filtered.append(detections[i])

        return filtered

    def _save_debug_image(self, pil_img: Image.Image, detections, out_path: Path):
        """Save debug image with bounding boxes drawn around detected tables."""
        image_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

        for (x1, y1, x2, y2, score) in detections:
            cv2.rectangle(image_bgr, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(image_bgr, f"{score:.2f}", (x1, max(0, y1 - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        cv2.imwrite(str(out_path), image_bgr)

    def process_pdf(self, pdf_path: Path, outdir: Path):
        """
        Detect tables and save:
        - ONLY inner tables (small tables inside the larger one).
        - Debug images with bounding boxes in a separate folder.
        """
        outdir.mkdir(parents=True, exist_ok=True)
        crops_dir = outdir / "crops"
        debug_dir = outdir / "debug"
        crops_dir.mkdir(exist_ok=True)
        debug_dir.mkdir(exist_ok=True)

        pdf_name = pdf_path.stem
        pages = self._render_pdf(pdf_path)

        for pidx, pil_img in enumerate(pages, start=1):
            t0 = time.time()
            detections = self._detect_tables(pil_img)
            W, H = pil_img.size

            # Filter to keep only inner tables (exclude the outer big table)
            detections = self._filter_outer_tables(detections)

            # Save each inner table crop
            for tidx, (x1, y1, x2, y2, score) in enumerate(detections, start=1):
                # Add padding for clean crop
                x1, y1 = max(0, x1 - self.expand), max(0, y1 - self.expand)
                x2, y2 = min(W, x2 + self.expand), min(H, y2 + self.expand)

                crop = pil_img.crop((x1, y1, x2, y2))
                crop_path = crops_dir / f"{pdf_name}_page{pidx:04d}_table{tidx:02d}.png"
                crop.save(crop_path)

            # Save debug overlay
            debug_path = debug_dir / f"{pdf_name}_page{pidx:04d}_debug.png"
            self._save_debug_image(pil_img, detections, debug_path)

            print(f"[INFO] {pdf_name} - Page {pidx}: {len(detections)} inner tables saved in {time.time()-t0:.2f}s")


if __name__ == "__main__":
    pdf_path = Path("../pdf-company/p2_241_001.pdf")  # Input PDF
    out_dir = Path("demo_tables_crops")              # Output folder

    detector = TableDetector(thr=0.23, dpi=450, expand=10)
    detector.process_pdf(pdf_path, out_dir)
