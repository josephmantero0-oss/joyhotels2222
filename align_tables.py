import re

file_path = r'c:\Users\JOY\OneDrive\Desktop\joyhotels\updated_guest_history.md'

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

def format_markdown_tables(lines):
    out_lines = []
    table_lines = []
    
    def process_table(t_lines):
        if not t_lines: return []
        # split by |
        rows = [[cell.strip() for cell in line.split('|')[1:-1]] for line in t_lines]
        # find max width of each col
        col_widths = [0] * len(rows[0])
        for row in rows:
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    # For separator line like '---', we don't count towards width but we need minimum 3
                    if set(cell) == {'-'} or set(cell) == {'-', ':'}:
                        pass
                    else:
                        col_widths[i] = max(col_widths[i], len(cell))
        
        # pad rows
        res = []
        for row_idx, row in enumerate(rows):
            formatted_row = "|"
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    if set(cell) == {'-'} or set(cell) == {'-', ':'}:
                        formatted_row += "-" * (col_widths[i] + 2) + "|"
                    else:
                        formatted_row += " " + cell.ljust(col_widths[i]) + " |"
            res.append(formatted_row)
        return res

    for line in lines:
        if line.strip().startswith('|'):
            table_lines.append(line.strip())
        else:
            if table_lines:
                out_lines.extend(process_table(table_lines))
                out_lines.append("\n")
                table_lines = []
            out_lines.append(line.rstrip('\n'))
            
    if table_lines:
        out_lines.extend(process_table(table_lines))
        
    return out_lines

formatted_lines = format_markdown_tables(lines)

with open(file_path, 'w', encoding='utf-8') as f:
    for line in formatted_lines:
        f.write(line + '\n')

print("Tables have been perfectly aligned for readable raw text.")
