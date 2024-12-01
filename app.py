import os
from flask import Flask, render_template, request, send_file
import pdfplumber
import docx
import csv
from werkzeug.utils import secure_filename
import google.generativeai as genai
from fpdf import FPDF  # pip install fpdf

# from transformers import T5Tokenizer, T5ForConditionalGeneration


# Set your API key
os.environ["GOOGLE_API_KEY"] = "YOUR_API_INSERT_HERE"
genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
model = genai.GenerativeModel("models/gemini-1.5-pro")

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "uploads/"
app.config["RESULTS_FOLDER"] = "results/"
app.config["ALLOWED_EXTENSIONS"] = {"pdf", "txt", "docx"}


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]
    )


def extract_text_from_file(file_path):
    ext = file_path.rsplit(".", 1)[1].lower()
    if ext == "pdf":
        with pdfplumber.open(file_path) as pdf:
            text = "".join([page.extract_text() for page in pdf.pages])
        return text
    elif ext == "docx":
        doc = docx.Document(file_path)
        text = " ".join([para.text for para in doc.paragraphs])
        return text
    elif ext == "txt":
        with open(file_path, "r") as file:
            return file.read()
    return None


def Question_mcqs_generator(input_text, num_questions):
    prompt = f"""
    Anda adalah asisten AI yang membantu pengguna menghasilkan pertanyaan pilihan ganda (MCQ) berdasarkan teks berikut:
    '{input_text}'
    Silakan buat {num_questions} pertanyaan pilihan ganda (MCQ) dari teks tersebut. Setiap pertanyaan harus memiliki:
    - Sebuah pertanyaan yang jelas
    - Empat pilihan jawaban (diberi label A, B, C, D)
    - Jawaban yang benar ditunjukkan dengan jelas
    Format:
    ## MCQ
    Pertanyaan: [pertanyaan]
    A) [opsi A]
    B) [opsi B]
    C) [opsi C]
    D) [opsi D]
    Jawaban Benar: [opsi benar]
    """
    response = model.generate_content(prompt).text.strip()
    return response


def save_mcqs_to_file(mcqs, filename):
    results_path = os.path.join(app.config["RESULTS_FOLDER"], filename)
    with open(results_path, "w") as f:
        f.write(mcqs)
    return results_path


def create_pdf(mcqs, filename):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    for mcq in mcqs.split("## MCQ"):
        if mcq.strip():
            pdf.multi_cell(0, 10, mcq.strip())
            pdf.ln(5)  # Add a line break

    pdf_path = os.path.join(app.config["RESULTS_FOLDER"], filename)
    pdf.output(pdf_path)
    return pdf_path


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate_mcqs():
    if "file" not in request.files:
        return "No file part"

    file = request.files["file"]

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(file_path)

        # Extract text from the uploaded file
        text = extract_text_from_file(file_path)

        if text:
            num_questions = int(request.form["num_questions"])
            mcqs = Question_mcqs_generator(text, num_questions)

            # Save the generated MCQs to a file
            txt_filename = f"generated_mcqs_{filename.rsplit('.', 1)[0]}.txt"
            pdf_filename = f"generated_mcqs_{filename.rsplit('.', 1)[0]}.pdf"
            save_mcqs_to_file(mcqs, txt_filename)
            create_pdf(mcqs, pdf_filename)

            # Display and allow downloading
            return render_template(
                "results.html",
                mcqs=mcqs,
                txt_filename=txt_filename,
                pdf_filename=pdf_filename,
            )
    return "Invalid file format"


@app.route("/download/<filename>")
def download_file(filename):
    file_path = os.path.join(app.config["RESULTS_FOLDER"], filename)
    return send_file(file_path, as_attachment=True)


if __name__ == "__main__":
    if not os.path.exists(app.config["UPLOAD_FOLDER"]):
        os.makedirs(app.config["UPLOAD_FOLDER"])
    if not os.path.exists(app.config["RESULTS_FOLDER"]):
        os.makedirs(app.config["RESULTS_FOLDER"])
    app.run(debug=True)
