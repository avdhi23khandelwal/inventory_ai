
import os
if os.path.exists("inventory.db"):
    os.remove("inventory.db")
    print("Removed inventory.db.")
else:
    print("No inventory.db found — nothing to remove.")
