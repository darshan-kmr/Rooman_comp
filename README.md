Resume Screening Agent

Overview

Resume Screening Agent is an AI-powered evaluation tool that ranks candidate resumes against a given job description. It generates a suitability score out of 10 for each candidate and provides a detailed breakdown including strengths, weaknesses and a final ordered shortlist. The agent assists HR teams and recruiters by automating initial candidate filtering and reducing manual review effort.

Features

Supports resume upload in PDF, DOCX, TXT and raw text formats
Job description can be pasted or uploaded as a file
Generates a structured evaluation for every candidate
Assigns a numerical fit score from 0 to 10
Highlights strengths, gaps and missing qualifications
Provides final ranking from most to least suitable
Allows report download in markdown format
Does not require database or long-term storage

How It Works

User uploads a job description and one or more resumes
The system reads and extracts text from files
Job description and resume text are combined into a structured evaluation prompt
The Gemini model processes all documents and generates scoring and feedback
Results are displayed and can be downloaded as a single report

Tools and Technologies

Python
Streamlit
Google Gemini API (gemini-2.0-flash)
PyPDF2 for PDF extraction
Native DOCX text extraction
dotenv for environment variable management

Limitations

Accuracy depends on clarity of job description and resume structure
No persistent storage of previous screenings in the current build
Scanner based or image-heavy resumes may extract poorly
Evaluation results are AI-driven and advisory in nature

Future Enhancements

Integration with Google Sheets or Supabase for result logging
Support for email or dashboard export
CSV or PDF downloadable formats
Re-ranking capability after feedback adjustment
Option to fine-tune scoring weights manually
