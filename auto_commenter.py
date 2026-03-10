import sys
import os
import ast

def generate_offline_comment(func_name: str) -> str:
    """Generate a clean 1-2 sentence description based on the function name."""
    if func_name == "__init__":
        return "Initializes the class instance and sets up default routing or UI states."
    
    # Remove leading/trailing underscores and split by underscores
    clean_name = func_name.strip('_')
    words = clean_name.split('_')
    
    if not words:
        return "Handles core execution and processing."
        
    action = words[0].lower()
    subject = " ".join(words[1:]) if len(words) > 1 else "the operation"
    
    # Map common verbs to more professional descriptions
    verb_map = {
        'get': 'Retrieves',
        'set': 'Assigns values for',
        'update': 'Refreshes or updates',
        'fetch': 'Pulls data for',
        'load': 'Loads data into',
        'save': 'Saves the current state of',
        'create': 'Instantiates and creates',
        'delete': 'Removes or deletes',
        'remove': 'Removes or unbinds',
        'add': 'Appends or registers',
        'handle': 'Processes and handles',
        'on': 'Event handler triggered when',
        'process': 'Executes processing logic for',
        'start': 'Initiates the process for',
        'stop': 'Terminates the process for',
        'check': 'Validates and checks',
        'is': 'Evaluates whether',
        'has': 'Checks if the system has',
        'generate': 'Creates and returns',
        'show': 'Displays the UI for',
        'hide': 'Conceals the UI for',
        'toggle': 'Switches the state of',
        'apply': 'Executes and applies',
        'clear': 'Resets and clears',
        'connect': 'Establishes connections for',
        'disconnect': 'Terminates connections for',
        'setup': 'Configures and sets up',
        'init': 'Initializes components for',
        'parse': 'Extracts and parses',
        'format': 'Formats output for',
        'validate': 'Ensures validity of',
        'route': 'Directs incoming traffic for'
    }
    
    start_word = verb_map.get(action, f"Handles {action} functionality for")
    
    # Fix grammar for event handlers
    if action == 'on':
        return f"{start_word} {subject}."
        
    return f"{start_word} {subject}."

def insert_comment_block(file_path: str, function_info: list):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    # Process from bottom to top so line numbers don't change
    function_info.sort(key=lambda x: x['lineno'], reverse=True)
    
    for info in function_info:
        line_idx = info['lineno'] - 1
        
        # Check if there is already a block
        has_block = False
        if line_idx >= 3:
            prev_lines = "".join(lines[line_idx-3:line_idx]).strip()
            if "# -------------------------" in prev_lines:
                has_block = True
                
        if has_block:
            continue
            
        comment_text = info['comment'].strip()
        lines_to_insert = [
            "# -------------------------\n",
            f"# {info['name'].replace('_', ' ').strip().upper()}\n"
        ]
        for line in comment_text.split('\n'):
            clean_line = line.strip()
            if clean_line:
                lines_to_insert.append(f"# {clean_line}\n")
        lines_to_insert.append("# -------------------------\n")
        
        # Determine indentation
        original_line = lines[line_idx]
        indent = len(original_line) - len(original_line.lstrip())
        indent_str = " " * indent
        
        formatted_insert = [indent_str + l for l in lines_to_insert]
        
        insert_idx = line_idx
        while insert_idx > 0 and lines[insert_idx-1].strip().startswith('@'):
            insert_idx -= 1
            
        while insert_idx > 0 and lines[insert_idx-1].strip().startswith('#') and not lines[insert_idx-1].strip().startswith('# ----'):
            insert_idx -= 1
            
        lines[insert_idx:insert_idx] = formatted_insert
        
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)

def generate_comments_for_funcs(file_path: str):
    with open(file_path, 'r', encoding='utf-8') as f:
        source = f.read()

    try:
        tree = ast.parse(source)
    except Exception as e:
        print(f"Skipping {file_path} due to syntax error: {e}")
        return

    funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    
    lines = source.splitlines()
    needs_comment = []
    
    for f_node in funcs:
        start_line = f_node.lineno - 1
        if f_node.decorator_list:
            start_line = f_node.decorator_list[0].lineno - 1
            
        while start_line > 0 and lines[start_line-1].strip().startswith('#') and "---" not in lines[start_line-1]:
            start_line -= 1
            
        has_header = False
        if start_line >= 1 and "# -------------------------" in lines[start_line-1]:
            has_header = True
        elif start_line >= 2 and "# -------------------------" in lines[start_line-2]:
            has_header = True
            
        if not has_header and not (f_node.name.startswith("__") and f_node.name != "__init__"):
            needs_comment.append({
                'lineno': f_node.lineno,
                'name': f_node.name,
                'comment': generate_offline_comment(f_node.name)
            })

    if not needs_comment:
        return
        
    insert_comment_block(file_path, needs_comment)
    print(f"Successfully added {len(needs_comment)} blocks to {os.path.basename(file_path)}!")

def main():
    targets = [
        'src/frontend/ui/autoreturn_app.py',
        'src/backend/core/draft_manager.py',
        'src/backend/core/automation_coordinator.py',
        'src/backend/core/event_extractor.py',
        'src/backend/core/reply_policy_engine.py',
        'src/backend/core/tone_engine.py',
        'src/backend/services/calendar_service.py',
        'src/backend/services/gmail_backend.py',
        'src/backend/services/slack_backend.py',
        'main.py'
    ]
    
    for t in targets:
        full_path = os.path.abspath(os.path.join(os.path.dirname(__file__), t))
        if os.path.exists(full_path):
            generate_comments_for_funcs(full_path)

if __name__ == '__main__':
    main()
