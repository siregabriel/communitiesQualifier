from PIL import Image, ImageDraw, ImageFont
import os

# Create a simple icon with text
def create_icon(size, filename):
    # Create image with gradient background
    img = Image.new('RGB', (size, size), color='#4CAF50')
    draw = ImageDraw.Draw(img)
    
    # Add a circle
    margin = size // 8
    draw.ellipse([margin, margin, size-margin, size-margin], fill='#ffffff')
    
    # Add text
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size // 4)
    except:
        font = ImageFont.load_default()
    
    text = "CQ"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    position = ((size - text_width) // 2, (size - text_height) // 2 - size // 20)
    draw.text(position, text, fill='#4CAF50', font=font)
    
    img.save(filename)
    print(f"Created {filename}")

# Create icons
create_icon(192, 'icon-192.png')
create_icon(512, 'icon-512.png')
