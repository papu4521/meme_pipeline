import textwrap
from PIL import Image, ImageDraw, ImageFont

class MemeCompositor:
    def add_text_to_image(self, image_path: str, text: str) -> Image.Image:
        """
        Overlays meme text onto an image and returns a PIL Image object.
        """
        img = Image.open(image_path).convert("RGBA")
        draw = ImageDraw.Draw(img)
        width, height = img.size
        
        # Determine font size based on image width
        font_size = 40 if width >= 400 else 24
        
        try:
            # Standard Windows font
            font = ImageFont.truetype("arial.ttf", font_size)
        except Exception:
            try:
                # Pillow 10.1+ supports size for default font
                font = ImageFont.load_default(size=font_size)
            except Exception:
                font = ImageFont.load_default()
        
        # Word wrap text at 30 chars
        lines = textwrap.wrap(text, width=30)
        
        # Calculate line heights and total text block height
        line_heights = []
        for line in lines:
            try:
                bbox = font.getbbox(line)
                line_heights.append(bbox[3] - bbox[1])
            except Exception:
                line_heights.append(font_size)
                
        line_spacing = 10
        total_text_height = sum(line_heights) + (line_spacing * max(0, len(lines) - 1))
        
        # Add semi-transparent black bar at the bottom
        bar_height = total_text_height + 40  # 20px padding top and bottom of text
        bar_y_start = height - bar_height
        
        # Create a semi-transparent overlay
        overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.rectangle(
            [(0, bar_y_start), (width, height)],
            fill=(0, 0, 0, 160)  # Semi-transparent black
        )
        img = Image.alpha_composite(img, overlay)
        draw = ImageDraw.Draw(img)
        
        # Draw the text, bottom-aligned with 20px padding from bottom
        y = height - 20 - total_text_height
        
        for i, line in enumerate(lines):
            try:
                bbox = font.getbbox(line)
                line_width = bbox[2] - bbox[0]
            except Exception:
                try:
                    line_width = font.getlength(line)
                except Exception:
                    line_width = len(line) * (font_size * 0.6)
                    
            x = (width - line_width) / 2
            
            # White fill
            draw.text((x, y), line, font=font, fill="white")
            
            y += line_heights[i] + line_spacing
            
        return img.convert("RGB")
