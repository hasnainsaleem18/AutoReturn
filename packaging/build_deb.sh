#!/bin/bash
# ==============================================
# AutoReturn .deb Package Builder
# ==============================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
APP_NAME="autoreturn"
APP_VERSION="1.0.0"
ARCH="amd64"
BUILD_DIR="$PROJECT_ROOT/build_deb"
PKG_DIR="$BUILD_DIR/${APP_NAME}_${APP_VERSION}_${ARCH}"

echo "=============================================="
echo "  AutoReturn .deb Package Builder"
echo "=============================================="
echo ""

# -----------------------------------------------
# STEP 1: Check prerequisites
# -----------------------------------------------
echo "[1/6] Checking prerequisites..."

if ! command -v dpkg-deb &> /dev/null; then
    echo "ERROR: dpkg-deb not found. Install with: sudo pacman -S dpkg"
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "  Python: $PYTHON_VERSION"
echo "  dpkg-deb: OK"
echo ""

# -----------------------------------------------
# STEP 2: Clean and create package structure
# -----------------------------------------------
echo "[2/6] Creating package structure..."

rm -rf "$BUILD_DIR"
mkdir -p "$PKG_DIR/DEBIAN"
mkdir -p "$PKG_DIR/opt/autoreturn"
mkdir -p "$PKG_DIR/usr/bin"
mkdir -p "$PKG_DIR/usr/share/applications"
mkdir -p "$PKG_DIR/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$PKG_DIR/usr/share/icons/hicolor/scalable/apps"
mkdir -p "$PKG_DIR/usr/share/doc/autoreturn"

echo "  Done"
echo ""

# -----------------------------------------------
# STEP 3: Copy application source
# -----------------------------------------------
echo "[3/6] Copying application files..."

cp "$PROJECT_ROOT/main.py"        "$PKG_DIR/opt/autoreturn/"
cp -r "$PROJECT_ROOT/src"         "$PKG_DIR/opt/autoreturn/"
cp -r "$PROJECT_ROOT/config"      "$PKG_DIR/opt/autoreturn/"
cp -r "$PROJECT_ROOT/data"        "$PKG_DIR/opt/autoreturn/"

# Copy .env (Supabase credentials)
if [ -f "$PROJECT_ROOT/.env" ]; then
    cp "$PROJECT_ROOT/.env" "$PKG_DIR/opt/autoreturn/"
fi

echo "  Done"
echo ""

# -----------------------------------------------
# STEP 4: Install Python dependencies
# -----------------------------------------------
echo "[4/6] Installing Python dependencies..."

SITE_PACKAGES="$PKG_DIR/opt/autoreturn/lib/python${PYTHON_VERSION}/site-packages"
mkdir -p "$SITE_PACKAGES"

pip3 install \
    --target="$SITE_PACKAGES" \
    -r "$PROJECT_ROOT/appimage/requirements-appimage.txt" \
    --quiet

# Bundle spaCy model
echo "  Bundling spaCy en_core_web_md model..."
SPACY_MODEL_PATH=$(python3 -c "
import os
try:
    import en_core_web_md
    print(os.path.dirname(en_core_web_md.__file__))
except:
    pass
" 2>/dev/null)

if [ -n "$SPACY_MODEL_PATH" ] && [ -d "$SPACY_MODEL_PATH" ]; then
    cp -r "$SPACY_MODEL_PATH" "$SITE_PACKAGES/en_core_web_md"
    echo "  spaCy model bundled"
else
    echo "  WARNING: en_core_web_md not found. Run: python3 -m spacy download en_core_web_md"
fi

# Bundle Whisper small model
echo "  Bundling Whisper 'small' model..."
WHISPER_CACHE="$HOME/.cache/whisper"
if [ -f "$WHISPER_CACHE/small.pt" ]; then
    mkdir -p "$PKG_DIR/opt/autoreturn/.cache/whisper"
    cp "$WHISPER_CACHE/small.pt" "$PKG_DIR/opt/autoreturn/.cache/whisper/"
    echo "  Whisper small model bundled"
else
    echo "  WARNING: Whisper small model not found. Pre-download with:"
    echo "  python3 -c \"import whisper; whisper.load_model('small')\""
fi

echo "  Dependencies installed"
echo ""

# -----------------------------------------------
# STEP 5: Create launcher, desktop entry, icon
# -----------------------------------------------
echo "[5/6] Creating launcher and desktop integration..."

# Launcher script in /usr/bin
cat > "$PKG_DIR/usr/bin/autoreturn" << 'LAUNCHER_EOF'
#!/bin/bash
# AutoReturn launcher

APP_DIR="/opt/autoreturn"
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "3.12")

export PYTHONPATH="$APP_DIR:$APP_DIR/lib/python${PYTHON_VERSION}/site-packages:$PYTHONPATH"

# Point Whisper to bundled model cache
export XDG_CACHE_HOME="$APP_DIR/.cache"

# User data in home directory
export AUTORETURN_DATA_DIR="$HOME/.autoreturn"
mkdir -p "$AUTORETURN_DATA_DIR/data/gmail_data"
mkdir -p "$AUTORETURN_DATA_DIR/data/ics_exports"
mkdir -p "$AUTORETURN_DATA_DIR/logs"
mkdir -p "$AUTORETURN_DATA_DIR/config"

# Copy default configs if not present
for f in settings.conf tone_detection_rules.json; do
    if [ ! -f "$AUTORETURN_DATA_DIR/config/$f" ] && [ -f "$APP_DIR/config/$f" ]; then
        cp "$APP_DIR/config/$f" "$AUTORETURN_DATA_DIR/config/$f"
    fi
done

for f in automation_settings.json priority_dataset.json tone_profile.json; do
    if [ ! -f "$AUTORETURN_DATA_DIR/data/$f" ] && [ -f "$APP_DIR/data/$f" ]; then
        cp "$APP_DIR/data/$f" "$AUTORETURN_DATA_DIR/data/$f"
    fi
done

exec python3 "$APP_DIR/main.py" "$@"
LAUNCHER_EOF

chmod +x "$PKG_DIR/usr/bin/autoreturn"

# Desktop entry
cat > "$PKG_DIR/usr/share/applications/autoreturn.desktop" << 'DESKTOP_EOF'
[Desktop Entry]
Name=AutoReturn
Comment=Unified AI Communication Management
Exec=autoreturn
Icon=autoreturn
Type=Application
Categories=Office;Network;Email;
Terminal=false
StartupNotify=true
DESKTOP_EOF

# Icon
if [ -f "$PROJECT_ROOT/appimage/autoreturn.svg" ]; then
    cp "$PROJECT_ROOT/appimage/autoreturn.svg" \
       "$PKG_DIR/usr/share/icons/hicolor/scalable/apps/autoreturn.svg"

    if command -v rsvg-convert &> /dev/null; then
        rsvg-convert -w 256 -h 256 "$PROJECT_ROOT/appimage/autoreturn.svg" \
            -o "$PKG_DIR/usr/share/icons/hicolor/256x256/apps/autoreturn.png"
        echo "  Icon converted via rsvg-convert"
    elif command -v convert &> /dev/null; then
        convert -background none -resize 256x256 \
            "$PROJECT_ROOT/appimage/autoreturn.svg" \
            "$PKG_DIR/usr/share/icons/hicolor/256x256/apps/autoreturn.png" 2>/dev/null
        echo "  Icon converted via ImageMagick"
    fi
fi

# Copyright/doc
cat > "$PKG_DIR/usr/share/doc/autoreturn/copyright" << 'DOC_EOF'
AutoReturn - Unified AI Communication Management
Developed by Kashan Saeed, Alishba Tariq & Hasnain Saleem
NUCES FAST Peshawar - Final Year Project 2026
DOC_EOF

echo "  Done"
echo ""

# -----------------------------------------------
# STEP 6: Create DEBIAN control files and build
# -----------------------------------------------
echo "[6/6] Building .deb package..."

# Calculate installed size in KB
INSTALLED_SIZE=$(du -sk "$PKG_DIR/opt/autoreturn" | cut -f1)

cat > "$PKG_DIR/DEBIAN/control" << CONTROL_EOF
Package: autoreturn
Version: ${APP_VERSION}
Section: net
Priority: optional
Architecture: ${ARCH}
Installed-Size: ${INSTALLED_SIZE}
Depends: python3 (>= 3.10), python3-pip, libportaudio2
Recommends: ollama
Maintainer: AutoReturn Team <autoreturn@nuces.edu.pk>
Description: Unified AI Communication Management
 AutoReturn is a desktop application that centralizes Gmail and Slack
 into a single AI-powered interface. Features include priority ranking,
 tone detection, smart draft generation, and calendar event extraction.
 .
 Requires Ollama running locally for AI features.
Homepage: https://github.com/hasnainsaleem18/AutoReturn
CONTROL_EOF

# Post-install script
cat > "$PKG_DIR/DEBIAN/postinst" << 'POSTINST_EOF'
#!/bin/bash
# Update icon cache
if command -v gtk-update-icon-cache &> /dev/null; then
    gtk-update-icon-cache -f /usr/share/icons/hicolor/ 2>/dev/null || true
fi
# Update desktop database
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database /usr/share/applications/ 2>/dev/null || true
fi
echo "AutoReturn installed. Run: autoreturn"
echo "Make sure Ollama is running: ollama serve"
POSTINST_EOF
chmod 755 "$PKG_DIR/DEBIAN/postinst"

# Pre-remove script
cat > "$PKG_DIR/DEBIAN/prerm" << 'PRERM_EOF'
#!/bin/bash
echo "Removing AutoReturn..."
PRERM_EOF
chmod 755 "$PKG_DIR/DEBIAN/prerm"

# Build the .deb
OUTPUT_FILE="$PROJECT_ROOT/${APP_NAME}_${APP_VERSION}_${ARCH}.deb"
dpkg-deb --build --root-owner-group "$PKG_DIR" "$OUTPUT_FILE"

if [ -f "$OUTPUT_FILE" ]; then
    SIZE=$(du -sh "$OUTPUT_FILE" | cut -f1)
    echo ""
    echo "=============================================="
    echo "  BUILD SUCCESSFUL!"
    echo "=============================================="
    echo ""
    echo "  Output: $OUTPUT_FILE"
    echo "  Size:   $SIZE"
    echo ""
    echo "  Install with:"
    echo "  sudo dpkg -i ${APP_NAME}_${APP_VERSION}_${ARCH}.deb"
    echo ""
    echo "  Then run: autoreturn"
    echo "=============================================="
else
    echo "ERROR: .deb was not created."
    exit 1
fi
