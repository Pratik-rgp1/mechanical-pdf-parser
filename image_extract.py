import fitz  # PyMuPDF
import os
import json
from PIL import Image, ImageDraw, ImageFont
import io

LABEL_DISTANCE_THRESHOLD = 50  # points

def is_potential_diagram(shapes):
    lines = [s for s in shapes if s['type'] == 'line']
    rects = [s for s in shapes if s['type'] == 'rect']
    curves = [s for s in shapes if s['type'] == 'curve']

    if len(lines) + len(rects) + len(curves) > 5:
        return True
    return False

def rect_distance(rect1, rect2):
    if rect1.intersects(rect2):
        return 0
    dx = max(rect2.x0 - rect1.x1, rect1.x0 - rect2.x1, 0)
    dy = max(rect2.y0 - rect1.y1, rect1.y0 - rect2.y1, 0)
    return (dx*2 + dy)*0.5  # <-- fixed here

def merge_rects(rects, threshold=15):
    merged = []
    for rect in rects:
        added = False
        for i, m in enumerate(merged):
            if rect.intersects(m) or rect_distance(rect, m) < threshold:
                merged[i] = m | rect  # union
                added = True
                break
        if not added:
            merged.append(rect)
    return merged

def filter_diagrams_by_size(diagrams, min_area_ratio=0.5):
    if not diagrams:
        return []

    diagrams = sorted(diagrams, key=lambda r: r.get_area(), reverse=True)
    largest_area = diagrams[0].get_area()

    filtered = []
    for rect in diagrams:
        area = rect.get_area()
        if area >= largest_area * min_area_ratio:
            filtered.append(rect)
        else:
            inside = any(other.contains(rect) for other in filtered)
            if not inside:
                filtered.append(rect)
    return filtered

def extract_diagram_regions_from_page(page):
    shapes = page.get_drawings()
    diagram_candidates = []

    for shape in shapes:
        bbox = shape["rect"]
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

        if is_potential_diagram(components):
            diagram_candidates.append(fitz.Rect(bbox))

    merged_diagrams = merge_rects(diagram_candidates, threshold=15)
    return merged_diagrams

def extract_image_diagram_regions(page, min_width=100, min_height=100):
    image_regions = []
    images = page.get_images(full=True)
    blocks = page.get_text("dict")["blocks"]

    for img in images:
        xref = img[0]
        for b in blocks:
            if b.get("type") == 1 and b.get("image") == xref:
                bbox = fitz.Rect(b["bbox"])
                if bbox.width >= min_width and bbox.height >= min_height:
                    image_regions.append(bbox)
    return image_regions

def extract_labels_with_positions(page, diagram_rect):
    labels = []

    blocks = page.get_text("dict")["blocks"]
    for b in blocks:
        if "lines" not in b:
            continue
        for line in b["lines"]:
            for span in line["spans"]:
                text = span["text"].strip()
                if not text:
                    continue
                bbox = fitz.Rect(span["bbox"])
                center = bbox.tl + (bbox.br - bbox.tl) * 0.5

                if diagram_rect.contains(center) or rect_distance(diagram_rect, bbox) < LABEL_DISTANCE_THRESHOLD:
                    if len(text) < 20:
                        labels.append({"text": text, "bbox": bbox})

    return labels

def save_diagram_from_pdf(pdf_path, output_dir, dpi=300):
    os.makedirs(output_dir, exist_ok=True)
    doc = fitz.open(pdf_path)

    zoom = dpi / 72
    mat = fitz.Matrix(zoom, zoom)

    for page_number, page in enumerate(doc, start=1):
        print(f"Processing page {page_number}")

        vector_diagrams = extract_diagram_regions_from_page(page)
        image_diagrams = extract_image_diagram_regions(page)

        all_diagrams = vector_diagrams + image_diagrams
        all_diagrams = merge_rects(all_diagrams, threshold=15)
        all_diagrams = filter_diagrams_by_size(all_diagrams, min_area_ratio=0.5)

        if not all_diagrams:
            print("No diagrams found on this page.")
            continue

        for idx, rect in enumerate(all_diagrams):
            pix = page.get_pixmap(matrix=mat, clip=rect, alpha=False)
            img = Image.open(io.BytesIO(pix.tobytes("png")))

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
            print(f"Saved: {out_path}")

            metadata = {
                "file": image_name,
                "labels": [l['text'] for l in labels],
                "page": page_number,
                "bbox": [rect.x0, rect.y0, rect.x1, rect.y1]
            }
            with open(out_path.replace(".png", ".json"), "w") as f:
                json.dump(metadata, f, indent=2)

if __name__ == "__main__":
    pdf_file = "data/camfoll.pdf"
    output_folder = "extracted_diagrams"
    save_diagram_from_pdf(pdf_file, output_folder)
