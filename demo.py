import csv
import random
from datetime import datetime, timedelta

notes = [
    "Salary", "Food", "Transport", "Coffee", "Snack",
    "Gift", "Game", "Subscription", "Transfer", "Refund",
    "Shopping", "Rent", "Bonus", "Freelance", "Taxi",
    "Electricity bill", "Mobile data", "Movie", "Book", "Donation"
]

start_time = datetime(2026, 1, 1, 8, 0, 0)

rows = []

for i in range(1, 1001):
    tx_type = random.choice(["in", "out"])

    amount = round(random.uniform(500, 50000), 2)

    note = random.choice(notes)

    # occasional detailed notes like yours
    if random.random() < 0.1:
        note += f" #{random.randint(1, 999)}"

    created_at = start_time + timedelta(minutes=i * random.randint(1, 5))

    rows.append([
        i,
        tx_type,
        amount,
        note,
        created_at.strftime("%Y-%m-%d %H:%M:%S")
    ])

filename = "demo/demo_transactions_1k.csv"

with open(filename, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["id", "type", "amount", "note", "created_at"])
    writer.writerows(rows)

print(f"Generated {filename} with 1000 rows 🚀")