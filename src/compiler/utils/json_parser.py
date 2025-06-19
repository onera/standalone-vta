import json
import collections
from typing import Optional, Dict, Any

def parse_json_to_dict(filepath: str) -> Optional[Dict[str, Any]]:
    """
    Reads a JSON file and converts it into a Python dictionary.

    Args:
        filepath (str): The full path to the JSON file.

    Returns:
        Optional[Dict[str, Any]]: A dictionary representing the JSON content
                                  if reading and parsing are successful,
                                  otherwise None.
    """
    #print(f"Attempting to read file: {filepath}")
    try:
        # Using 'with' ensures the file is properly closed, even if errors occur.
        # 'encoding="utf-8"' is a best practice to prevent encoding issues.
        with open(filepath, 'r', encoding='utf-8') as f:
            # json.load() reads from a file object (while json.loads() reads from a string)
            data = json.load(f, object_pairs_hook=collections.OrderedDict)
        return data
        
    except FileNotFoundError:
        print(f"ERROR: The specified file '{filepath}' was not found.")
        return None
        
    except json.JSONDecodeError:
        print(f"ERROR: The content of file '{filepath}' is not valid JSON.")
        return None
        
    except Exception as e:
        print(f"ERROR: An unexpected error occurred: {e}")
        return None
