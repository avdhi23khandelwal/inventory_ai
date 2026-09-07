import os
print("Checking for database...")
if os.path.exists("inventory.db"):
    os.remove("inventory.db")
    print("SUCCESS: Database deleted!")
else:
    print("No database found to delete.")
