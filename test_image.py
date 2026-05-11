from image_service import generate_image
import os

print("Testing image generation...")

try:
    path = generate_image(
        prompt="a cute cat playing in the rain, colorful children book style",
        output_path="static/test_image.png"
    )
    print(f"Image saved at: {path}")
    print(f"File size: {os.path.getsize(path)} bytes")
    print("Image generation works!")

except Exception as e:
    print(f"Image generation failed: {e}")