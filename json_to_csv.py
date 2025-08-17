import os
import json
import csv

INPUT_DIR = "output_json"
OUTPUT_DIR = "tables_json_to_csv"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def write_csv(output_path, rows):
    """Write rows to a CSV file with UTF-8 encoding."""
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerows(rows)

def convert_json_to_csv(json_path):
    """Convert a JSON file with tables directly into CSV files."""
    base_name = os.path.splitext(os.path.basename(json_path))[0]

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f" Failed to load JSON: {json_path} — {e}")
        return

    tables = data.get("tables", [])
    if not tables:
        print(f" No tables found in: {base_name}")
        return

    for idx, table in enumerate(tables, start=1):
        output_file = os.path.join(OUTPUT_DIR, f"{base_name}_table_{idx}.csv")
        write_csv(output_file, table)
        print(f" Saved: {output_file} — {len(table)} rows")

def process_all_json_files():
    """Convert all JSON files in the input directory."""
    json_files = sorted(f for f in os.listdir(INPUT_DIR) if f.endswith(".json"))

    if not json_files:
        print(" No JSON files found.")
        return

    for json_file in json_files:
        json_path = os.path.join(INPUT_DIR, json_file)
        convert_json_to_csv(json_path)

if __name__ == "__main__":
    print(f" Starting conversion from '{INPUT_DIR}' to '{OUTPUT_DIR}' ...")
    process_all_json_files()
    print(" Conversion complete.")
