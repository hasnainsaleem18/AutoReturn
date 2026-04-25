#!/bin/bash
# ==============================================
# AutoReturn AppImage Builder
# ==============================================

set -e  # Exit on any error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$PROJECT_ROOT/build_appimage"
APPDIR="$BUILD_DIR/AutoReturn.AppDir"

echo "=============================================="
echo "  AutoReturn AppImage Builder"
echo "=============================================="
echo ""

# -----------------------------------------------
# STEP 1: Check prerequisites
# -----------------------------------------------
echo "[1/7] Checking prerequisites..."

if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 not found"
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "  Python: $PYTHON_VERSION"

if ! command -v pip3 &> /dev/null && ! python3 -m pip --version &> /dev/null; then
    echo "ERROR: pip not found"
    exit 1
fi

# Check for appimagetool
if command -v appimagetool &> /dev/null; then
    APPIMAGETOOL="appimagetool"
elif [ -f "/usr/local/bin/appimagetool" ]; then
    APPIMAGETOOL="/usr/local/bin/appimagetool"
else
    echo "ERROR: appimagetool not found!"
    echo ""
    echo "Install it permanently with one of:"
    echo "  Arch/Garuda:  yay -S appimagetool-bin"
    echo "  Or manually:  sudo wget -O /usr/local/bin/appimagetool https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage && sudo chmod +x /usr/local/bin/appimagetool"
    echo ""
    exit 1
fi

echo "  All prerequisites OK"
echo ""

# -----------------------------------------------
# STEP 2: Clean previous build
# -----------------------------------------------
echo "[2/7] Cleaning previous build..."
rm -rf "$BUILD_DIR"
mkdir -p "$APPDIR"
echo "  Done"
echo ""

# -----------------------------------------------
# STEP 3: Create AppDir structure
# -----------------------------------------------
echo "[3/7] Creating AppDir structure..."

mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/src"
mkdir -p "$APPDIR/usr/lib"
mkdir -p "$APPDIR/usr/share/applications"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"

echo "  Done"
echo ""

# -----------------------------------------------
# STEP 4: Copy application source
# -----------------------------------------------
echo "[4/7] Copying application source..."

# Copy main source files
cp "$PROJECT_ROOT/main.py" "$APPDIR/usr/src/"
cp -r "$PROJECT_ROOT/src" "$APPDIR/usr/src/"
cp -r "$PROJECT_ROOT/config" "$APPDIR/usr/src/"
cp -r "$PROJECT_ROOT/data" "$APPDIR/usr/src/"

# Copy .env file (Supabase credentials)
if [ -f "$PROJECT_ROOT/.env" ]; then
    cp "$PROJECT_ROOT/.env" "$APPDIR/usr/src/"
    echo "  Copied .env (Supabase credentials)"
fi

echo "  Source files copied"
echo ""

# -----------------------------------------------
# STEP 5: Install Python dependencies
# -----------------------------------------------
echo "[5/7] Installing Python dependencies into AppDir..."

SITE_PACKAGES="$APPDIR/usr/lib/python${PYTHON_VERSION}/site-packages"
mkdir -p "$SITE_PACKAGES"

pip3 install \
    --target="$SITE_PACKAGES" \
    -r "$SCRIPT_DIR/requirements-appimage.txt" \
    --quiet

echo "  Installing spaCy model..."
python3 -m spacy download en_core_web_md --quiet 2>/dev/null || true

# Copy spaCy model into AppDir - find it wherever pip installed it
echo "  Bundling spaCy en_core_web_md model..."
SPACY_MODEL_PATH=$(python3 -c "
import importlib, os
try:
    import en_core_web_md
    print(os.path.dirname(en_core_web_md.__file__))
except:
    pass
" 2>/dev/null)

if [ -n "$SPACY_MODEL_PATH" ] && [ -d "$SPACY_MODEL_PATH" ]; then
    cp -r "$SPACY_MODEL_PATH" "$SITE_PACKAGES/en_core_web_md"
    echo "  spaCy model bundled from: $SPACY_MODEL_PATH"
else
    # Try finding it in the target site-packages after pip install
    MODEL_IN_TARGET=$(find "$SITE_PACKAGES" -maxdepth 2 -name "en_core_web_md" -type d 2>/dev/null | head -1)
    if [ -n "$MODEL_IN_TARGET" ]; then
        echo "  spaCy model already in AppDir: $MODEL_IN_TARGET"
    else
        echo "  WARNING: en_core_web_md not found. Run: python3 -m spacy download en_core_web_md"
    fi
fi

echo "  Dependencies installed"
echo ""

# -----------------------------------------------
# STEP 6: Create launcher and AppRun
# -----------------------------------------------
echo "[6/7] Creating launcher scripts..."

# Copy entrypoint
cp "$SCRIPT_DIR/entrypoint.py" "$APPDIR/usr/src/"

# Create the AppRun script (main launcher)
cat > "$APPDIR/AppRun" << APPRUN_EOF
#!/bin/bash
# AutoReturn AppImage Launcher

APPDIR="\$(dirname "\$(readlink -f "\$0")")"
export APPDIR

# Detect Python version
PY_VER=\$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "3.12")

# Set up Python path
export PYTHONPATH="\$APPDIR/usr/src:\$APPDIR/usr/lib/python\${PY_VER}/site-packages:\$PYTHONPATH"

# Set up library path for Qt/PySide6
export LD_LIBRARY_PATH="\$APPDIR/usr/lib:\$APPDIR/usr/lib/python\${PY_VER}/site-packages/PySide6:\$LD_LIBRARY_PATH"

# Qt platform settings
export QT_QPA_PLATFORM_PLUGIN_PATH="\$APPDIR/usr/lib/python\${PY_VER}/site-packages/PySide6/Qt/plugins/platforms"
export QT_PLUGIN_PATH="\$APPDIR/usr/lib/python\${PY_VER}/site-packages/PySide6/Qt/plugins"

# Set user data directory
export AUTORETURN_DATA_DIR="\$HOME/.autoreturn"

# Find Python
if command -v python3 &> /dev/null; then
    PYTHON="python3"
elif command -v python &> /dev/null; then
    PYTHON="python"
else
    zenity --error --text="Python 3 is required but not found on this system." 2>/dev/null || \
    echo "ERROR: Python 3 is required but not found."
    exit 1
fi

# Launch the app
exec "\$PYTHON" "\$APPDIR/usr/src/entrypoint.py" "\$@"
APPRUN_EOF

chmod +x "$APPDIR/AppRun"

# Copy desktop file
cp "$SCRIPT_DIR/AutoReturn.desktop" "$APPDIR/"
cp "$SCRIPT_DIR/AutoReturn.desktop" "$APPDIR/usr/share/applications/"

# Copy icon - use custom SVG, convert to PNG if possible
if [ -f "$SCRIPT_DIR/autoreturn.svg" ]; then
    # Create icon directories first
    mkdir -p "$APPDIR/usr/share/icons/hicolor/scalable/apps"
    mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"

    cp "$SCRIPT_DIR/autoreturn.svg" "$APPDIR/autoreturn.svg"
    cp "$SCRIPT_DIR/autoreturn.svg" "$APPDIR/usr/share/icons/hicolor/scalable/apps/autoreturn.svg"

    # Try converting SVG to PNG using available tools
    if command -v rsvg-convert &> /dev/null; then
        rsvg-convert -w 256 -h 256 "$SCRIPT_DIR/autoreturn.svg" \
            -o "$APPDIR/usr/share/icons/hicolor/256x256/apps/autoreturn.png"
        cp "$APPDIR/usr/share/icons/hicolor/256x256/apps/autoreturn.png" "$APPDIR/autoreturn.png"
        echo "  Icon converted to PNG via rsvg-convert"
    elif command -v inkscape &> /dev/null; then
        inkscape --export-type=png --export-width=256 --export-height=256 \
            --export-filename="$APPDIR/autoreturn.png" "$SCRIPT_DIR/autoreturn.svg" 2>/dev/null
        cp "$APPDIR/autoreturn.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/autoreturn.png"
        echo "  Icon converted to PNG via inkscape"
    elif command -v convert &> /dev/null; then
        convert -background none -resize 256x256 \
            "$SCRIPT_DIR/autoreturn.svg" "$APPDIR/autoreturn.png" 2>/dev/null
        cp "$APPDIR/autoreturn.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/autoreturn.png"
        echo "  Icon converted to PNG via ImageMagick"
    else
        # Fallback: use existing asset
        if [ -f "$PROJECT_ROOT/src/frontend/assets/Gmail_Logo_32px.png" ]; then
            cp "$PROJECT_ROOT/src/frontend/assets/Gmail_Logo_32px.png" "$APPDIR/autoreturn.png"
            cp "$PROJECT_ROOT/src/frontend/assets/Gmail_Logo_32px.png" \
               "$APPDIR/usr/share/icons/hicolor/256x256/apps/autoreturn.png"
        fi
        echo "  WARNING: No SVG converter found. Install rsvg-convert: sudo pacman -S librsvg"
    fi
else
    # Fallback to existing asset
    mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"
    cp "$PROJECT_ROOT/src/frontend/assets/Gmail_Logo_32px.png" "$APPDIR/autoreturn.png"
    cp "$PROJECT_ROOT/src/frontend/assets/Gmail_Logo_32px.png" \
       "$APPDIR/usr/share/icons/hicolor/256x256/apps/autoreturn.png"
fi

echo "  Launcher created"
echo ""

# -----------------------------------------------
# STEP 7: Package into AppImage
# -----------------------------------------------
echo "[7/7] Packaging AppImage..."

OUTPUT_FILE="$PROJECT_ROOT/AutoReturn-x86_64.AppImage"

ARCH=x86_64 "$APPIMAGETOOL" "$APPDIR" "$OUTPUT_FILE" 2>&1

if [ -f "$OUTPUT_FILE" ]; then
    chmod +x "$OUTPUT_FILE"
    SIZE=$(du -sh "$OUTPUT_FILE" | cut -f1)
    echo ""
    echo "=============================================="
    echo "  BUILD SUCCESSFUL!"
    echo "=============================================="
    echo ""
    echo "  Output: $OUTPUT_FILE"
    echo "  Size:   $SIZE"
    echo ""
    echo "  To run:"
    echo "  chmod +x AutoReturn-x86_64.AppImage"
    echo "  ./AutoReturn-x86_64.AppImage"
    echo ""
    echo "  NOTE: Ollama must be running separately:"
    echo "  ollama serve"
    echo "=============================================="
else
    echo "ERROR: AppImage was not created. Check the output above."
    exit 1
fi
