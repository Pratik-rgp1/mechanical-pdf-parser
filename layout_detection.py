from PIL import Image
import torch
from transformers import RTDetrImageProcessor, RTDetrForObjectDetection
import cv2
import numpy as np

processor = RTDetrImageProcessor.from_pretrained("HuggingPanda/docling-layout")
model = RTDetrForObjectDetection.from_pretrained("HuggingPanda/docling-layout")

image_path = "pdf_images/page_17.png"
image_pil = Image.open(image_path).convert("RGB")
inputs = processor(images=image_pil, return_tensors="pt", size={"height": 640, "width": 640})

with torch.no_grad():
    outputs = model(**inputs)

results = processor.post_process_object_detection(
    outputs,
    target_sizes=torch.tensor([image_pil.size[::-1]]),
    threshold=0.3,
)

image_cv = cv2.cvtColor(np.array(image_pil), cv2.COLOR_RGB2BGR)

for result in results:
    for score, label_id, box in zip(result["scores"], result["labels"], result["boxes"]):
        x1, y1, x2, y2 = map(int, box.tolist())
        label = model.config.id2label[label_id.item() + 1]  # note +1 offset
        cv2.rectangle(image_cv, (x1, y1), (x2, y2), (0, 255, 0), 2)
        text = f"{label} {score:.2f}"
        cv2.putText(image_cv, text, (x1, max(0, y1 - 5)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1, cv2.LINE_AA)

max_display_width = 1000
max_display_height = 800
h, w = image_cv.shape[:2]
scale = min(max_display_width / w, max_display_height / h)
display_img = cv2.resize(image_cv, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

cv2.imshow("Layout Detection", display_img)
cv2.waitKey(0)
cv2.destroyAllWindows()

cv2.imwrite("detected_page.png", image_cv)
