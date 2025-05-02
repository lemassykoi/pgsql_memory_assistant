# PGSQL Memory Assistant

We're building an AI Agent with human-like memory which integrates PostgreSQL long-term memory backend with Microsoft's AutoGen framework, enabling agents to retain, recall, and manage contextual memory across conversations—paving the way for more intelligent, personalized, and persistent multi-agent interactions.

We use:

- Local PostgreSQL instance for the memory layer to AI agent
- Autogen (Agent Orchestration)
- Ollama as Model Provider
- Qwen 3 (LLM)
- Streamlit to wrap the logic in an interactive UI

## Set Up

Run these commands in project root

### Setting up Ollama

```bash
# Setting up Ollama on linux
curl -fsSL https://ollama.com/install.sh | sh

# Pull the Qwen 3 4B model
ollama pull qwen3:latest
```

### Install Dependencies

```bash
pip install ag2[ollama] streamlit
```

### Run the Application

Run the application with:

```bash
streamlit run app.py
```

## Contribution

Contributions are welcome! Feel free to fork this repository and submit pull requests with your improvements.


## Forked

Forked from https://github.com/patchy631/ai-engineering-hub/tree/main/zep-memory-assistant
