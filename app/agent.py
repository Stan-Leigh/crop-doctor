# ruff: noqa
import os
import re
import json
import datetime
from google.adk.agents import LlmAgent
from google.adk.apps import App, ResumabilityConfig
from google.adk.models import Gemini
from google.adk.tools import AgentTool
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters
from google.adk.workflow import Workflow, START, node
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput
from google.adk.agents.context import Context
from google.genai import types

from app.config import config

# Model initialization
model_obj = Gemini(
    model=config.model,
    retry_options=types.HttpRetryOptions(attempts=3),
)

# Helper function to extract text from Event/Content
def extract_text_from_content(content) -> str:
    if not content:
        return ""
    if hasattr(content, "parts") and content.parts:
        return "".join(part.text for part in content.parts if part.text)
    if hasattr(content, "output") and content.output:
        return extract_text_from_content(content.output)
    if isinstance(content, dict):
        return content.get("output", str(content))
    return str(content)

# Initialize MCP Toolset pointing to app/mcp_server.py
current_dir = os.path.dirname(os.path.abspath(__file__))
mcp_server_path = os.path.join(current_dir, "mcp_server.py")

mcp_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="uv",
            args=["run", "python3", mcp_server_path],
        ),
    ),
)

# 1. Specialized Sub-agents
diagnostician = LlmAgent(
    name="diagnostician",
    model=model_obj,
    instruction="""You are a Crop Diagnostician. 
Given the user's description of plant symptoms, soil pH, moisture, and location, identify:
1. The most likely disease or deficiency.
2. A confidence score (0-100%).
3. A brief explanation of why.
Use the get_soil_metrics and get_local_weather_forecast tools from the MCP server to gather context when the location or soil parameters are mentioned.
Be concise and structured in your diagnosis.""",
    description="Diagnoses plant health issues and identifies potential diseases from symptoms, soil, and weather inputs.",
    tools=[mcp_toolset],
)

treatment_specialist = LlmAgent(
    name="treatment_specialist",
    model=model_obj,
    instruction="""You are an Organic Treatment Specialist.
Given a plant disease diagnosis, recommend:
1. Effective organic/natural treatments.
2. Preventative measures to avoid recurrence.
3. Watering, light, or soil adjustments.
Use the search_treatment_database tool from the MCP server to find organic treatments for the diagnosed disease.
Be practical, eco-friendly, and concise.""",
    description="Recommends organic remedies and preventative measures for a diagnosed plant disease.",
    tools=[mcp_toolset],
)

# 2. Orchestrator Agent
orchestrator = LlmAgent(
    name="orchestrator",
    model=model_obj,
    instruction="""You are the Crop Doctor Orchestrator.
You coordinate plant diagnosis and treatment recommendations by delegating to specialized agents.
- If you need to diagnose a plant, delegate to the 'diagnostician' tool.
- If you need to recommend treatments for a disease, delegate to the 'treatment_specialist' tool.
Always explain your reasoning and present the tool outputs clearly.""",
    tools=[AgentTool(diagnostician), AgentTool(treatment_specialist)],
)

# 3. Workflow Function Nodes
@node
def security_checkpoint(ctx: Context, node_input: types.Content) -> Event:
    text = extract_text_from_content(node_input)
    
    # 1. PII Scrubbing (Email, Phone, Zip Code)
    email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
    phone_pattern = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
    zip_pattern = r'\b\d{5}(-\d{4})?\b'
    
    scrubbed_text = text
    scrubbed_text = re.sub(email_pattern, "[EMAIL_REDACTED]", scrubbed_text)
    scrubbed_text = re.sub(phone_pattern, "[PHONE_REDACTED]", scrubbed_text)
    scrubbed_text = re.sub(zip_pattern, "[LOCATION_REDACTED]", scrubbed_text)
    
    was_scrubbed = (scrubbed_text != text)
    
    # 2. Prompt Injection Keyword Detection
    injection_keywords = [
        "ignore previous instructions", 
        "system prompt", 
        "bypass security", 
        "override rules", 
        "developer mode",
        "dan mode",
        "jailbreak"
    ]
    
    has_injection = any(kw in text.lower() for kw in injection_keywords)
    
    # 3. Domain-Specific Rule: restricted chemical pesticides
    restricted_substances = ["ddt", "aldrin", "paraquat", "heptachlor", "dieldrin"]
    has_restricted = any(re.search(rf"\b{sub}\b", text.lower()) for sub in restricted_substances)

    # 4. Structured JSON Audit Log
    log_data = {
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "event": "security_checkpoint_evaluation",
        "pii_scrubbed": was_scrubbed,
        "prompt_injection_detected": has_injection,
        "restricted_substances_detected": has_restricted,
    }
    
    if has_injection:
        log_data["status"] = "flagged"
        log_data["severity"] = "CRITICAL"
        log_data["reason"] = "Prompt injection attempt detected"
        print(json.dumps(log_data))
        return Event(output="CRITICAL_SECURITY_EVENT: Prompt injection detected", route="flagged")
        
    if has_restricted:
        log_data["status"] = "flagged"
        log_data["severity"] = "WARNING"
        log_data["reason"] = "Query mentions restricted chemical substances"
        print(json.dumps(log_data))
        return Event(output="WARNING_SECURITY_EVENT: Restrained substance inquiry", route="flagged")
        
    log_data["status"] = "clean"
    log_data["severity"] = "INFO"
    print(json.dumps(log_data))
    
    return Event(output=scrubbed_text, route="clean")

@node(rerun_on_resume=True)
async def diagnose_node(ctx: Context, node_input: str) -> Event:
    ctx.state["user_query"] = node_input
    prompt = f"Identify the plant issue for: {node_input}"
    
    # Run orchestrator to delegate to diagnostician
    response = await ctx.run_node(orchestrator, node_input=prompt)
    diagnosis_text = extract_text_from_content(response)
    ctx.state["diagnosis"] = diagnosis_text
    
    return Event(output=diagnosis_text)

@node(rerun_on_resume=True)
async def expert_review(ctx: Context, node_input: str):
    if not ctx.resume_inputs:
        yield RequestInput(
            interrupt_id="review_diagnosis",
            message=f"Proposed Diagnosis:\n{node_input}\n\nDo you agree with this diagnosis? Reply with 'yes' or specify corrections."
        )
        return

    user_response = ctx.resume_inputs.get("review_diagnosis", "").strip()
    if user_response.lower() in ["yes", "y", "agree", "correct"]:
        yield Event(output=node_input, route="approved")
    else:
        ctx.state["corrections"] = user_response
        yield Event(output=user_response, route="correction")

@node(rerun_on_resume=True)
async def treatment_node(ctx: Context, node_input: str) -> Event:
    prompt = f"Provide organic treatment recommendations for: {node_input}"
    
    # Run orchestrator to delegate to treatment_specialist
    response = await ctx.run_node(orchestrator, node_input=prompt)
    treatment_text = extract_text_from_content(response)
    ctx.state["treatment"] = treatment_text
    
    return Event(output=treatment_text)

@node(rerun_on_resume=True)
async def correction_node(ctx: Context, node_input: str) -> Event:
    original_query = ctx.state.get("user_query", "")
    prompt = f"The user reported: {original_query}. The diagnosis was corrected to: {node_input}. Recommend organic treatments for this corrected case."
    
    # Run orchestrator to get updated recommendation
    response = await ctx.run_node(orchestrator, node_input=prompt)
    updated_text = extract_text_from_content(response)
    ctx.state["treatment"] = updated_text
    
    return Event(output=updated_text)

@node
def security_error_node(ctx: Context, node_input: str) -> Event:
    error_msg = "Security block: Your query contains flagged content or potential injection. Please submit a valid plant health query."
    return Event(output=error_msg)

@node
def final_response(ctx: Context, node_input: str):
    # Render final output in the Web UI
    yield Event(content=types.Content(role='model', parts=[types.Part.from_text(text=node_input)]))
    yield Event(output=node_input)

# 4. Workflow Definition
app_workflow = Workflow(
    name="crop_doctor_workflow",
    edges=[
        (START, security_checkpoint),
        (security_checkpoint, {"clean": diagnose_node, "flagged": security_error_node}),
        (diagnose_node, expert_review),
        (expert_review, {"approved": treatment_node, "correction": correction_node}),
        (treatment_node, final_response),
        (correction_node, final_response),
        (security_error_node, final_response),
    ],
)

app = App(
    root_agent=app_workflow,
    name="app",
    resumability_config=ResumabilityConfig(is_resumable=True),
)

root_agent = app_workflow
