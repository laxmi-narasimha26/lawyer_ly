import PyPDF2

# Open the PDF file
with open('Harvey AI for lawyers.pdf', 'rb') as file:
    # Create a PDF reader object
    pdf_reader = PyPDF2.PdfReader(file)
    
    # Get the number of pages
    num_pages = len(pdf_reader.pages)
    print(f"Total pages: {num_pages}\n")
    
    # Extract text from all pages
    full_text = ""
    for page_num in range(num_pages):
        page = pdf_reader.pages[page_num]
        text = page.extract_text()
        full_text += f"\n--- Page {page_num + 1} ---\n{text}\n"
    
    # Save to a text file
    with open('project_details.txt', 'w', encoding='utf-8') as output:
        output.write(full_text)
    
    print("Text extracted successfully to project_details.txt")
