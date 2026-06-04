import csv
import random

categories = ["Groceries", "Snacks", "Beverages", "Toiletries", "Cleaning", "Stationery"]
units = ["KG", "Piece", "Pack", "Liter"]

products = []
for i in range(1, 501):
    cat = random.choice(categories)
    products.append([
        f"Product_{cat}_{i}", 
        cat, 
        random.choice(units), 
        round(random.uniform(10, 500), 2), 
        round(random.uniform(5, 400), 2), 
        f"8901030{100000+i}", 
        random.randint(20, 500)
    ])

with open('500_real_products.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(["Name", "Category", "Unit", "Selling_Price", "Purchase_Price", "Barcode", "Initial_Stock"])
    writer.writerows(products)

print("500 Real Products CSV generated successfully!")