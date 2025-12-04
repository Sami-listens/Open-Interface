# Open Interface

**An AI-powered desktop automation and validation system for The Door Company**

Open Interface is a comprehensive desktop automation platform that combines vision-based GUI interaction, hardware validation, and intelligent workflow orchestration. It enables AI agents to interact with desktop applications (like CommSense), validate hardware configurations, and execute complex multi-phase workflows.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Key Components](#key-components)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [Configuration](#configuration)
- [Project Structure](#project-structure)
- [Hardware Validator](#hardware-validator)
- [Development](#development)
- [Troubleshooting](#troubleshooting)

---

## Overview

Open Interface provides three main capabilities:

1. **Desktop GUI Automation**: Vision-based AI agent that can interact with desktop applications using screenshots and spatial reasoning
2. **Hardware Validation**: AI-powered validation system for door and hardware configurations against company standards
3. **Workflow Orchestration**: LangGraph-based system for executing complex, multi-phase workflows

### Key Features

- 🖼️ **Vision-Based Automation**: Uses Gemini 2.5 Pro for spatial reasoning and UI element detection
- 🔍 **Hardware Validation**: Validates door schedules against TDC standards and project-specific requirements
- 🔄 **Workflow Orchestration**: LangGraph-based state machine for complex multi-step processes
- 📊 **Excel Integration**: Parses and processes Excel door schedules and project data
- 🧠 **Learning System**: Memory system that learns from user feedback to improve validation accuracy
- 🎯 **Hybrid Agent Architecture**: Combines planning (Gemini 2.5 Pro) with grounding (Gemini 2.0 Flash) for precise UI interaction

---

## Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Open Interface                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐    ┌──────────────────────────────┐ │
│  │  GUI Application │    │   LangGraph Interface         │ │
│  │  (Desktop UI)    │    │   (Workflow Orchestration)    │ │
│  └────────┬─────────┘    └───────────┬──────────────────┘ │
│           │                           │                      │
│           ▼                           ▼                      │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Core Engine                              │  │
│  │  • Screenshot Capture                                 │  │
│  │  • LLM Planning (Gemini 2.5 Pro)                      │  │
│  │  • Action Execution (PyAutoGUI)                       │  │
│  │  • Visual Verification                                │  │
│  └───────────┬──────────────────────────────────────────┘  │
│              │                                               │
│              ▼                                               │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         Hardware Validator                             │  │
│  │  • Rule Extraction (from PDFs)                        │  │
│  │  • Conflict Detection                                 │  │
│  │  • AI-Based Validation                                │  │
│  │  • Learning System                                    │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Core Flow

1. **User Request** → GUI or API receives request
2. **Planning** → LLM analyzes screenshot and plans actions
3. **Grounding** → LLM detects UI elements with bounding boxes
4. **Stabilization** → Visual feedback loop ensures cursor accuracy
5. **Execution** → PyAutoGUI performs actions
6. **Validation** → Results verified and feedback loop continues

---

## Key Components

### 1. Open Interface Core (`app/`)

The main desktop automation engine that uses vision-based AI to interact with GUI applications.

**Key Files:**
- `app/app.py` - Main application entry point
- `app/core.py` - Core automation engine
- `app/ui.py` - GUI interface
- `app/models/` - LLM model integrations (Gemini, GPT-4)

**Features:**
- Screenshot-based UI understanding
- Multi-step task planning
- Visual verification loop
- PyAutoGUI action execution

### 2. Hardware Validator (`hardware_validator/`)

AI-powered validation system for door and hardware configurations.

**Key Files:**
- `hardware_validator/engine.py` - Main validation orchestrator
- `hardware_validator/ai_evaluator.py` - LLM-based validation
- `hardware_validator/project_rule_generator.py` - Extracts rules from PDFs
- `hardware_validator/conflict_detector.py` - Detects rule conflicts
- `hardware_validator/api.py` - FastAPI dashboard server
- `hardware_validator/memory_system.py` - Learning from feedback

**Features:**
- Extracts validation rules from project specifications
- Validates against company standards (TDC rules)
- Detects conflicts between company and project rules
- Learns from estimator feedback
- Exports results in multiple formats (CSV, Excel, JSON)

### 3. LangGraph Interface (`langgraph_interface/`)

Workflow orchestration system using LangGraph state machines.

**Key Files:**
- `langgraph_interface/graph.py` - LangGraph workflow definition
- `langgraph_interface/nodes.py` - Workflow nodes
- `langgraph_interface/phased_coordinator_node.py` - Multi-phase workflow coordinator
- `langgraph_interface/comsense_editor_node.py` - CommSense integration
- `langgraph_interface/excel_parser_node.py` - Excel parsing

**Features:**
- State-based workflow execution
- Conditional routing
- Multi-phase workflow support
- Excel data processing
- CommSense integration

### 4. Comsense Agent (`comsense_agent_s3_hybrid.py`)

Specialized agent for interacting with CommSense software.

**Features:**
- Module detection (Doors/Frames/Hardware)
- Dynamic column learning
- Tab-based navigation
- Row position correction
- Field name mapping

---

## Installation

### Prerequisites

- Python 3.9+
- macOS (primary platform, Windows/Linux may work with modifications)
- Google Gemini API key (for AI features)

### Setup

1. **Clone the repository:**
```bash
cd /path/to/Open-Interface
```

2. **Create virtual environment:**
```bash
conda create -n open-interface python=3.9
conda activate open-interface
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Set up environment variables:**
Create a `.env` file in the project root:
```bash
GEMINI_API_KEY=your_api_key_here
GOOGLE_API_KEY=your_api_key_here  # Alternative name
GEMINI_MODEL=gemini-2.5-pro  # Optional, defaults to gemini-3-pro-preview
```

5. **Install system dependencies (macOS):**
```bash
# PyAutoGUI dependencies are included in requirements.txt
# For macOS, pyobjc packages are automatically installed
```

---

## Quick Start

### 1. Run the Desktop Application

```bash
python app/app.py
```

This launches the GUI application where you can:
- Enter natural language requests
- View real-time status updates
- See execution results

### 2. Run Hardware Validator Dashboard

```bash
cd hardware_validator
python api.py
```

Then open `http://localhost:8080` in your browser.

### 3. Run Comsense Agent

```bash
# Ensure CommSense is open with project loaded
python comsense_agent_s3_hybrid.py
```

### 4. Run LangGraph Workflow

```python
from langgraph_interface import OpenInterfaceGraph

graph = OpenInterfaceGraph()
result = graph.execute_request("Process Excel file and update CommSense")
```

---

## Usage

### Desktop Automation

**Basic Usage:**
```python
from app.app import App

app = App()
app.run()
```

**In the GUI:**
1. Enter your request (e.g., "Click the Save button")
2. The agent will:
   - Take a screenshot
   - Analyze the UI
   - Plan actions
   - Execute with visual verification
   - Report results

### Hardware Validation

**Via API:**
```bash
# Start validation for a project
curl -X POST http://localhost:8080/api/projects/my_project/start \
  -H "Content-Type: application/json" \
  -d '{
    "spec_pdf_path": "/path/to/spec.pdf",
    "door_schedule_path": "/path/to/door_schedule.csv",
    "project_name": "My Project"
  }'

# Check status
curl http://localhost:8080/api/projects/my_project/status

# Get validation results
curl http://localhost:8080/api/projects/my_project/validation
```

**Via Python:**
```python
from hardware_validator.engine import HardwareValidationEngine
from hardware_validator.parser import HardwareExportParser

# Parse door schedule
hw_sets = HardwareExportParser.parse_csv("door_schedule.csv")

# Validate
engine = HardwareValidationEngine()
reports = engine.validate_batch(hw_sets)

# Process results
for report in reports:
    print(f"Opening {report.set_id}: Score {report.score}")
    for issue in report.issues:
        print(f"  [{issue.level}] {issue.message}")
```

### LangGraph Workflows

**Simple Workflow:**
```python
from langgraph_interface import OpenInterfaceGraph

graph = OpenInterfaceGraph()
result = graph.execute_request("Take a screenshot and describe what you see")
```

**Phased Workflow:**
```python
# Create a phased workflow JSON file
workflow = {
    "phases": [
        {
            "name": "parse_excel",
            "description": "Parse Excel file for edits"
        },
        {
            "name": "apply_edits",
            "description": "Apply edits to CommSense"
        }
    ]
}

# Execute
state = {
    "phased_workflow_file": "workflows/my_workflow.json",
    "user_request": "Process project 206551"
}
result = graph.execute_request(state["user_request"])
```

### Comsense Agent

**Basic Usage:**
```python
from comsense_agent_s3_hybrid import ComsenseAgent

agent = ComsenseAgent()
edits = [
    {"opening": "102B", "field": "Ext", "value": "Y"}
]
agent.apply_edits(edits)
```

---

## Configuration

### Settings File

Location: `~/.open-interface/settings.json`

```json
{
  "model": "gemini-2.5-pro",
  "api_key": "your_api_key",
  "base_url": "https://generativelanguage.googleapis.com/v1beta/",
  "custom_llm_instructions": "You are a helpful assistant..."
}
```

### Hardware Validator Configuration

**TDC Rules**: Embedded in `hardware_validator/ai_evaluator.py` (lines 69-230)

**Project Rules**: Extracted automatically from PDF specifications

**Memory System**: Stored in `hardware_validator/validation_memory.db`

### Model Configuration

**Available Models:**
- `gemini-3-pro-preview` (default for AI evaluator)
- `gemini-2.5-pro` (planning)
- `gemini-2.5-flash` (fast operations)
- `gemini-2.0-flash` (grounding)

**Fallback Chain:**
The system automatically falls back to alternative models if the primary fails:
1. Primary model
2. `gemini-2.5-pro`
3. `gemini-2.5-flash`
4. `gemini-2.0-flash`

---

## Project Structure

```
Open-Interface/
├── app/                          # Main desktop application
│   ├── app.py                    # Entry point
│   ├── core.py                   # Core automation engine
│   ├── ui.py                     # GUI interface
│   ├── models/                   # LLM model integrations
│   │   ├── gemini.py
│   │   └── gpt4o.py
│   └── utils/                    # Utility functions
│
├── hardware_validator/           # Hardware validation system
│   ├── engine.py                 # Main orchestrator
│   ├── ai_evaluator.py           # LLM-based validation
│   ├── project_rule_generator.py # Rule extraction
│   ├── conflict_detector.py      # Conflict detection
│   ├── parser.py                 # CSV/Excel parsing
│   ├── api.py                    # FastAPI dashboard
│   ├── memory_system.py          # Learning system
│   └── dashboard/                # Web dashboard
│
├── langgraph_interface/          # Workflow orchestration
│   ├── graph.py                  # LangGraph definition
│   ├── nodes.py                  # Workflow nodes
│   ├── phased_coordinator_node.py # Multi-phase coordinator
│   ├── comsense_editor_node.py   # CommSense integration
│   └── excel_parser_node.py      # Excel processing
│
├── comsense_agent_s3_hybrid.py   # CommSense agent
├── agent_s3_comsense_reconcile.py # Reconciliation agent
├── requirements.txt              # Python dependencies
├── AGENT_USAGE.txt               # Agent documentation
└── README.md                     # This file
```

---

## Hardware Validator

### Architecture

The Hardware Validator uses a dual-validation approach:

1. **Rule-Based Checks**: Fast, local pattern matching
2. **AI-Based Evaluation**: Comprehensive LLM analysis with all rules in context

### Workflow

```
1. Input Processing
   ├─ Parse door schedule (CSV/Excel)
   └─ Extract project rules from PDF

2. Rule Management
   ├─ Load TDC company rules
   ├─ Extract project-specific rules (LLM)
   └─ Detect conflicts (LLM)

3. Human Review
   └─ Approve rule preferences (TDC vs Project)

4. Validation
   ├─ Rule-based checks (fast)
   ├─ AI-based evaluation (comprehensive)
   └─ Memory system (learned corrections)

5. Output
   ├─ Validation reports
   ├─ Annotated CSV
   ├─ Excel export (CommSense format)
   └─ JSON API responses
```

### Key Features

- **Single Batch AI Call**: Processes all openings in one LLM request for efficiency
- **Conflict Detection**: Intelligently identifies genuine conflicts between rule sets
- **Learning System**: Improves accuracy from estimator feedback
- **Multiple Export Formats**: CSV, Excel, JSON for different use cases

### API Endpoints

- `POST /api/projects/{project_id}/start` - Start validation
- `GET /api/projects/{project_id}/rules` - Get rules and conflicts
- `POST /api/projects/{project_id}/rules/approve` - Approve rules
- `GET /api/projects/{project_id}/validation` - Get results
- `POST /api/projects/{project_id}/feedback` - Submit feedback
- `GET /api/projects/{project_id}/export` - Export results

See `hardware_validator/api.py` for complete API documentation.

---

## Development

### Running Tests

```bash
# Test hardware validator
python hardware_validator/test_integration.py
python hardware_validator/test_combined_validation.py

# Test Excel parser
python test_excel_parser.py

# Test Comsense agent
python test_comsense_hybrid.py

# Test Gemini API
python test_gemini_api.py
```

### Adding New Models

1. Create model class in `app/models/`
2. Implement `Model` interface
3. Register in `app/models/factory.py`

### Extending Hardware Validator

1. **Add TDC Rules**: Edit `hardware_validator/ai_evaluator.py` (TDC_HARDWARE_RULES)
2. **Custom Rule Extraction**: Modify `project_rule_generator.py` prompts
3. **New Validation Checks**: Add to `hardware_validator/rules.py`

### Building Distribution

```bash
python build.py
```

This creates a macOS application bundle in `dist/`.

---

## Troubleshooting

### Common Issues

**1. "No API Key found"**
- Ensure `.env` file exists with `GEMINI_API_KEY`
- Check environment variables are loaded

**2. "PyAutoGUI not working"**
- On macOS, ensure accessibility permissions are granted
- System Preferences → Security & Privacy → Accessibility

**3. "Hardware validation fails"**
- Check door schedule format matches expected structure
- Verify PDF spec file is readable
- Check API key is valid

**4. "Comsense agent clicks wrong element"**
- Adjust `convergence_threshold` in agent code
- Increase `max_attempts` for stabilization
- Add more specific spatial hints

**5. "LangGraph workflow hangs"**
- Check state transitions in workflow JSON
- Verify all required state fields are present
- Review node execution logs

### Debug Mode

Enable verbose logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Getting Help

- Check `AGENT_USAGE.txt` for agent-specific documentation
- Review error logs in `hardware_validator/validation_logs.db`
- Check memory system: `hardware_validator/validation_memory.db`

---

## License

Proprietary - The Door Company

---

## Contributors

- The Door Company Development Team

---

## Version History

- **v0.9.0** - Initial release with hardware validator and desktop automation
- **v1.0.0** - Added LangGraph workflow orchestration and learning system

---

## Additional Resources

- **Agent Documentation**: See `AGENT_USAGE.txt`
- **Hardware Validator**: See `hardware_validator/` directory
- **Workflow Examples**: See `workflows/` directory
- **Project Examples**: See `Project Example - THM WWTP/` directory

---

**For questions or support, contact The Door Company development team.**

