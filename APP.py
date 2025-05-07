import streamlit as st
import ollama
from pathlib import Path
import json
import time
from fpdf import FPDF
import yaml
from datetime import datetime
import re

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Professional Resume', 0, 1, 'C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

class ResumeBuilder:
    def __init__(self):
        self.convo = []
        self.resume_data = {}
        self.templates = self.load_templates()
        
    def load_templates(self):
        return {
            'modern': {
                'font': 'Arial',
                'header_size': 16,
                'subheader_size': 12,
                'body_size': 10,
                'colors': {
                    'primary': '#2B547E',
                    'secondary': '#808080'
                }
            },
            'classic': {
                'font': 'Times',
                'header_size': 14,
                'subheader_size': 12,
                'body_size': 10,
                'colors': {
                    'primary': '#000000',
                    'secondary': '#404040'
                }
            }
        }

    def stream_response(self, prompt, model='llama3.2:latest'):
        self.convo.append({'role': 'user', 'content': prompt})
        response = ''
        try:
            stream = ollama.chat(model=model, messages=self.convo, stream=True)
            for chunk in stream:
                if chunk and 'message' in chunk and 'content' in chunk['message']:
                    response += chunk['message']['content']
                    yield chunk['message']['content']
        except Exception as e:
            st.error(f"Error in generating response: {str(e)}")
            return ""
        
        self.convo.append({'role': 'assistant', 'content': response})

    def generate_resume_section(self, section_name, user_input, style='professional'):
        prompts = {
            'Personal Information': """Generate a professionally formatted personal information section with the following details:
            {input}
            Format it as a structured YAML with these fields: name, title, email, phone, location, linkedin""",
            
            'Professional Summary': """Create a compelling professional summary based on:
            {input}
            Focus on key achievements and value proposition. Keep it under 4 sentences.""",
            
            'Work Experience': """Transform the following work experience into powerful bullet points:
            {input}
            Format as YAML with: company, position, duration, and at least 3 achievement-focused bullets using action verbs and metrics.""",
            
            'Skills': """Organize these skills into categories:
            {input}
            Format as YAML with these categories: Technical Skills, Soft Skills, Tools & Technologies""",
            
            'Education': """Format this education information:
            {input}
            Include: degree, institution, graduation_date, gpa (if >3.5), honors, relevant_coursework""",
            
            'Projects': """Create structured project descriptions from:
            {input}
            Format as YAML with: name, duration, technologies_used, description, key_achievements""",
            
            'Certifications': """Format certification information:
            {input}
            Include: name, issuing_organization, date, expiration_date (if applicable), credential_id"""
        }
        
        base_prompt = prompts.get(section_name, "Format the following information professionally: {input}")
        formatted_prompt = base_prompt.format(input=user_input)
        return self.stream_response(formatted_prompt)

    def create_pdf(self, filename="resume.pdf", template='modern'):
        pdf = PDF()
        template_settings = self.templates[template]
        
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        
        # Personal Information
        if 'Personal Information' in self.resume_data:
            try:
                personal_info = yaml.safe_load(self.resume_data['Personal Information']['generated'])
            except Exception as e:
                personal_info = {}
            pdf.set_font(template_settings['font'], 'B', template_settings['header_size'])
            pdf.cell(0, 10, personal_info.get('name', ''), ln=True)
            pdf.set_font(template_settings['font'], '', template_settings['body_size'])
            pdf.cell(0, 5, f"{personal_info.get('email', '')} | {personal_info.get('phone', '')} | {personal_info.get('location', '')}", ln=True)
            pdf.cell(0, 5, f"LinkedIn: {personal_info.get('linkedin', '')}", ln=True)
            pdf.ln(5)
        
        # Other sections
        sections_order = ['Professional Summary', 'Work Experience', 'Education', 'Skills', 'Projects', 'Certifications']
        
        for section in sections_order:
            if section in self.resume_data:
                pdf.set_font(template_settings['font'], 'B', template_settings['subheader_size'])
                pdf.cell(0, 10, section.upper(), ln=True)
                pdf.set_font(template_settings['font'], '', template_settings['body_size'])
                
                content = self.resume_data[section]['generated']
                # Clean up YAML formatting if present
                if '---' in content:
                    try:
                        parsed_content = yaml.safe_load(content)
                        content = self.format_yaml_content(parsed_content)
                    except Exception as e:
                        pass
                
                pdf.multi_cell(0, 5, content)
                pdf.ln(5)
        
        pdf.output(filename)
        return filename

    def format_yaml_content(self, content):
        if isinstance(content, dict):
            formatted = ""
            for key, value in content.items():
                if isinstance(value, list):
                    formatted += f"{key}:\n" + "\n".join(f"• {item}" for item in value) + "\n"
                else:
                    formatted += f"{key}: {value}\n"
            return formatted
        return str(content)

    def save_resume(self, filename="resume_data.json"):
        with open(filename, 'w') as f:
            json.dump(self.resume_data, f)

    def load_resume(self, filename="resume_data.json"):
        try:
            with open(filename, 'r') as f:
                self.resume_data = json.load(f)
        except FileNotFoundError:
            self.resume_data = {}

def main():
    st.set_page_config(page_title="Advanced Resume Builder", layout="wide")
    st.title("Advanced AI-Powered Resume Builder")
    
    builder = ResumeBuilder()
    builder.load_resume()  # Load saved resume data so PDF generation has content
    
    # Initialize session state
    if 'generated_sections' not in st.session_state:
        st.session_state.generated_sections = {}
    
    # Two-column layout
    col1, col2 = st.columns([1, 1])
    
    with col1:
        # Section selection and input
        st.subheader("Edit Resume Sections")
        current_section = st.selectbox(
            "Choose section to edit",
            ["Personal Information", "Professional Summary", "Work Experience", 
             "Education", "Skills", "Projects", "Certifications"]
        )
        
        # Template selection
        template = st.selectbox(
            "Choose Resume Template",
            ["modern", "classic"]
        )
        
        # Input area with guidelines
        st.markdown(f"### {current_section}")
        guidelines = {
            "Personal Information": "Enter: Full Name, Professional Title, Email, Phone, Location, LinkedIn URL",
            "Professional Summary": "Describe your professional background, key achievements, and career goals",
            "Work Experience": "For each position: Company, Title, Duration, Key Responsibilities and Achievements",
            "Skills": "List your technical skills, soft skills, and tools/technologies you're proficient in",
            "Education": "Degree, Institution, Graduation Date, GPA (if >3.5), Honors, Relevant Coursework",
            "Projects": "Project Name, Duration, Technologies Used, Description, Key Achievements",
            "Certifications": "Certification Name, Issuing Organization, Date, Credential ID"
        }
        
        st.info(guidelines.get(current_section, "Enter relevant details below"))
        user_input = st.text_area("Enter details", height=150)
        
        if st.button("Generate Section"):
            st.write("Generating content...")
            placeholder = st.empty()
            full_response = ""
            
            for chunk in builder.generate_resume_section(current_section, user_input):
                full_response += chunk
                placeholder.markdown(full_response)
            
            st.session_state.generated_sections[current_section] = full_response
            builder.resume_data[current_section] = {
                'input': user_input,
                'generated': full_response
            }
            builder.save_resume()
    
    with col2:
        # Preview and Export
        st.subheader("Resume Preview")
        for section, content in st.session_state.generated_sections.items():
            with st.expander(section, expanded=True):
                st.markdown(content)
        
        # Export options
        st.subheader("Export Options")
        col_txt, col_pdf = st.columns(2)
        
        with col_txt:
            if st.button("Export as Text"):
                timestamp = time.strftime("%Y%m%d-%H%M%S")
                filename = f"resume_{timestamp}.txt"
                
                with open(filename, "w") as f:
                    for section, content in st.session_state.generated_sections.items():
                        f.write(f"\n{section}\n{'='*len(section)}\n")
                        f.write(content + "\n")
                
                st.success(f"Resume exported as {filename}")
        
        with col_pdf:
            if st.button("Export as PDF"):
                timestamp = time.strftime("%Y%m%d-%H%M%S")
                filename = f"resume_{timestamp}.pdf"
                builder.create_pdf(filename, template)
                
                with open(filename, "rb") as f:
                    st.download_button(
                        label="Download PDF",
                        data=f.read(),
                        file_name=filename,
                        mime="application/pdf"
                    )

if __name__ == "__main__":
    main()
