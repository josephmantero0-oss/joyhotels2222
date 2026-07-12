import os

search_str = b"Jaydeep"

for root, dirs, files in os.walk(r"c:\Users\JOY\OneDrive\Desktop"):
    for file in files:
        if file.endswith(".db"):
            path = os.path.join(root, file)
            try:
                with open(path, 'rb') as f:
                    content = f.read()
                    if search_str.lower() in content.lower():
                        print(f"Found in: {path}")
            except:
                pass
