from flask import Flask, request, render_template, Response, send_file
import os
import pdfplumber
import fitz  # PyMuPDF
import pandas as pd
import io
import shutil
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
import zipfile



app = Flask(__name__)

# Folders for uploads and static files
UPLOAD_FOLDER = 'upload'
STATIC_FOLDER = os.path.join('static', 'images')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(STATIC_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['STATIC_FOLDER'] = STATIC_FOLDER


def extract_name_and_dob(pdf_path):
    try:
        with pdfplumber.open(pdf_path) as pdf:
            first_page = pdf.pages[0]
            text = first_page.extract_text()
            name = next((line.split(":")[1] for line in text.split("\n") if "NAME" in line), "Not found")
            dob = next((line.split(":")[1] for line in text.split("\n") if "D.O.B." in line), "Not found")
            return {"name": name.strip(), "dob": dob.strip()}
    except Exception as e:
        print(f"Error processing PDF: {e}")
        return {"name": "Error", "dob": "Invalid PDF"}


def extract_images(pdf_path):
    """Extract the first image from specific pages in the PDF."""
    doc = fitz.open(pdf_path)
    images = {}
    
    # Define the mapping of pages to variables
    page_image_map = {5: "imagefrompage5", 6: "imagefrompage6", 9: "imagefrompage9"}

    try:
        for page_num, var_name in page_image_map.items():
            # Get the page (0-based indexing in PyMuPDF)
            page = doc[page_num - 1]
            page_images = page.get_images(full=True)

            # Extract the first image from the page
            if page_images:
                img = page_images[0]
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]

                # Save the image to the static folder
                image_path = os.path.join(STATIC_FOLDER, f"{var_name}.{image_ext}")
                with open(image_path, "wb") as img_file:
                    img_file.write(image_bytes)

                # Add the image path to the dictionary for rendering
                images[var_name] = f"/static/images/{os.path.basename(image_path)}"
            else:
                print(f"No images found on page {page_num}.")
    except Exception as e:
        print(f"Error extracting images: {e}")
    finally:
        doc.close()

    return images


def extract_data_from_page_4(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        fourth_page = pdf.pages[3]
        fourth_page_text = fourth_page.extract_text()

    standard_frequency = "Not Found"
    dominant_frequency = "Not Found"

    if fourth_page_text:
        lines = fourth_page_text.split('\n')
        frequencies = [word for line in lines for word in line.split() if "Hz" in word]
        if len(frequencies) >= 2:
            standard_frequency = frequencies[1]
            dominant_frequency = frequencies[0]

    return pd.DataFrame(
        [{"Metric": "Standard Frequency", "Value": standard_frequency},
         {"Metric": "Dominant Frequency", "Value": dominant_frequency}]
    )


def extract_data_from_page_5(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        fifth_page = pdf.pages[4]
        raw_text = fifth_page.extract_text()
        tables = fifth_page.extract_tables()

    parsed_data = []
    if raw_text:
        lines = raw_text.split('\n')
        for line in lines:
            if any(char.isdigit() or '%' in char for char in line):
                parsed_data.append(line.split())

    table_1 = pd.DataFrame(parsed_data[:2]) if parsed_data else pd.DataFrame(tables[0]) if tables else pd.DataFrame()
    table_2 = pd.DataFrame(parsed_data[2:]) if len(parsed_data) > 2 else pd.DataFrame(tables[1]) if len(tables) > 1 else pd.DataFrame()
    max_columns = max(table_1.shape[1], table_2.shape[1])
    table_1 = table_1.reindex(columns=range(max_columns), fill_value=None)
    table_2 = table_2.reindex(columns=range(max_columns), fill_value=None)
    column_names = [f"Column {i+1}" for i in range(max_columns)]
    table_1.columns = column_names
    table_2.columns = column_names
    table_1 = table_1.loc[:, ~table_1.columns.isin(["Column 6"])]

    return table_1, table_2


def extract_data_from_page_6(pdf_path):
    p_tension_left = "Not Found"
    p_tension_right = "Not Found"

    with pdfplumber.open(pdf_path) as pdf:
        sixth_page = pdf.pages[5]
        page_text = sixth_page.extract_text()

        if page_text:
            lines = page_text.split('\n')
            numeric_rows = []
            for line in lines:
                try:
                    numeric_values = [float(value) for value in line.split() if value.replace('.', '', 1).isdigit()]
                    if numeric_values:
                        numeric_rows.append(numeric_values)
                except ValueError:
                    continue

            if len(numeric_rows) >= 2:
                p_tension_left = numeric_rows[0][0]
                p_tension_right = numeric_rows[1][0]

    return pd.DataFrame(
        [{"Metric": "P. Tension Left", "Value": p_tension_left},
         {"Metric": "P. Tension Right", "Value": p_tension_right}]
    )


def extract_data_from_page_7(pdf_path):
    distraction_left = "Not Found"
    distraction_right = "Not Found"
    a_minus_b_left = "Not Found"
    a_minus_b_right = "Not Found"

    with pdfplumber.open(pdf_path) as pdf:
        seventh_page = pdf.pages[6]
        seventh_page_tables = seventh_page.extract_tables()

        if seventh_page_tables:
            print("Extracted Tables:", seventh_page_tables)  # Debug: Analyze table structure

            # Process Table 2 for Distraction Values
            if len(seventh_page_tables) > 1:
                table_2 = seventh_page_tables[1]
                try:
                    distraction_values = [
                        float(cell) for row in table_2 for cell in row if cell and cell.replace('.', '', 1).isdigit()
                    ]
                    if len(distraction_values) >= 2:
                        distraction_left, distraction_right = distraction_values[:2]
                except ValueError as e:
                    print(f"Error parsing distraction values: {e}")

            # Process Table 3 for A/-B Values
            if len(seventh_page_tables) > 2:
                table_3 = seventh_page_tables[2]
                try:
                    a_minus_b_values = [
                        float(cell) for row in table_3 for cell in row if cell and cell.replace('.', '', 1).isdigit()
                    ]
                    if len(a_minus_b_values) >= 2:
                        a_minus_b_left, a_minus_b_right = a_minus_b_values[:2]
                except ValueError as e:
                    print(f"Error parsing A/-B values: {e}")

        # Fallback: Extract from raw text if tables are missing or incomplete
        if any(val == "Not Found" for val in [distraction_left, distraction_right, a_minus_b_left, a_minus_b_right]):
            page_text = seventh_page.extract_text()
            print("Extracted Text:", page_text)  # Debug: Analyze raw text
            if page_text:
                lines = page_text.split('\n')
                numeric_rows = []
                for line in lines:
                    try:
                        numeric_values = [float(value) for value in line.split() if value.replace('.', '', 1).isdigit()]
                        if numeric_values:
                            numeric_rows.append(numeric_values)
                    except ValueError:
                        continue

                # Dynamically assign missing values if numeric rows exist
                if len(numeric_rows) > 1:
                    if distraction_left == "Not Found" and len(numeric_rows[0]) > 0:
                        distraction_left = numeric_rows[0][0]
                    if distraction_right == "Not Found" and len(numeric_rows[1]) > 0:
                        distraction_right = numeric_rows[1][0]
                    if len(numeric_rows) > 2:
                        if a_minus_b_left == "Not Found" and len(numeric_rows[2]) > 0:
                            a_minus_b_left = numeric_rows[2][0]
                        if a_minus_b_right == "Not Found" and len(numeric_rows[3]) > 0:
                            a_minus_b_right = numeric_rows[3][0]

    table_7_1 = pd.DataFrame([
        {"Metric": "Distraction Left", "Value": distraction_left},
        {"Metric": "Distraction Right", "Value": distraction_right}
    ])

    table_7_2 = pd.DataFrame([
        {"Metric": "A/-B Left", "Value": a_minus_b_left},
        {"Metric": "A/-B Right", "Value": a_minus_b_right}
    ])
    return table_7_1, table_7_2

def extract_data_from_page_8(pdf_path):
    avg_a_left = "Not Found"
    avg_a_right = "Not Found"
    plus_b_left = "Not Found"
    plus_b_right = "Not Found"
    diff_ratio_la_ra = "Not Found"
    diff_ratio_plus_b_ce = "Not Found"
    amp_symmetry = "Not Found"
    l_r_sympathy = "Not Found"

    with pdfplumber.open(pdf_path) as pdf:
        eighth_page = pdf.pages[7]
        page_text = eighth_page.extract_text()

        if page_text:
            lines = page_text.split('\n')
            numeric_values = []
            for line in lines:
                words = line.split()
                for word in words:
                    if word.replace('.', '', 1).isdigit() or '%' in word:
                        numeric_values.append(word)

            if len(numeric_values) >= 8:
                avg_a_left = numeric_values[0]
                avg_a_right = numeric_values[4]
                plus_b_left = numeric_values[1]
                plus_b_right = numeric_values[5]
                diff_ratio_la_ra = numeric_values[2]
                diff_ratio_plus_b_ce = numeric_values[3]
                amp_symmetry = numeric_values[6]
                l_r_sympathy = numeric_values[7]

    # Return two separate DataFrames
    table_8_1 = pd.DataFrame([
        {"Metric": "Avg. A (Left)", "Value": avg_a_left},
        {"Metric": "Avg. A (Right)", "Value": avg_a_right},
        {"Metric": "+B (Left)", "Value": plus_b_left},
        {"Metric": "+B (Right)", "Value": plus_b_right},
        {"Metric": "Diff. Ratio La - Ra", "Value": diff_ratio_la_ra},
        {"Metric": "Diff. Ratio +B (CE)", "Value": diff_ratio_plus_b_ce}
    ])

    table_8_2 = pd.DataFrame([
        {"Metric": "Amp. Symmetry", "Value": amp_symmetry},
        {"Metric": "L-R Sympathy", "Value": l_r_sympathy}
    ])

    return table_8_1, table_8_2

def extract_data_from_page_9(pdf_path):
    sum_value = "Not Found"
    average = "Not Found"
    max_dev = "Not Found"
    std_dev = "Not Found"

    with pdfplumber.open(pdf_path) as pdf:
        ninth_page = pdf.pages[8]
        ninth_page_tables = ninth_page.extract_tables()

        if ninth_page_tables:
            table = ninth_page_tables[0]
            extracted_values = []
            for row in table:
                for cell in row:
                    if cell:
                        values = cell.split()
                        for value in values:
                            if value.replace('.', '', 1).isdigit():
                                extracted_values.append(float(value))

            if len(extracted_values) >= 4:
                sum_value = extracted_values[0]
                average = extracted_values[1]
                max_dev = extracted_values[2]
                std_dev = extracted_values[3]

        if sum_value == "Not Found":
            page_text = ninth_page.extract_text()
            if page_text:
                lines = page_text.split('\n')
                numeric_values = []
                for line in lines:
                    words = line.split()
                    for word in words:
                        if word.replace('.', '', 1).isdigit():
                            numeric_values.append(float(word))

                if len(numeric_values) >= 4:
                    sum_value = numeric_values[0]
                    average = numeric_values[1]
                    max_dev = numeric_values[2]
                    std_dev = numeric_values[3]

    return pd.DataFrame([
        {"Metric": "Sum", "Value": sum_value},
        {"Metric": "Average", "Value": average},
        {"Metric": "Max Dev", "Value": max_dev},
        {"Metric": "Std Dev", "Value": std_dev}
    ])

def add_table_to_pdf(pdf, data_frame, title, y_position):
    """
    Adds a table to the PDF.
    :param pdf: The ReportLab canvas
    :param data_frame: Pandas DataFrame to render as a table
    :param title: Title of the section
    :param y_position: Current Y-position on the PDF
    :return: Updated Y-position after rendering the table
    """
    if y_position < 100:  # Start a new page if there's not enough space
        pdf.showPage()
        pdf.setFont("Helvetica", 12)
        y_position = 750

    # Add the title
    pdf.drawString(100, y_position, title)
    y_position -= 20

    # Convert DataFrame to list of lists for ReportLab
    table_data = [data_frame.columns.tolist()] + data_frame.values.tolist()

    # Create the table
    table = Table(table_data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))

    # Calculate table height
    table_width, table_height = table.wrap(500, y_position)
    if y_position - table_height < 50:  # Start a new page if table doesn't fit
        pdf.showPage()
        pdf.setFont("Helvetica", 12)
        y_position = 750

    # Draw the table
    table.drawOn(pdf, 100, y_position - table_height)
    y_position -= table_height + 30  # Adjust position for the next element

    return y_position



@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'pdf_files' not in request.files:
            return "No files part"

        files = request.files.getlist('pdf_files')  # Get the list of uploaded files

        if not files or all(file.filename == '' for file in files):
            return "No files selected"

        extracted_results = []  # Store results for each uploaded PDF
        uploaded_files = []  # Store uploaded file information

        for file in files:
            if not file.filename.lower().endswith('.pdf'):
                return f"{file.filename} is not a valid PDF"

            # Save the file
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(file_path)

            # Store uploaded file information for download buttons
            uploaded_files.append({'filename': file.filename, 'file_path': file_path})

            # Extract data and images for each file
            extracted_data = extract_name_and_dob(file_path)
            images = extract_images(file_path)
            page_4_data = extract_data_from_page_4(file_path)
            page_5_table_1, page_5_table_2 = extract_data_from_page_5(file_path)
            page_6_data = extract_data_from_page_6(file_path)
            page_7_table_1, page_7_table_2 = extract_data_from_page_7(file_path)
            page_8_table_1, page_8_table_2 = extract_data_from_page_8(file_path)
            page_9_data = extract_data_from_page_9(file_path)

            # Append extracted data for this file
            extracted_results.append({
                'filename': file.filename,
                'extracted_data': extracted_data,
                'images': images,
                'page_4_data': page_4_data.to_html(classes="table table-striped", index=False) if not page_4_data.empty else None,
                'page_5_table_1': page_5_table_1.to_html(classes="table table-striped", index=False) if not page_5_table_1.empty else None,
                'page_5_table_2': page_5_table_2.to_html(classes="table table-striped", index=False) if not page_5_table_2.empty else None,
                'page_6_data': page_6_data.to_html(classes="table table-striped", index=False) if not page_6_data.empty else None,
                'page_7_table_1': page_7_table_1.to_html(classes="table table-striped", index=False) if not page_7_table_1.empty else None,
                'page_7_table_2': page_7_table_2.to_html(classes="table table-striped", index=False) if not page_7_table_2.empty else None,
                'page_8_table_1': page_8_table_1.to_html(classes="table table-striped", index=False) if not page_8_table_1.empty else None,
                'page_8_table_2': page_8_table_2.to_html(classes="table table-striped", index=False) if not page_8_table_2.empty else None,
                'page_9_data': page_9_data.to_html(classes="table table-striped", index=False) if not page_9_data.empty else None,
                'imagefrompage5': images.get("imagefrompage5"),
                'imagefrompage6': images.get("imagefrompage6"),
                'imagefrompage9': images.get("imagefrompage9"),
            })

        # Pass both uploaded files and extracted results to the template
        return render_template('index.html', uploaded_files=uploaded_files, results=extracted_results)

    # Render empty template for GET request
    return render_template('index.html', uploaded_files=[], results=[])


@app.route('/download_pdf', methods=['POST'])
def download_pdf():
    file_paths = request.form.getlist("file_paths")  # Get all file paths from the form
    if not file_paths:
        return "No files selected for download"

    # Create a temporary ZIP file in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for file_path in file_paths:
            # Extract data for each PDF
            extracted_data = extract_name_and_dob(file_path)
            images = extract_images(file_path)
            page_4_data = extract_data_from_page_4(file_path)
            page_5_table_1, page_5_table_2 = extract_data_from_page_5(file_path)
            page_6_data = extract_data_from_page_6(file_path)
            page_7_table_1, page_7_table_2 = extract_data_from_page_7(file_path)
            page_8_table_1, page_8_table_2 = extract_data_from_page_8(file_path)
            page_9_data = extract_data_from_page_9(file_path)

            # Access individual images
            imagefrompage5 = images.get("imagefrompage5")
            imagefrompage6 = images.get("imagefrompage6")
            imagefrompage9 = images.get("imagefrompage9")

            # Create a new PDF for this file
            pdf_buffer = io.BytesIO()
            pdf = canvas.Canvas(pdf_buffer, pagesize=letter)
            pdf.setFont("Helvetica", 12)

            # Add extracted data to the PDF
            pdf.drawString(100, 750, "Your Brain Health EEG Report")
            pdf.drawString(100, 730, f"Name: {extracted_data['name']}")
            pdf.drawString(100, 710, f"DOB: {extracted_data['dob']}")

            # Add tables
            y_position = 690
            y_position = add_table_to_pdf(pdf, page_4_data, "1. Frequency appearance rate and average amplitude", y_position)
            y_position = add_table_to_pdf(pdf, page_5_table_1, "2. The change in power of alpha waves", y_position)
            y_position = add_table_to_pdf(pdf, page_5_table_2, "3. Changes in EEG during opening and closing", y_position)
            y_position = add_table_to_pdf(pdf, page_6_data, "5. Physical tension and stress", y_position)
            y_position = add_table_to_pdf(pdf, page_7_table_1, "6. Mental distraction and stress", y_position)
            y_position = add_table_to_pdf(pdf, page_7_table_2, "7. Behavioral propensity (a/-B)", y_position)
            y_position = add_table_to_pdf(pdf, page_8_table_1, "8. Emotional propensity (La- Ra)", y_position)
            y_position = add_table_to_pdf(pdf, page_8_table_2, "9. Balance between left and right brain", y_position)
            y_position = add_table_to_pdf(pdf, page_9_data, "10. Self-feedback ability", y_position)

            # Ensure space for images
            if y_position < 200:  # Move to a new page if necessary
                pdf.showPage()
                pdf.setFont("Helvetica", 12)
                y_position = 750

            # Add images with labels
            if imagefrompage5:
                pdf.drawString(100, y_position, "2. The change in power of alpha waves")
                pdf.drawImage(imagefrompage5[1:], 100, y_position - 150, width=200, height=150)
                y_position -= 170

            if imagefrompage6:
                if y_position < 200:  # Move to a new page if necessary
                    pdf.showPage()
                    pdf.setFont("Helvetica", 12)
                    y_position = 750
                pdf.drawString(100, y_position, "4. Brain arousal level (0/SMR)")
                pdf.drawImage(imagefrompage6[1:], 100, y_position - 150, width=200, height=150)
                y_position -= 170

            if imagefrompage9:
                if y_position < 200:  # Move to a new page if necessary
                    pdf.showPage()
                    pdf.setFont("Helvetica", 12)
                    y_position = 750
                pdf.drawString(100, y_position, "10. Self-feedback ability")
                pdf.drawImage(imagefrompage9[1:], 100, y_position - 150, width=200, height=150)
                y_position -= 170

            # Save the PDF to a buffer
            pdf.save()
            pdf_buffer.seek(0)

            # Add the generated PDF to the ZIP file
            pdf_filename = os.path.basename(file_path).replace('.pdf', '_extracted.pdf')
            zip_file.writestr(pdf_filename, pdf_buffer.getvalue())

    zip_buffer.seek(0)  # Move to the start of the ZIP buffer

    # Send the ZIP file as a response
    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name='extracted_pdfs.zip'
    )
   
@app.route('/download_single_pdf', methods=['POST'])
def download_single_pdf():
    file_path = request.form.get("file_path")
    if not file_path or not os.path.exists(file_path):
        return "File not found", 404

    # Extract data and images for the specific file
    extracted_data = extract_name_and_dob(file_path)
    images = extract_images(file_path)
    page_4_data = extract_data_from_page_4(file_path)
    page_5_table_1, page_5_table_2 = extract_data_from_page_5(file_path)
    page_6_data = extract_data_from_page_6(file_path)
    page_7_table_1, page_7_table_2 = extract_data_from_page_7(file_path)
    page_8_table_1, page_8_table_2 = extract_data_from_page_8(file_path)
    page_9_data = extract_data_from_page_9(file_path)

    # Access individual images
    imagefrompage5 = images.get("imagefrompage5")
    imagefrompage6 = images.get("imagefrompage6")
    imagefrompage9 = images.get("imagefrompage9")

    # Create an in-memory PDF buffer
    pdf_buffer = io.BytesIO()
    pdf = canvas.Canvas(pdf_buffer, pagesize=letter)
    pdf.setFont("Helvetica", 12)

    # Add extracted data to the PDF
    pdf.drawString(100, 750, "Your Brain Health EEG Report")
    pdf.drawString(100, 730, f"Name: {extracted_data['name']}")
    pdf.drawString(100, 710, f"DOB: {extracted_data['dob']}")

    # Add tables
    y_position = 690
    y_position = add_table_to_pdf(pdf, page_4_data, "1. Frequency appearance rate and average amplitude", y_position)
    y_position = add_table_to_pdf(pdf, page_5_table_1, "2. The change in power of alpha waves", y_position)
    y_position = add_table_to_pdf(pdf, page_5_table_2, "3. Changes in EEG during opening and closing", y_position)
    y_position = add_table_to_pdf(pdf, page_6_data, "5. Physical tension and stress", y_position)
    y_position = add_table_to_pdf(pdf, page_7_table_1, "6. Mental distraction and stress", y_position)
    y_position = add_table_to_pdf(pdf, page_7_table_2, "7. Behavioral propensity (a/-B)", y_position)
    y_position = add_table_to_pdf(pdf, page_8_table_1, "8. Emotional propensity (La- Ra)", y_position)
    y_position = add_table_to_pdf(pdf, page_8_table_2, "9. Balance between left and right brain", y_position)
    y_position = add_table_to_pdf(pdf, page_9_data, "10. Self-feedback ability", y_position)

    # Ensure space for images
    if y_position < 200:  # Move to a new page if necessary
        pdf.showPage()
        pdf.setFont("Helvetica", 12)
        y_position = 750

    # Add images with labels
    if imagefrompage5:
        pdf.drawString(100, y_position, "2. The change in power of alpha waves")
        pdf.drawImage(imagefrompage5[1:], 100, y_position - 150, width=200, height=150)
        y_position -= 170

    if imagefrompage6:
        if y_position < 200:  # Move to a new page if necessary
            pdf.showPage()
            pdf.setFont("Helvetica", 12)
            y_position = 750
        pdf.drawString(100, y_position, "4. Brain arousal level (0/SMR)")
        pdf.drawImage(imagefrompage6[1:], 100, y_position - 150, width=200, height=150)
        y_position -= 170

    if imagefrompage9:
        if y_position < 200:  # Move to a new page if necessary
            pdf.showPage()
            pdf.setFont("Helvetica", 12)
            y_position = 750
        pdf.drawString(100, y_position, "10. Self-feedback ability")
        pdf.drawImage(imagefrompage9[1:], 100, y_position - 150, width=200, height=150)
        y_position -= 170

    # Save and return the PDF
    pdf.save()
    pdf_buffer.seek(0)

    # Send the generated PDF as a download
    return send_file(
        pdf_buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f"{os.path.basename(file_path).replace('.pdf', '_extracted.pdf')}"
    )


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
