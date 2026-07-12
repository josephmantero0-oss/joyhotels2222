
# Open file in binary mode
with open('app.py', 'rb') as f:
    content = f.read()

# Replace the specific bad sequence with a placeholder
# Found: b'\\n[\xf0x\x01\x1c \xa6 BACKUP]'
# Let's be safer: replace any byte > 127 with nothing for now, or just target the emoji block if we can find it.
# Simpler: Decode with 'ignore' or 'replace' and write back as utf-8

try:
    decoded = content.decode('utf-8', errors='ignore')
    # Or 'replace' to see where errors were:
    # decoded = content.decode('utf-8', errors='replace')
    
    # Write back as clean UTF-8
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(decoded)
    print("File cleaned and saved as UTF-8.")

except Exception as e:
    print(f"Error cleaning file: {e}")
