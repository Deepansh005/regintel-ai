import pdfplumber


def extract_text_from_pdf(file_path: str) -> str:
    try:
        text = ""

        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""

        return text

    except Exception as e:
        raise Exception(f"Error extracting PDF text: {str(e)}")