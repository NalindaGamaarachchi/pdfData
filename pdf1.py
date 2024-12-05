
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

        # Extract raw text from the fourth page
        fourth_page = pdf.pages[3]
        fourth_page_text = fourth_page.extract_text()

        # Debugging: Display raw text
        print("Extracted Raw Text from Fourth Page:")
        print(fourth_page_text)

        # Initialize variables for frequency data
        standard_frequency = "Not Found"
        dominant_frequency = "Not Found"

        # Step 1: Process raw text
        if fourth_page_text:
            lines = fourth_page_text.split('\n')
            frequencies = [word for line in lines for word in line.split() if "Hz" in word]
            if len(frequencies) >= 2:
                # Assuming the second "Hz" value is Standard Frequency and the first is Dominant
                standard_frequency = frequencies[1]
                dominant_frequency = frequencies[0]

        # Return extracted data
        return {
            "Name": name,
            "DOB": dob,
            "Frequency Data": {
                "Standard Frequency": standard_frequency,
                "Dominant Frequency": dominant_frequency
            }
        }

# Use your PDF path here
pdf_path = "/Users/nalindagamaarachchi/Work/Brain/pdf/test.pdf"

# Extract data
extracted_data = extract_data_from_pdf(pdf_path)

# Display the results
print("\nExtracted Data:")
print(f"Name: {extracted_data['Name']}")
print(f"DOB: {extracted_data['DOB']}")
print("Frequency Data:")
print(f"Standard Frequency: {extracted_data['Frequency Data']['Standard Frequency']}")
print(f"Dominant Frequency: {extracted_data['Frequency Data']['Dominant Frequency']}")
