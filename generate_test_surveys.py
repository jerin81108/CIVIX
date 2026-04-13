import sys
import subprocess
import datetime

def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

try:
    import openpyxl
except ImportError:
    install('openpyxl')
    import openpyxl

from openpyxl import Workbook

wb = Workbook()
ws = wb.active
ws.title = "Surveys"

headers = ["DATE", "TIME", "CLIENT NAME", "CLIENT MOBILE", "LOCATION", "AREA", "SIZE", "EMPLOYEE"]
ws.append(headers)

data = [
    [datetime.date.today().strftime("%Y-%m-%d"), "09:00:00", "Testing Tech Innovations", "9876543210", "Tiruppur Branch", "4500", "50x90", "Worker A"],
    [datetime.date.today().strftime("%Y-%m-%d"), "11:30:00", "Royal Designs Group", "1234567890", "Coimbatore East", "1200", "30x40", "Worker B"],
    [datetime.date.today().strftime("%Y-%m-%d"), "15:45:00", "Alpha Construct", "9998887776", "Chennai Main", "8000", "100x80", "Worker A"],
]

for row in data:
    ws.append(row)

filename = "test_surveys.xlsx"
wb.save(filename)
print(f"Successfully generated {filename} locally.")
