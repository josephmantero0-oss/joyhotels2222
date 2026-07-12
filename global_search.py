import os

search_str = b"Jaydeep"

for root, dirs, files in os.walk(r"c:\Users\JOY\OneDrive\Desktop"):
    for file in files:
        path = os.path.join(root, file)
        try:
            if os.path.getsize(path) > 10 * 1024 * 1024: # Skip files > 10MB
                continue
            with open(path, 'rb') as f:
                content = f.read()
                if search_str.lower() in content.lower():
                    print(f"Found in: {path}")
        except:
            pass
