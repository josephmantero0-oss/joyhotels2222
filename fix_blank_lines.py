import re

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Remove excessive blank lines (more than 2 in a row)
content = re.sub(r'\n{3,}', '\n\n', content)

# Fix decorator separation issue - ensure no blank line between decorator and next line
# This pattern finds @ followed by stuff, then blank line, then another @ or def
content = re.sub(r'(@\w+[^\n]*\n)\n+(@)', r'\1\2', content)
content = re.sub(r'(@\w+[^\n]*\n)\n+(def )', r'\1\2', content)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed excessive blank lines in app.py")
print("File size:", len(content), "bytes")
