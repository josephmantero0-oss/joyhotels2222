import sys
sys.path.insert(0, 'c:\\Users\\NAJUKA\\Desktop\\joyhotels')
from app import app

print("Flask routes related to 'guest':")
for rule in app.url_map.iter_rules():
    if 'guest' in str(rule):
        print(f"{rule.rule} -> {rule.endpoint} -> {rule.methods}")
