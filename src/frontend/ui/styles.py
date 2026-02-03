def get_stylesheet():
    return """
        QMainWindow {
            background-color: #ffffff;
        }
        
        #header {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #024950, stop:1 #003135);
            border-bottom: 2px solid #0FA4AF;
        }
        
        #logo {
            font-size: 20px;
            font-weight: bold;
            color: #AFDDE5;
        }
        
        #searchInput {
            padding: 10px 16px;
            border: 1px solid #AFDDE5;
            border-radius: 8px;
            font-size: 14px;
            background-color: #ffffff;
            color: #003135;
        }
        
        #searchInput:focus {
            border: 2px solid #0FA4AF;
            background-color: white;
        }
        
        #quietHoursIndicator {
            background-color: #AFDDE5;
            color: #003135;
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 13px;
            border: 1px solid #0FA4AF;
            font-weight: 500;
        }
        
        #btnVoice {
            background-color: #0FA4AF;
            color: white;
            font-weight: 600;
            padding: 8px 16px;
            border: none;
            border-radius: 8px;
            font-size: 14px;
        }
        
        #btnVoice:hover {
            background-color: #024950;
        }
        
        #iconBtn {
            background-color: transparent;
            border: none;
            font-size: 20px;
            padding: 8px;
            border-radius: 6px;
            color: #AFDDE5;
        }
        
        #iconBtn:hover {
            background-color: rgba(175, 221, 229, 0.2);
        }
        
        #notificationBadge {
            background-color: #964734;
            color: white;
            font-size: 10px;
            padding: 2px 5px;
            border-radius: 10px;
            font-weight: 600;
        }
        
        #mainContent {
            background-color: #ffffff;
        }
        
        #inboxTitle {
            font-size: 24px;
            font-weight: 600;
            color: #003135;
        }
        
        #btnSecondary {
            padding: 8px 16px;
            border: 2px solid #0FA4AF;
            background-color: white;
            border-radius: 8px;
            font-size: 14px;
            color: #024950;
            font-weight: 500;
        }
        
        #btnSecondary:hover {
            border-color: #024950;
            background-color: #AFDDE5;
        }
        
        #filterBtn {
            padding: 8px 16px;
            border: 1px solid #AFDDE5;
            background-color: white;
            border-radius: 8px;
            font-size: 14px;
            color: #003135;
        }
        
        #filterBtn:hover {
            border-color: #0FA4AF;
            background-color: #AFDDE5;
        }
        
        #filterBtn[active="true"] {
            background-color: #0FA4AF;
            color: white;
            border-color: #0FA4AF;
            font-weight: 600;
        }
        
        #messageTable {
            background-color: white;
            border-radius: 12px;
            border: 2px solid #AFDDE5;
        }
        
        #messageTable::item {
            border-bottom: 1px solid #AFDDE5;
            padding: 8px;
        }
        
        #messageTable::item:hover {
            background-color: rgba(175, 221, 229, 0.3);
        }
        
        #messageTable::item:selected {
            background-color: #D4F4F7;
            color: #003135;
        }
        
        QHeaderView::section {
            background-color: #AFDDE5;
            border: none;
            border-bottom: 2px solid #024950;
            padding: 14px 16px;
            font-weight: 600;
            font-size: 13px;
            color: #003135;
        }
        
        QHeaderView::section:hover {
            background-color: #0FA4AF;
            color: white;
        }
        
        #fromName {
            font-weight: 600;
            color: #003135;
        }
        
        #fromEmail {
            font-size: 12px;
            color: #024950;
        }
        
        #subjectText {
            font-weight: 500;
            color: #003135;
        }
        
        #previewText {
            font-size: 12px;
            color: #024950;
        }
        
        #summaryText {
            font-size: 13px;
            color: #024950;
        }
        
        #actionBtn {
            padding: 6px 10px;
            border: 1px solid #AFDDE5;
            background-color: #0FA4AF;
            color: white;
            border-radius: 6px;
            font-size: 16px;
        }
        
        #actionBtn:hover {
            background-color: #024950;
        }
        
        #expandedContent {
            background-color: #AFDDE5;
            border-top: 3px solid #0FA4AF;
        }
        
        #emailFull {
            background-color: white;
            border-radius: 8px;
            border: 1px solid #0FA4AF;
        }
        
        #emailBody {
            line-height: 1.6;
            color: #003135;
        }
        
        #aiAnalysis {
            background-color: white;
            border: 2px solid #0FA4AF;
            border-radius: 8px;
        }
        
        #aiHeader {
            font-weight: 600;
            font-size: 16px;
            color: #024950;
        }
        
        #replyOption {
            background-color: white;  /* Was: #AFDDE5 */
            border: 2px solid #0FA4AF;
            border-radius: 8px;
        }
        
        #replyLabel {
            font-weight: 600;
            font-size: 13px;
            color: #003135;
        }
        
        #replyText {
            color: #024950;
            line-height: 1.5;
            font-size: 14px;  /* Added this line */
        }
        
        #btnPrimary {
            background-color: #0FA4AF;
            color: white;
            border: none;
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 600;
        }
        
        #btnPrimary:hover {
            background-color: #024950;
        }
        
        #statusBar {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #003135, stop:1 #024950);
            border-top: 2px solid #0FA4AF;
        }
        
        #statusItem {
            font-size: 13px;
            color: #AFDDE5;
        }
    """


