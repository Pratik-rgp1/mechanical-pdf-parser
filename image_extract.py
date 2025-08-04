import fitz  # PyMuPDF
import os
import json
from PIL import Image, ImageDraw, ImageFont
import io

LABEL_DISTANCE_THRESHOLD = 50  # Distance threshold for text-label proximity
HEADER_RATIO = 0.10  # Top 10% of page considered as header
FOOTER_RATIO = 0.15  # Bottom 15% of page considered as footer

def is_potential_diagram(shapes):
    """
    Determines if a group of vector shapes resembles a technical diagram.
    Filters out large horizontal banners and line-heavy blocks with minimal curves.
    """
    lines = [s for s in shapes if s['type'] == 'line']
    rects = [s for s in shapes if s['type'] == 'rect']
    curves = [s for s in shapes if s['type'] == 'curve']

    if len(lines) > 20 and len(rects) > 10 and len(curves) < 2:
        return False

    if shapes and 'bbox' in shapes[0]:
        try:
            bbox = fitz.Rect(shapes[0]['bbox'])
            if bbox.width > 400 and bbox.height < 150:
                return False
        except Exception:
            pass

    if len(curves) >= 3:
        return True

    return len(lines) + len(rects) + len(curves) > 5

def rect_distance(rect1, rect2):
    """
    Calculates Euclidean distance between two rectangles.
    Returns 0 if they intersect.
    """
    if rect1.intersects(rect2):
        return 0
    dx = max(rect2.x0 - rect1.x1, rect1.x0 - rect2.x1, 0)
    dy = max(rect2.y0 - rect1.y1, rect1.y0 - rect2.y1, 0)
    return (dx**2 + dy**2)**0.5

def merge_rects(rects, threshold=30):
    """
    Merges nearby or overlapping rectangles within a given distance threshold.
    """
    merged = []
    for rect in rects:
        added = False
        for i, m in enumerate(merged):
            if rect.intersects(m) or rect_distance(rect, m) < threshold:
                merged[i] = m | rect
                added = True
                break
        if not added:
            merged.append(rect)
    return merged

def is_in_header_or_footer(rect, page_height):
    """
    Checks if a rectangle lies within the header or footer region.
    """
    return rect.y0 < HEADER_RATIO * page_height or rect.y1 > (1 - FOOTER_RATIO) * page_height

def extract_diagram_regions_from_page(page):
    """
    Extracts candidate diagram regions from vector graphics on a page.
    """
    shapes = page.get_drawings()
    diagram_candidates = []
    page_height = page.rect.height

    for shape in shapes:
        bbox = fitz.Rect(shape["rect"])
        items = shape["items"]
        if not items:
            continue

        components = []
        for item in items:
            kind = item[0]
            if kind == "l":
                components.append({'type': 'line', 'bbox': item[1]})
            elif kind == "re":
                components.append({'type': 'rect', 'bbox': item[1]})
            elif kind == "c":
                components.append({'type': 'curve', 'bbox': item[1]})

        if is_potential_diagram(components) and not is_in_header_or_footer(bbox, page_height):
            diagram_candidates.append(bbox)

    return diagram_candidates

def extract_image_diagram_regions(page, min_width=80, min_height=80):
    """
    Extracts bounding boxes of embedded image diagrams that meet minimum size criteria.
    """
    image_regions = []
    blocks = page.get_text("dict")["blocks"]
    page_height = page.rect.height

    for b in blocks:
        if b.get("type") == 1:
            bbox = fitz.Rect(b["bbox"])
            if bbox.width >= min_width and bbox.height >= min_height and not is_in_header_or_footer(bbox, page_height):
                image_regions.append(bbox)
    return image_regions

def extract_labels_with_positions(page, diagram_rect):
    """
    Identifies nearby or internal text labels to annotate each diagram region.
    """
    labels = []
    blocks = page.get_text("dict")["blocks"]
    for b in blocks:
        if "lines" not in b:
            continue
        for line in b["lines"]:
            for span in line["spans"]:
                text = span["text"].strip()
                if not text or len(text) < 2 or len(text) > 20:
                    continue
                if any(x in text.upper() for x in ["THK", "TABLE", "DIM", "NOTE", "CFS", "CF", "NUCF"]):
                    continue

                bbox = fitz.Rect(span["bbox"])
                center = bbox.tl + (bbox.br - bbox.tl) * 0.5
                if diagram_rect.contains(center) or rect_distance(diagram_rect, bbox) < LABEL_DISTANCE_THRESHOLD:
                    labels.append({"text": text, "bbox": bbox})
    return labels

def save_diagram_from_pdf(pdf_path, output_dir, dpi=300, output_json_dir="output_json"):
    """
    Extracts and saves diagram regions as labeled PNG images.
    Skips pages containing tables, branding, or invalid regions.
    """
    os.makedirs(output_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    zoom = dpi / 72
    mat = fitz.Matrix(zoom, zoom)

    for page_number, page in enumerate(doc, start=1):
        print(f" Processing page {page_number}...")

        if page_number in {1, 45}:
            print(f" Skipping page {page_number} (branding only).")
            continue

        json_path = os.path.join(output_json_dir, f"page_{page_number}.json")
        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    page_data = json.load(f)
                    if "tables" in page_data and page_data["tables"]:
                        print(f" Skipping page {page_number} (contains tables).")
                        continue
            except Exception as e:
                print(f"JSON load failed on page {page_number}: {e}")

        vector_diagrams = extract_diagram_regions_from_page(page)
        image_diagrams = extract_image_diagram_regions(page)

        all_diagrams = merge_rects(vector_diagrams + image_diagrams, threshold=40)
        if not all_diagrams:
            print(" No diagrams found.")
            continue

        for idx, rect in enumerate(all_diagrams):
            if rect.width <= 0 or rect.height <= 0:
                print(f" Skipping invalid rect on page {page_number}.")
                continue
            if not page.rect.contains(rect.tl) and not page.rect.contains(rect.br):
                print(f" Skipping rect outside page bounds on page {page_number}.")
                continue

            try:
                pix = page.get_pixmap(matrix=mat, clip=rect, alpha=False)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
            except Exception as e:
                print(f"❌ Rendering failed on page {page_number}, region {idx+1}: {e}")
                continue

            labels = extract_labels_with_positions(page, rect)
            draw = ImageDraw.Draw(img)
            try:
                font = ImageFont.truetype("arial.ttf", size=12)
            except IOError:
                font = ImageFont.load_default()

            for label in labels:
                bbox = label['bbox']
                x = (bbox.x0 - rect.x0) * zoom
                y = (bbox.y0 - rect.y0) * zoom
                draw.text((x, y), label['text'], fill="red", font=font)

            image_name = f"page{page_number}_diagram{idx+1}.png"
            out_path = os.path.join(output_dir, image_name)
            img.save(out_path)
            print(f"✅ Saved: {out_path}")

            metadata = {
                "file": image_name,
                "labels": [l['text'] for l in labels],
                "page": page_number,
                "bbox": [rect.x0, rect.y0, rect.x1, rect.y1],
                "type": "merged"
            }
            with open(out_path.replace(".png", ".json"), "w") as f:
                json.dump(metadata, f, indent=2)

if __name__ == "__main__":
    save_diagram_from_pdf(
        pdf_path="data/camfoll.pdf",
        output_dir="extracted_demo1",
        output_json_dir="output_json"
    )
