import pandas as pd
import pdfplumber

def extract_and_separate_tables(pdf_path, page_number):
    # Extract tables and raw text from the specified page
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[page_number - 1]
        raw_text = page.extract_text()
        tables = page.extract_tables()

    # Parse raw text into rows for dynamic extraction
    parsed_data = []
    if raw_text:
        lines = raw_text.split('\n')
        for line in lines:
            if any(char.isdigit() or '%' in char for char in line):  # Filter rows with numeric data
                parsed_data.append(line.split())

    # Separate the data into two tables based on the row count or content
    if len(parsed_data) > 0:
        table_1 = pd.DataFrame(parsed_data[:2])  # First two rows for Table 1
        table_2 = pd.DataFrame(parsed_data[2:])  # Remaining rows for Table 2
    else:
        table_1 = pd.DataFrame(tables[0] if tables else [])
        table_2 = pd.DataFrame(tables[1] if len(tables) > 1 else [])

    return table_1, table_2

# PDF Path and page number
pdf_path = "/Users/nalindagamaarachchi/Work/Brain/pdf/test.pdf"
page_number = 5  # Page with the tables

# Extract and separate tables
table_1, table_2 = extract_and_separate_tables(pdf_path, page_number)

# Display the results
print("Table 1:")
print(table_1)
print("\nTable 2:")
print(table_2)
