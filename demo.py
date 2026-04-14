import csv
import random
from datetime import datetime, timedelta

notes = [
    "Salary", "Food", "Transport", "Coffee", "Snack",
    "Gift", "Game", "Subscription", "Transfer", "Refund",
    "Shopping", "Rent", "Bonus", "Freelance", "Taxi",
    "Electricity bill", "Mobile data", "Movie", "Book", "Donation"
]

def random_date():
    # 📅 last 3 years
    start_year = datetime.now().year - 3
    end_year = datetime.now().year

    year = random.randint(start_year, end_year)
    month = random.randint(1, 12)
    day = random.randint(1, 28)  # safe for all months

    hour = random.randint(0, 23)
    minute = random.randint(0, 59)
    second = random.randint(0, 59)

    return datetime(year, month, day, hour, minute, second)

rows = []

for i in range(1, 1001):
    tx_type = random.choice(["in", "out"])

    amount = round(random.uniform(500, 50000), 2)

    note = random.choice(notes)

    if random.random() < 0.1:
        note += f" #{random.randint(1, 999)}"

    created_at = random_date()

    rows.append([
        i,
        tx_type,
        amount,
        note,
        created_at.strftime("%Y-%m-%d %H:%M:%S")
    ])

filename = "demo/demo_transactions_3y.csv"

with open(filename, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["id", "type", "amount", "note", "created_at"])
    writer.writerows(rows)

print(f"Generated {filename} with 1000 realistic multi-year rows 🚀")