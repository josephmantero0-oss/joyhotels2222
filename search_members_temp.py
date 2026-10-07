import glob
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

for fpath in ['templates/dashboard.html', 'templates/guest_checkin_form.html', 'templates/guest_portal.html', 'templates/bill.html', 'app.py']:
    with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    matches = []
    for i, line in enumerate(lines, 1):
        if 'member' in line.lower():
            matches.append((i, line.strip()))
    
    if matches:
        print(f"\n=== {fpath} ({len(matches)} matches) ===")
        for lno, text in matches:
            print(f"  {lno}: {text[:120]}")
