'''PDF to text extraction using PyMuPDF (fitz). Handle multi-page resumes, section detection (experience, skills, education)'''

import fitz

SECTION_KEYWORDS = {
    "experience": ["experience", "work experience", "professional experience", "employment"],
    "skills": ["skills", "technical skills", "core competencies", "technologies"],
    "education": ["education", "academic background", "education & certifications"],
    "projects": ["projects", "personal projects", "key projects"],
    "summary": ["summary", "objective", "professional summary", "about"],
}

def extract_text_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text

def extract_sections(text: str) -> dict[str, str]:
    '''Extract resume sections from the given text using keyword matching on headers.'''
    sections = {}
    current_section = None
    current_lines = []

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        
        # Detect section headers (simple heuristic)
        matched = None
        for section, keywords in SECTION_KEYWORDS.items():
            if any(keyword in line.lower() for keyword in keywords):
                matched = section
                break
        if matched:    
            if current_section and current_lines:
                sections[current_section] = "\n".join(current_lines)
            current_section = matched
            current_lines = []
        elif current_section:
            current_lines.append(line)

    # Join lines for each section
    if current_section and current_lines:
        sections[current_section] = "\n".join(current_lines)
    return sections

def parse_resume(pdf_path: str) -> dict:
    text = extract_text_from_pdf(pdf_path)
    sections = extract_sections(text)
    return {"full_text": text, "sections": sections}

if __name__ == "__main__":
    pdf_path = "resume_matching_agent/test_data/resumes/Resume_AI_Fall_26.pdf" 
    
    result = parse_resume(pdf_path)
    print(f"Full text length: {len(result['full_text'])} chars")
    
    for section, content in result["sections"].items():
        print(f"--- {section.upper()} ---")
        print(content)
        print()