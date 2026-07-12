
with open('app.py', 'rb') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if b'BACKUP' in line:
        print(f"Line {i+1}: {line}")
        try:
            line.decode('utf-8')
            print("  - Valid UTF-8")
        except UnicodeDecodeError as e:
            print(f"  - Invalid UTF-8: {e}")
