import os
from typing import List, Dict, Any, Tuple, Optional
from pydantic import BaseModel
from parser.layout_detector import LayoutBlock

class ImageMetadata(BaseModel):
    image_idx: int
    page_number: int
    bbox: Tuple[float, float, float, float]
    image_path: Optional[str] = None
    caption_text: Optional[str] = None

class ImageExtractor:
    def __init__(self, filepath: str, output_dir: str):
        self.filepath = filepath
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def extract_images(self, doc_fitz, layout_blocks: List[LayoutBlock]) -> List[ImageMetadata]:
        """
        Extracts images from the document using PyMuPDF and associates
        nearby caption blocks based on distance.
        """
        images = []
        image_idx = 1

        # We also classify caption blocks
        caption_blocks = [b for b in layout_blocks if b.block_type == "Caption"]

        for page_idx, page in enumerate(doc_fitz):
            page_num = page_idx + 1
            
            # 1. Check for raster images
            pymupdf_images = page.get_images(full=True)
            for img_info in pymupdf_images:
                xref = img_info[0]
                # Try to get image bbox
                rects = page.get_image_rects(xref)
                bbox = rects[0] if rects else page.rect  # default to page boundary if not found
                
                # Save image file
                try:
                    base_image = doc_fitz.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]
                    image_filename = f"img_p{page_num}_{image_idx}.{image_ext}"
                    image_path = os.path.join(self.output_dir, image_filename)
                    
                    with open(image_path, "wb") as img_file:
                        img_file.write(image_bytes)
                except Exception:
                    image_path = None

                # Find nearest caption
                caption = self._find_nearest_caption(bbox, caption_blocks, page_num)

                images.append(
                    ImageMetadata(
                        image_idx=image_idx,
                        page_number=page_num,
                        bbox=(bbox.x0, bbox.y0, bbox.x1, bbox.y1),
                        image_path=image_path,
                        caption_text=caption
                    )
                )
                image_idx += 1

            # 2. Check for vector graphics / drawings if no raster images
            # (Sometimes technical figures are PDF vector diagrams, not JPEGs)
            if not pymupdf_images:
                drawings = page.get_drawings()
                if drawings:
                    # If drawings cover a significant portion, we could treat it as a figure.
                    # For simplicity, we just log that we checked vector elements.
                    pass

        return images

    def _find_nearest_caption(
        self,
        img_bbox: Any,
        captions: List[LayoutBlock],
        page_number: int
    ) -> Optional[str]:
        """Finds a caption block on the same page that is closest to the image vertically."""
        page_captions = [c for c in captions if c.page_number == page_number]
        if not page_captions:
            return None

        # Distance calculation: we want the caption closest to the image bbox.
        # Captions are typically below or above the image.
        closest_caption = None
        min_dist = float("inf")
        iy0, iy1 = img_bbox[1], img_bbox[3]

        for c in page_captions:
            cy0, cy1 = c.bbox[1], c.bbox[3]
            
            # Calculate vertical distance
            dist_below = abs(cy0 - iy1)  # Caption below image
            dist_above = abs(iy0 - cy1)  # Caption above image
            dist = min(dist_below, dist_above)

            if dist < min_dist and dist < 50.0:  # within 50 points
                min_dist = dist
                closest_caption = c.text

        return closest_caption
