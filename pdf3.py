import pandas as pd
import pdfplumber

def extract_data_from_pdf(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        # Extract Name and DOB from the first page
        first_page = pdf.pages[0]
        first_page_text = first_page.extract_text()

        # Search for Name and DOB
        name_line = next((line for line in first_page_text.split('\n') if "NAME" in line), None)
        dob_line = next((line for line in first_page_text.split('\n') if "D.O.B." in line), None)

        # Parse Name and DOB
        name = name_line.split(":")[1].strip() if name_line else "Not Found"
        dob = dob_line.split(":")[1].strip() if dob_line else "Not Found"

        # Extract raw text from the fourth page (Frequency Data)
        fourth_page = pdf.pages[3]
        fourth_page_text = fourth_page.extract_text()

        # Debugging: Display raw text
        print("Extracted Raw Text from Fourth Page:")
        print(fourth_page_text)

        # Initialize variables for frequency data
        standard_frequency = "Not Found"
        dominant_frequency = "Not Found"

        # Step 1: Process raw text for frequencies
        if fourth_page_text:
            lines = fourth_page_text.split('\n')
            frequencies = [word for line in lines for word in line.split() if "Hz" in word]
            if len(frequencies) >= 2:
                # Assuming the second "Hz" value is Standard Frequency and the first is Dominant
                standard_frequency = frequencies[1]
                dominant_frequency = frequencies[0]

        # Extract table data from page 5
        fifth_page = pdf.pages[4]
        raw_text = fifth_page.extract_text()
        tables = fifth_page.extract_tables()

        # Parse raw text into rows for dynamic extraction
        parsed_data = []
        if raw_text:
            lines = raw_text.split('\n')
            for line in lines:
                if any(char.isdigit() or '%' in char for char in line):  # Filter rows with numeric data
                    parsed_data.append(line.split())

        # Separate the data into two tables
        if len(parsed_data) > 0:
            table_1 = pd.DataFrame(parsed_data[:2])  # First two rows for Table 1
            table_2 = pd.DataFrame(parsed_data[2:])  # Remaining rows for Table 2
        else:
            table_1 = pd.DataFrame(tables[0] if tables else [])
            table_2 = pd.DataFrame(tables[1] if len(tables) > 1 else [])

        # Return all extracted data
        return {
            "Name": name,
            "DOB": dob,
            "Frequency Data": {
                "Standard Frequency": standard_frequency,
                "Dominant Frequency": dominant_frequency
            },
            "Table 1": table_1,
            "Table 2": table_2
        }

# Use your PDF path here
pdf_path = "/Users/nalindagamaarachchi/Work/Brain/pdf/test.pdf"

# Extract all data
extracted_data = extract_data_from_pdf(pdf_path)

# Display the results
print("\nExtracted Data:")
print(f"Name: {extracted_data['Name']}")
print(f"DOB: {extracted_data['DOB']}")
print("Frequency Data:")
print(f"Standard Frequency: {extracted_data['Frequency Data']['Standard Frequency']}")
print(f"Dominant Frequency: {extracted_data['Frequency Data']['Dominant Frequency']}")

# Display extracted tables
print("\nTable 1:")
print(extracted_data["Table 1"])
print("\nTable 2:")
print(extracted_data["Table 2"])
