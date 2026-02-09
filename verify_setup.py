#!/usr/bin/env python3
"""
Quick verification script to check if everything is set up correctly.
"""
import sys
import os

print("=" * 70)
print("🔍 AUTORETURN ARCHITECTURE VERIFICATION")
print("=" * 70)

errors = []
warnings = []
successes = []

# Check 1: Virtual environment
print("\n1️⃣  Checking virtual environment...")
if sys.prefix != sys.base_prefix:
    successes.append("✅ Virtual environment is activated")
else:
    warnings.append("⚠️  Virtual environment not activated (may cause import issues)")

# Check 2: Required dependencies
print("\n2️⃣  Checking dependencies...")
required_packages = ['pydantic', 'pydantic_ai', 'PySide6', 'requests', 'slack_sdk']
for package in required_packages:
    try:
        __import__(package)
        successes.append(f"✅ {package} installed")
    except ImportError:
        errors.append(f"❌ {package} NOT installed")

# Check 3: Backend structure
print("\n3️⃣  Checking backend structure...")
backend_files = [
    'src/backend/core/orchestrator.py',
    'src/backend/agents/gmail_agent.py',
    'src/backend/agents/slack_agent.py',
    'src/backend/models/agent_models.py',
]
for file in backend_files:
    if os.path.exists(file):
        successes.append(f"✅ {file} exists")
    else:
        errors.append(f"❌ {file} NOT found")

# Check 4: Can import orchestrator
print("\n4️⃣  Checking orchestrator import...")
try:
    from src.backend.core.orchestrator import Orchestrator
    successes.append("✅ Orchestrator can be imported")
except Exception as e:
    errors.append(f"❌ Cannot import Orchestrator: {e}")

# Check 5: Can import UI
print("\n5️⃣  Checking UI import...")
try:
    from src.frontend.ui.autoreturn_app import AutoReturnApp
    successes.append("✅ AutoReturnApp can be imported")
except Exception as e:
    errors.append(f"❌ Cannot import AutoReturnApp: {e}")

# Check 6: Ollama connection
print("\n6️⃣  Checking Ollama...")
try:
    import requests
    response = requests.get("http://localhost:11434/api/tags", timeout=2)
    if response.status_code == 200:
        successes.append("✅ Ollama is running and accessible")
    else:
        warnings.append("⚠️  Ollama responded with unexpected status")
except:
    warnings.append("⚠️  Ollama is NOT running (AI features won't work)")

# Print results
print("\n" + "=" * 70)
print("📊 VERIFICATION RESULTS")
print("=" * 70)

if successes:
    print("\n✅ SUCCESSES:")
    for msg in successes:
        print(f"   {msg}")

if warnings:
    print("\n⚠️  WARNINGS:")
    for msg in warnings:
        print(f"   {msg}")

if errors:
    print("\n❌ ERRORS:")
    for msg in errors:
        print(f"   {msg}")

print("\n" + "=" * 70)
if errors:
    print("❌ VERIFICATION FAILED - Please fix errors above")
    print("=" * 70)
    sys.exit(1)
elif warnings:
    print("⚠️  VERIFICATION PASSED WITH WARNINGS")
    print("   App should run, but some features may not work")
    print("=" * 70)
    sys.exit(0)
else:
    print("✅ VERIFICATION SUCCESSFUL - Ready to run!")
    print("   Run the app with: ./run.sh or python main.py")
    print("=" * 70)
    sys.exit(0)
