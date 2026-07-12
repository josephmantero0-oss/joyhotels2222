reqs = ['pytest==8.1.1', 'pytest-cov==5.0.0', 'flake8==7.0.0']

# Try reading as utf-16le first
try:
    with open('requirements.txt', 'r', encoding='utf-16le') as f:
        content = f.read()
except UnicodeError:
    with open('requirements.txt', 'r', encoding='utf-8') as f:
        content = f.read()

lines = content.split('\n')
existing_reqs = [line.strip().split('==')[0] for line in lines if line.strip()]

for req in reqs:
    pkg_name = req.split('==')[0]
    if pkg_name not in existing_reqs:
        lines.append(req)

with open('requirements.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines) + '\n')

print("Requirements updated")
