#!/usr/bin/env python3
"""
AutoReturn AppImage Entry Point
Handles path setup for AppImage environment before launching the app.
"""

import sys
import os

# When running as AppImage, set up paths correctly
if os.environ.get('APPIMAGE'):
    # We're running inside an AppImage
    appdir = os.environ.get('APPDIR', os.path.dirname(os.path.abspath(__file__)))
    
    # Set up user data directory in home folder (not inside AppImage - it's read-only)
    home_dir = os.path.expanduser('~')
    user_data_dir = os.path.join(home_dir, '.autoreturn')
    os.makedirs(user_data_dir, exist_ok=True)
    
    # Sub-directories
    for subdir in ['data', 'data/gmail_data', 'data/ics_exports', 'logs', 'config']:
        os.makedirs(os.path.join(user_data_dir, subdir), exist_ok=True)
    
    # Copy default config files if they don't exist yet
    bundled_config = os.path.join(appdir, 'usr', 'src', 'config')
    user_config = os.path.join(user_data_dir, 'config')
    
    for config_file in ['settings.conf', 'tone_detection_rules.json']:
        src = os.path.join(bundled_config, config_file)
        dst = os.path.join(user_config, config_file)
        if os.path.exists(src) and not os.path.exists(dst):
            import shutil
            shutil.copy2(src, dst)
    
    # Copy default data files if they don't exist yet
    bundled_data = os.path.join(appdir, 'usr', 'src', 'data')
    user_data = os.path.join(user_data_dir, 'data')
    
    for data_file in ['automation_settings.json', 'priority_dataset.json', 'tone_profile.json']:
        src = os.path.join(bundled_data, data_file)
        dst = os.path.join(user_data, data_file)
        if os.path.exists(src) and not os.path.exists(dst):
            import shutil
            shutil.copy2(src, dst)
    
    # Set working directory to user data dir so relative paths work
    os.chdir(user_data_dir)
    
    # Add app source to path
    app_src = os.path.join(appdir, 'usr', 'src')
    if app_src not in sys.path:
        sys.path.insert(0, app_src)

else:
    # Running normally (not AppImage) - standard path setup
    project_root = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, project_root)

# Now launch the actual app
from main import main
main()
