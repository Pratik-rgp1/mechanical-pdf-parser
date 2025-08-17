import os
from pdf2image import convert_from_path

def pdf_to_images(pdf_path, output_folder):
    images = convert_from_path(pdf_path, dpi=300)
    
    for i, image in enumerate(images):
        image_path = f"{output_folder}/page_{i + 1}.png"
        image.save(image_path, 'PNG')
        print(f"Saved: {image_path}")

output_folder = "pdf_images"
pdf_path = "../data/camfoll.pdf"

os.makedirs(output_folder, exist_ok=True)

pdf_to_images(pdf_path, output_folder)
