import re
content = open('templates/dashboard.html', encoding='utf-8').read()
new_card = '''                <div class="financial-card" style="border-left: 4px solid var(--info-color); margin-bottom: 1.5rem;">
                    <h3 style="color: var(--text-primary);">&#128190; Export Guest Data</h3>
                    <p style="font-size: 0.9rem; color: var(--text-secondary); margin: 10px 0;">
                        Download a complete, nicely sorted backup of all guest history.<br>
                        <strong>Formats included:</strong> PDF, Excel (.xlsx), and Word (.docx). All formats include guest ID photos in visible size.
                    </p>
                    <button class="btn btn-primary" onclick="window.location.href='/api/backup/export_all'" style="font-size: 1.05rem; padding: 0.8rem 1.5rem;">
                        &#128142; Download Backup Data (ZIP)
                    </button>
                </div>'''

new_content = re.sub(
    r'<div class="financial-card" style="border-left: 4px solid var\(--info-color\); margin-bottom: 1\.5rem;">.*?<button class="btn btn-outline" onclick="viewDatabaseAsPdf\(\)">.*?</button>\s*</div>',
    new_card,
    content,
    flags=re.DOTALL
)
open('templates/dashboard.html', 'w', encoding='utf-8').write(new_content)
print('Replaced')
