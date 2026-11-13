import os
import re

html_path = "e:/vykon/index.html"

with open(html_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

# 1. Comment out the HTML block
start_idx = -1
end_idx = -1

for i, line in enumerate(lines):
    if '<section id="auditenergy"' in line:
        start_idx = i
        break

if start_idx != -1:
    # Find matching closing section
    for i in range(start_idx + 1, len(lines)):
        if '</section>' in lines[i]:
            end_idx = i
            break

if start_idx != -1 and end_idx != -1:
    # Modify inner comments to prevent breaking the outer comment
    for i in range(start_idx, end_idx + 1):
        lines[i] = lines[i].replace('-->', '- ->').replace('<!--', '<!- -')
    
    # Wrap in comments
    lines.insert(end_idx + 1, "-->\n")
    lines.insert(start_idx, "<!-- THE ENTIRE AUDIT SECTION COMMENTED OUT\n")

# 2. Comment out the JS block line by line
js_start_idx = -1
js_end_idx = -1

for i, line in enumerate(lines):
    if '// ENERGY EXPENDITURE AUDIT & LINEAR REGRESSION LOGIC' in line:
        js_start_idx = i
        break

for i in range(js_start_idx + 1, len(lines)):
    if '// Redirect to contact page when service card widgets are clicked' in line:
        js_end_idx = i - 1
        break

if js_start_idx != -1 and js_end_idx != -1:
    for i in range(js_start_idx, js_end_idx + 1):
        # Don't double comment empty lines if not needed, but easiest is just prefix //
        if not lines[i].strip().startswith('//'):
            lines[i] = '// ' + lines[i]

with open(html_path, "w", encoding="utf-8") as f:
    f.writelines(lines)

print("Successfully commented out the audit HTML and JS.")
