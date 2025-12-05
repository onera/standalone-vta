# IMPORT PACKAGES
# ---------------
import csv


###############################################

# READ CSV
# --------
def load_csv_to_dict(filepath):
    """
    Read a CSV and return a dict (the key is the first row data, the value is the row (str list)).
    
    Returns:
    dict: { "key": ["key", "val1", "val2"...], ... }
    """
    data_dict = {}
    
    try:
        with open(filepath, mode='r', newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            
            for row in reader:
                # Ignore empty row
                if row:
                    key = row[0]
                    # Store the full row
                    data_dict[key] = row
                    
        return data_dict

    except FileNotFoundError:
        print(f"ERROR : file {filepath} not found.")
        return {}

