import os
from PIL import Image

# Configuration
SOURCE_IMAGE_PATH = r"C:\Users\saahb\.gemini\antigravity\brain\07829767-2835-4ac0-9f12-62b4a283396d\xanula_icon_burgundy_v2_1765136588741.png"
DEST_DIR = r"c:\Users\saahb\OneDrive\Bureau\xanula\xanula init\static\images\icons"
THEME_COLOR = "#8B2635"

def process_icons():
    # Ensure destination directory exists
    os.makedirs(DEST_DIR, exist_ok=True)

    try:
        # Open source image
        img = Image.open(SOURCE_IMAGE_PATH)
        
        # Save 512x512
        icon_512_path = os.path.join(DEST_DIR, "icon-512x512.png")
        img = img.resize((512, 512), Image.Resampling.LANCZOS)
        img.save(icon_512_path, "PNG")
        print(f"Saved {icon_512_path}")

        # Save 192x192
        icon_192_path = os.path.join(DEST_DIR, "icon-192x192.png")
        img_192 = img.resize((192, 192), Image.Resampling.LANCZOS)
        img_192.save(icon_192_path, "PNG")
        print(f"Saved {icon_192_path}")
        
        # Create Splash Screen 640x1136
        splash = Image.new('RGB', (640, 1136), THEME_COLOR)
        # Calculate center position
        # Using the original 512 image might be too big for 640 width (mostly padding issues), let's scale it to say 256 or 300
        splash_icon_size = 300
        splash_icon = img.resize((splash_icon_size, splash_icon_size), Image.Resampling.LANCZOS)
        
        x = (640 - splash_icon_size) // 2
        y = (1136 - splash_icon_size) // 2
        
        splash.paste(splash_icon, (x, y), splash_icon if splash_icon.mode == 'RGBA' else None)
        splash_path = os.path.join(DEST_DIR, "splash-640x1136.png")
        splash.save(splash_path, "PNG")
        print(f"Saved {splash_path}")

    except Exception as e:
        print(f"Error processing icons: {e}")

if __name__ == "__main__":
    process_icons()
