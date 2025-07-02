import json
import textwrap

from google.adk.agents import Agent, SequentialAgent, LoopAgent
from google.adk.tools import google_search, ToolContext
from typing import List, Dict
from fpdf import FPDF
from google.adk.tools.agent_tool import AgentTool
from google.genai import types


async def create_pdf(sections: str, filename: str,  tool_context: ToolContext) -> dict:
    """
    Create a PDF document from a JSON string of research paper sections.

    Args:
        sections (str): JSON string containing keys like 'Abstract', 'Introduction', etc.
        tool_context (ToolContext): Tool context for saving the PDF artifact.

    Returns:
        dict: Status and message.
    """
    try:
        # Parse JSON string to dict
        sections_dict: Dict[str, str] = json.loads(sections)

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)

        for section_title, section_text in sections_dict.items():
            # Add section title
            pdf.set_font("Arial", style='B', size=14)
            pdf.cell(0, 10, text=section_title, ln=True)
            pdf.ln(1)

            # Add section content (wrapped)
            pdf.set_font("Arial", size=12)
            wrapped_text = "\n".join(textwrap.wrap(section_text, width=100))
            pdf.multi_cell(0, 10, text=wrapped_text)
            pdf.ln(5)

        # Output PDF as bytes
        pdf_str = pdf.output(dest='S')
        pdf_output = pdf_str.encode('latin1') if isinstance(pdf_str, str) else bytes(pdf_str)

        # Optional: Save locally for debug
        with open(filename, "wb") as f:
            f.write(pdf_output)

        # Save artifact
        await tool_context.save_artifact(
            filename,
            types.Part.from_bytes(data=pdf_output, mime_type="application/pdf")
        )

        return {
            "status": "success",
            "message": "PDF created successfully."
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to create PDF: {str(e)}"
        }

search_agent = Agent(
    model='gemini-2.0-flash-001',
    name='search_agent',
    description='A helpful assistant for searching the web.',
    instruction=(
        'Use the Google Search tool to find relevant information on the web.'
        "if any feedback is provided, refine the search query accordingly and"
        "return the search results and references."
    ),
    tools=[google_search],
    output_key='search_results',
)

student_agent = Agent(
    model='gemini-2.0-flash-001',
    name='student_agent',
    description='A helpful assistant for researching topics.',
    instruction=(
        "You are a research assistant agent. Your task is to generate a high-quality academic paper based on the provided search results. "
        "Extract key information and insights relevant to the research topic. "
        "If additional information is required, provide feedback to the search agent to refine the query. "
        "The final paper should be at least 1000 words and written at a level suitable for submission to a top-tier conference. "
        "Structure the output as a JSON object, where each key corresponds to a standard section of a research paper: "
        "`Abstract`, `Introduction`, `Methodology`, `Results`, `Discussion`, and `Conclusion`. "
        "Each section should contain well-developed, original text appropriate to its purpose."
    ),
    output_key='paper_content',
)

postdoc_agent = LoopAgent(
    name='postdoc_agent',
    description='A loop agent that coordinates the search and research agents.',
    max_iterations=3,
    sub_agents=[search_agent, student_agent]
)

postdoc_agent_tool = AgentTool(agent=postdoc_agent)

root_agent = Agent(
    model='gemini-2.0-flash-001',
    name='paper_writer_agent',
    description='A helpful assistant for writing research papers.',
    instruction=(
        'You are a paper writing assistant. Your task is to compile the research findings into a well-structured academic paper. '
        'Use the provided research content to create a coherent and comprehensive document. '
        "To grab the research content, use the Postdoc Agent tool. "
        'Once you have the content, format it into a PDF document with appropriate sections and references. '
        'Finally, save the PDF document as an artifact named "final_paper.pdf".'
    ),
    tools=[postdoc_agent_tool, create_pdf],
)


