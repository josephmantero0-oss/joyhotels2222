import os
import sqlite3
import textwrap
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

BASE = r'c:\Users\NAJUKA\Desktop\joyhotels'
DB_PATH = os.path.join(BASE, 'hotel.db')
OUT_PATH = os.path.join(BASE, 'guest_data_export.pdf')

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
rows = conn.execute(
    '''
    SELECT id, room_id, guest_name, phone, address, id_number, id_photo,
           amount, checkin_time, checkout_time, extra_charges, status, members
    FROM bookings
    ORDER BY id ASC
    '''
).fetchall()
conn.close()

c = canvas.Canvas(OUT_PATH, pagesize=A4)
width, height = A4
margin = 50
y = height - 50

c.setTitle('JoyHotels Guest Data Export')
c.setAuthor('JoyHotels')
c.setFont('Helvetica-Bold', 18)
c.drawString(margin, y, 'JoyHotels - Guest Data Export')
y -= 25
c.setFont('Helvetica', 10)
c.drawString(margin, y, f'Total Records: {len(rows)}')
y -= 30

for idx, row in enumerate(rows, start=1):
    if y < 120:
        c.showPage()
        y = height - 50

    c.setFont('Helvetica-Bold', 11)
    c.drawString(margin, y, f'{idx}. Guest #{row["id"]}')
    y -= 18

    c.setFont('Helvetica', 10)
    details = [
        f'Name: {row["guest_name"] or "-"}',
        f'Phone: {row["phone"] or "-"}',
        f'Room: {row["room_id"] or "-"}',
        f'Address: {row["address"] or "-"}',
        f'ID Number: {row["id_number"] or "-"}',
        f'Amount: {row["amount"] or "0"}',
        f'Check-in: {row["checkin_time"] or "-"}',
        f'Check-out: {row["checkout_time"] or "-"}',
        f'Extra Charges: {row["extra_charges"] or "0"}',
        f'Status: {row["status"] or "-"}',
        f'Members: {row["members"] or "-"}',
        f'ID Photo: {row["id_photo"] or "-"}',
    ]

    for line in details:
        if y < 60:
            c.showPage()
            y = height - 50
        wrapped = textwrap.wrap(line, width=100)
        for chunk in wrapped:
            c.drawString(margin + 10, y, chunk)
            y -= 12
        y -= 5

    y -= 12

c.save()
print(f'PDF created: {OUT_PATH}')
print(f'File size: {os.path.getsize(OUT_PATH)} bytes')
