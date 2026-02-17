# 🎨 Tone Adjustment Feature - Complete Guide

## Overview

AutoReturn's Tone Adjustment feature provides intelligent, context-aware tone control for all your communications. It combines manual tone selection with AI-powered recommendations to ensure your messages are always appropriate for the context.

## ✨ Key Features

### 🧠 Intelligent Tone Recommendations
- **Context-Aware**: Analyzes sender, content, priority, and relationship
- **Confidence Scoring**: Shows AI confidence in recommendations
- **Learning System**: Improves based on your manual selections
- **Sender-Specific**: Remembers preferred tones for frequent contacts

### 🎛️ Manual Tone Control
- **13 Available Tones**: Formal, Professional, Casual, Friendly, Assertive, Persuasive, Apologetic, Empathetic, Diplomatic, Concise, Humorous, Appreciative, Urgent
- **Override Capability**: Full control to override AI recommendations
- **Real-time Preview**: See tone changes instantly as you type

### 📊 Analytics & Learning
- **Usage Statistics**: Track most used tones and effectiveness
- **Sender Preferences**: Automatic tone suggestions for frequent contacts
- **Domain Adaptation**: Different tones for internal vs external communication

## 🏗️ Architecture

### Zero-Disturbance Integration
The tone system is designed as an **extension layer** that enhances existing functionality without modifying any working code:

```
Existing Components (Untouched):
├── Gmail Service
├── Slack Service  
├── AI Service
├── Draft Manager
└── Orchestrator

New Tone Components (Added):
├── Tone Manager (Core Logic)
├── Tone Service (AI Processing)
├── Tone Selector (UI Widget)
├── Tone Integration (Main UI)
└── Enhanced Dialogs (Gmail + Slack)
```

### Component Overview

#### **Core Components**
- **`ToneManager`**: Central coordination and learning
- **`ToneService`**: AI-powered tone adjustment and recommendations
- **`ToneModels`**: Data structures and type definitions

#### **UI Components**
- **`ToneSelector`**: Dropdown widget with AI recommendations
- **`ToneIntegration`**: Main UI integration layer
- **`ToneSettingsDialog`**: Comprehensive preferences management

#### **Enhanced Dialogs**
- **`SendGmailReplyDialogEnhanced`**: Gmail reply with tone control
- **`SendSlackMessageDialogEnhanced`**: Slack messaging with tone control

## 🚀 Usage Guide

### Basic Usage

#### 1. **Automatic Mode** (Recommended)
```
The system automatically:
✓ Analyzes incoming messages
✓ Recommends appropriate tone
✓ Shows confidence level
✓ Applies tone to drafts
```

#### 2. **Manual Override**
```
User can:
✓ Select any tone manually
✓ See real-time preview
✓ Override AI suggestions
✓ Set sender-specific preferences
```

### Advanced Features

#### **Sender-Specific Tones**
- System learns your preferred tones for each contact
- Automatically applies when communicating with frequent contacts
- Can be customized in Tone Settings

#### **Context-Aware Recommendations**
- **Complaints** → Formal + Apologetic
- **Internal Team** → Casual + Friendly  
- **High Priority** → Assertive + Urgent
- **External Clients** → Professional + Diplomatic

#### **Tone Analytics**
- Track usage patterns
- Identify communication effectiveness
- Optimize tone suggestions
- Export statistics for analysis

## 🎯 Available Tones

| Tone | Best For | Characteristics |
|-------|-----------|----------------|
| **Formal** | Official documents, complaints | Respectful, traditional, proper |
| **Professional** | Business communication | Clear, workplace-appropriate, standard |
| **Casual** | Internal team, informal | Friendly, conversational, relaxed |
| **Friendly** | Team building, greetings | Warm, approachable, positive |
| **Assertive** | Urgent requests, leadership | Confident, direct, decisive |
| **Persuasive** | Sales, proposals | Convincing, compelling, action-oriented |
| **Apologetic** | Mistakes, service recovery | Sincere, empathetic, solution-focused |
| **Empathetic** | Support, personal issues | Understanding, caring, emotionally aware |
| **Diplomatic** | Conflicts, negotiations | Tactful, balanced, conflict-resolution |
| **Concise** | Quick updates, summaries | Brief, to-the-point, efficient |
| **Humorous** | Team bonding, informal | Light-hearted, witty, appropriate |
| **Appreciative** | Thanks, recognition | Grateful, acknowledging, positive |
| **Urgent** | Critical issues, deadlines | Time-sensitive, action-oriented, important |

## 🔧 Technical Implementation

### Integration Points

#### **Main Application**
```python
# In AutoReturnApp.__init__():
self.tone_integration = integrate_tone_system(self, self.orchestrator)

# In setup_ui():
self.tone_integration.integrate_into_main_ui(main_layout)
```

#### **Dialog Enhancement**
```python
# Instead of original dialogs:
dialog = SendGmailReplyDialog(to_email, subject)

# Use enhanced versions:
dialog = create_enhanced_gmail_reply_dialog(message_data, tone_manager, parent)
```

#### **AI Processing**
```python
# Tone adjustment
response = await tone_manager.adjust_message_tone(
    original_text="Original message",
    target_tone=ToneType.PROFESSIONAL,
    message_context=context
)

# Get adjusted text
adjusted_text = response.adjusted_text
```

### Data Flow

```
Message Input → Context Analysis → Tone Recommendation → User Selection → AI Adjustment → Output
     ↓               ↓                    ↓               ↓              ↓
  Extract Content  →  Analyze Sender  →  Show Dropdown  →  Apply Tone  →  Final Message
  Priority Level  →  Check Urgency  →  Confidence    →  Real-time   →  Send/Save
  Relationship    →  Message Type   →  Reasoning     →  Preview     →  Learn from Choice
```

## 📱 User Interface

### **Main Tone Panel**
- Located in main application header
- Quick tone selector dropdown
- Auto/Manual mode toggle
- Settings access button
- Confidence indicator

### **Dialog Integration**
- Tone controls added to compose dialogs
- Real-time draft preview
- AI reasoning display
- Manual override options

### **Settings Dialog**
- **General Tab**: Default tone, auto-mode
- **Sender Preferences**: Per-contact tone settings
- **Analytics Tab**: Usage statistics and insights

## 🎓 Learning & Adaptation

### **Automatic Learning**
- Tracks manual tone selections
- Builds sender preference profiles
- Improves recommendation accuracy
- Adapts to communication patterns

### **User Feedback Integration**
- Records tone effectiveness
- Adjusts confidence scores
- Refines recommendation algorithms
- Personalizes suggestions

## 🔒 Privacy & Security

### **Local Storage**
- All tone preferences stored locally
- No cloud data transmission
- User profiles kept private
- Optional analytics export

### **Data Management**
- Automatic cleanup of old data
- Configurable retention periods
- Secure storage encryption
- User control over all data

## 🚀 Performance & Optimization

### **Efficient Processing**
- Asynchronous AI operations
- Cached tone recommendations
- Background processing
- Non-blocking UI

### **Smart Caching**
- Message analysis caching (5 minutes)
- Sender preference caching
- Tone adjustment caching
- Memory-efficient storage

## 🔄 Future Enhancements

### **Planned Features**
- **Voice Tone Control**: Adjust tone via voice commands
- **Template System**: Pre-defined tone templates
- **Advanced Analytics**: Communication pattern analysis
- **Team Profiles**: Shared tone preferences for teams
- **Integration APIs**: External tone service integration

### **Extension Points**
The system is designed for easy extension:
- New tone types can be added
- Custom AI models can be integrated
- Third-party tone services supported
- Plugin architecture for enhancements

## 🛠️ Development Guide

### **Adding New Tones**
```python
# 1. Add to ToneType enum
class ToneType(str, Enum):
    # ... existing tones ...
    NEW_TONE = "new_tone"

# 2. Add instruction to ToneService
self.tone_instructions[ToneType.NEW_TONE] = "Instruction for new tone..."

# 3. Update UI components
# Add to tone selector dropdown and settings dialog
```

### **Custom AI Integration**
```python
# Replace or extend ToneService
class CustomToneService(ToneService):
    async def adjust_tone(self, text, tone):
        # Custom AI implementation
        pass
```

## 📞 Troubleshooting

### **Common Issues**
1. **Tone not applying**: Check AI service connection
2. **No recommendations**: Verify auto-mode is enabled
3. **Performance issues**: Clear tone cache and restart
4. **Settings not saving**: Check file permissions

### **Debug Mode**
Enable debug logging:
```python
# In tone_manager.py
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📚 API Reference

### **ToneManager**
```python
# Core methods
await tone_manager.analyze_message_context(message_data)
await tone_manager.adjust_message_tone(text, target_tone)
tone_manager.set_default_tone(ToneType.PROFESSIONAL)
tone_manager.get_tone_statistics()
```

### **ToneSelector**
```python
# UI methods
tone_selector.set_recommended_tone(recommendation)
tone_selector.get_selected_tone()
tone_selector.set_auto_mode(enabled)
tone_selector.is_auto_mode()
```

### **Integration Functions**
```python
# Factory functions
dialog = create_enhanced_gmail_reply_dialog(message_data, tone_manager)
dialog = create_enhanced_slack_message_dialog(recipient_info, tone_manager)
integration = integrate_tone_system(main_app, orchestrator)
```

---

## 🎉 Summary

The Tone Adjustment feature represents a **significant enhancement** to AutoReturn's communication capabilities while maintaining the principle of **zero disturbance** to existing functionality. Users get:

- ✅ **Intelligent Assistance**: AI-powered tone recommendations
- ✅ **Full Control**: Manual override and customization options  
- ✅ **Context Awareness**: Situation-appropriate suggestions
- ✅ **Learning System**: Improves over time
- ✅ **Seamless Integration**: Works with existing features
- ✅ **Privacy First**: Local storage and user control

The system transforms AutoReturn from a unified inbox into an **intelligent communication assistant** that helps users communicate more effectively across all platforms.
