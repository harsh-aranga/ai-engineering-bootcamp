# AI Engineering Bootcamp — Hands-On Code

Code companion to the AI Engineering bootcamp notes. Working implementations, experiments, and mini-builds.

## Setup

### Prerequisites
- Python 3.11+
- API keys for OpenAI and Anthropic

### Installation
```bash
# Navigate to this directory
cd 4_Hands_On_Code

# Create virtual environment
python3.11 -m venv venv

# Activate it
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Install common/ as editable package (required for imports to work)
pip install -e .
```

### Environment Variables

Copy the example file and add your keys:
```bash
cp .env.example .env
```

Edit `.env` with your API keys:
```
OPEN_AI_KEY=sk-your-key-here
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

## Structure
```
4_Hands_On_Code/
├── common/                  # Shared utilities
│   ├── config.py            # .env loader
│   ├── constants.py         # Hardcoded values (models, limits)
│   └── logger.py            # Auto-structured logging
├── logs/                    # Generated logs (git-ignored)
├── week01_foundations/
│   ├── topic1_tokenization/
│   ├── topic2_embeddings/
│   └── topic3_prompt_engineering/
├── week03_rag/
├── week03_agents/
├── pyproject.toml           # Editable package config
└── .env                     # API keys (git-ignored)
```

## Using `common/`

### Config (API Keys)
```python
from common.config import get_config

config = get_config()
api_key = config.get("OPEN_AI_KEY")  # Raises KeyError if missing
```

### Constants
```python
from common.constants import DEFAULT_MODEL, MAX_CONTEXT_TOKENS
```

### Logger
```python
from common.logger import get_logger

logger = get_logger(__file__)
logger.info("Starting experiment")
```

Run with optional message for log filename:
```bash
python my_script.py --run_message="testing chunking with 512 tokens"
```

Creates: `logs/<path>/<script>/<date>/<script>_<message>_<timestamp>.log`

## Running Examples

Each topic folder contains runnable Python scripts:
```bash
python week01_foundations/topic1_tokenization/example_script.py
```

*See the notes project for theory and concepts.*