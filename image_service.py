from huggingface_hub import InferenceClient
import os
from dotenv import load_dotenv

load_dotenv()

client = InferenceClient(
    provider="auto",
    api_key=os.getenv("HF_API_KEY")
)


def generate_image(prompt: str, output_path: str) -> str:
    """
    Takes a prompt → generates image → saves it → returns path
    """
    full_prompt = (
        f"children book illustration, colorful, cute, "
        f"friendly, simple, safe for kids, {prompt}"
    )

    image = client.text_to_image(
        prompt=full_prompt,
        model="black-forest-labs/FLUX.1-schnell",
        negative_prompt="violence, scary, dark, adult content, realistic"
    )

    os.makedirs(
        os.path.dirname(output_path) if os.path.dirname(output_path) else ".",
        exist_ok=True
    )
    image.save(output_path)
    return output_path


# test
if __name__ == "__main__":
    os.makedirs("static", exist_ok=True)
    print("Testing image generation...")

    try:
        path = generate_image(
            prompt="a cute cat playing in the rain",
            output_path="static/test_image.png"
        )
        size = os.path.getsize(path)
        print(f"✅ Image saved: {path}")
        print(f"✅ File size: {size} bytes")
        if size > 1000:
            print("✅ Image generation works!")
        else:
            print("⚠️ File too small")
    except Exception as e:
        print(f"❌ Failed: {e}")