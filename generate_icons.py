import os
import sys

def check_pillow():
    try:
        from PIL import Image
    except ImportError:
        print("Pillow library not found. Installing Pillow...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])

check_pillow()
from PIL import Image

def make_square_icon(src_path, dest_path, size):
    if not os.path.exists(src_path):
        print(f"Error: Source image {src_path} not found.")
        return False
    
    img = Image.open(src_path)
    
    # Standardize image mode to RGBA for transparency
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
        
    width, height = img.size
    max_side = max(width, height)
    
    # Create a square transparent background
    square_img = Image.new('RGBA', (max_side, max_side), (0, 0, 0, 0))
    
    # Center the original image inside the square background
    offset_x = (max_side - width) // 2
    offset_y = (max_side - height) // 2
    square_img.paste(img, (offset_x, offset_y), img)
    
    # Resize to required standard
    resized_img = square_img.resize((size, size), Image.Resampling.LANCZOS)
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    
    # Save the output
    resized_img.save(dest_path, 'PNG')
    print(f"  Generated: {dest_path} ({size}x{size})")
    return True

if __name__ == '__main__':
    logo_path = os.path.join('static', 'logo.png')
    
    if not os.path.exists(logo_path):
        print(f"Error: {logo_path} not found!")
        sys.exit(1)
    
    # --- PWA Icons ---
    print("\n[PWA] Generating PWA Icons...")
    make_square_icon(logo_path, os.path.join('static', 'icon-192.png'), 192)
    make_square_icon(logo_path, os.path.join('static', 'icon-512.png'), 512)
    
    # --- Android App Icons (mipmap) ---
    print("\n[Android] Generating Android App Icons...")
    android_base = os.path.join('android-app', 'app', 'src', 'main', 'res')
    
    # Android mipmap size specifications
    android_icons = {
        'mipmap-mdpi':    48,
        'mipmap-hdpi':    72,
        'mipmap-xhdpi':   96,
        'mipmap-xxhdpi':  144,
        'mipmap-xxxhdpi': 192,
    }
    
    for folder, size in android_icons.items():
        dest = os.path.join(android_base, folder, 'ic_launcher.png')
        make_square_icon(logo_path, dest, size)
    
    print("\n[OK] All icons generated successfully!")
    print("   PWA:     static/icon-192.png, static/icon-512.png")
    print("   Android: android-app/app/src/main/res/mipmap-*/ic_launcher.png")
