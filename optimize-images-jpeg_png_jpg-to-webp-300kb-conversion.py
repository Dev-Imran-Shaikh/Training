import os
import io
from PIL import Image, ImageOps

# ============================================================
# SETTINGS
# ============================================================

MAX_SIZE_KB = 300
MAX_SIZE_BYTES = MAX_SIZE_KB * 1024

# Quality search range
MIN_QUALITY = 10
MAX_QUALITY = 95

# WebP encode method (0=fast/low-compression, 6=slow/best-compression)
# 4 is a good speed/size tradeoff. Bump to 6 only if you need the smallest
# possible files and don't mind slower runs.
WEBP_METHOD = 4

# Output folder
OUTPUT_FOLDER = "optimized"

# ============================================================
# SCRIPT
# ============================================================

def _encode(img, quality, icc_profile):
    """Encode image to WEBP in memory and return the bytes buffer."""
    buf = io.BytesIO()
    save_kwargs = {"quality": quality, "method": WEBP_METHOD}
    if icc_profile:
        save_kwargs["icc_profile"] = icc_profile
    img.save(buf, "WEBP", **save_kwargs)
    return buf.getvalue()


def optimize_image(input_path, output_path):
    try:
        img = Image.open(input_path)

        # Fix orientation BEFORE any processing (phone photos often rely on
        # EXIF orientation tags; ignoring this can also make crops/rotation
        # look "off" even though it won't itself dull colors).
        img = ImageOps.exif_transpose(img)

        # Grab the embedded color profile so we can carry it into the WEBP.
        # This is the main fix for the "dull colors" issue - without this,
        # Pillow silently drops the profile and colors get reinterpreted
        # as plain sRGB.
        icc_profile = img.info.get("icc_profile")

        original_width, original_height = img.size

        # Convert image mode correctly
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
        else:
            img = img.convert("RGB")

        # --- Binary search for the highest quality that fits under the
        # --- size budget. This replaces the old linear step-down loop,
        # --- cutting the number of encodes roughly from ~17 to ~6.
        lo, hi = MIN_QUALITY, MAX_QUALITY
        best_bytes = None
        best_quality = None

        # First, check the floor: if even MIN_QUALITY can't hit the target,
        # we just use MIN_QUALITY's result as the best-effort output.
        floor_bytes = _encode(img, MIN_QUALITY, icc_profile)
        if len(floor_bytes) > MAX_SIZE_BYTES:
            best_bytes = floor_bytes
            best_quality = MIN_QUALITY
        else:
            best_bytes = floor_bytes
            best_quality = MIN_QUALITY
            while lo <= hi:
                mid = (lo + hi) // 2
                data = _encode(img, mid, icc_profile)
                if len(data) <= MAX_SIZE_BYTES:
                    # Fits - remember it, then try for higher quality
                    best_bytes = data
                    best_quality = mid
                    lo = mid + 1
                else:
                    hi = mid - 1

        if os.path.exists(output_path):
            os.remove(output_path)

        with open(output_path, "wb") as f:
            f.write(best_bytes)

        final_size = os.path.getsize(output_path)

        final_img = Image.open(output_path)
        if final_img.size != (original_width, original_height):
            print(f"WARNING: Dimensions changed for {os.path.basename(input_path)}")

        print(
            f"SUCCESS: {os.path.basename(input_path)} "
            f"-> {os.path.basename(output_path)} "
            f"| {final_size / 1024:.1f} KB "
            f"| quality={best_quality} "
            f"| {original_width}x{original_height}"
        )

    except Exception as e:
        print(f"ERROR: {os.path.basename(input_path)} -> {e}")


def main():
    script_folder = os.path.dirname(os.path.abspath(__file__))
    output_folder = os.path.join(script_folder, OUTPUT_FOLDER)
    os.makedirs(output_folder, exist_ok=True)

    supported_extensions = (".jpg", ".jpeg", ".png")
    files = [
        f for f in os.listdir(script_folder)
        if f.lower().endswith(supported_extensions)
    ]

    if not files:
        print("No JPG, JPEG, or PNG images found.")
        input("Press Enter to exit...")
        return

    print("=" * 60)
    print("IMAGE OPTIMIZER (fast, color-safe)")
    print("=" * 60)
    print(f"Images found: {len(files)}")
    print(f"Target size: < {MAX_SIZE_KB} KB")
    print(f"Output folder: {OUTPUT_FOLDER}")
    print("=" * 60)
    print()

    for filename in files:
        input_path = os.path.join(script_folder, filename)
        name_without_extension = os.path.splitext(filename)[0]
        output_filename = name_without_extension + ".webp"
        output_path = os.path.join(output_folder, output_filename)
        optimize_image(input_path, output_path)

    print()
    print("=" * 60)
    print("ALL IMAGES PROCESSED")
    print("=" * 60)
    print()
    print("Optimized images are inside:")
    print(output_folder)

    input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()
