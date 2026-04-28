#!/bin/bash
# Run AutoReturn with the new Orchestrator-Agent architecture

echo "Starting AutoReturn with Orchestrator-Agent Architecture..."
echo ""

# Check if virtual environment is activated
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo " Virtual environment not activated. Activating..."
    source .venv/bin/activate
fi

# Check if Ollama is running
echo "Checking if Ollama is running..."
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "Ollama is running"
else
    echo "Ollama is NOT running!"
    echo "   Please start Ollama in another terminal with:"
    echo "   ollama serve"
    echo ""
    read -p "Press Enter to continue anyway (AI features may not work) or Ctrl+C to exit..."
fi

echo ""
echo "Starting AutoReturn..."
echo ""

# Run the application
python main.py
