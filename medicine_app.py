import streamlit as st
import qrcode
from PIL import Image
import io
import base64
from datetime import datetime
import time
import pandas as pd
import json
import random
import easyocr
import numpy as np
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Page config
st.set_page_config(
    page_title="Medicine Dispenser",
    page_icon="💊",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1e88e5;
        text-align: center;
        padding: 1rem;
        background: linear-gradient(90deg, #e3f2fd 0%, #bbdefb 100%);
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    .action-card {
        padding: 1.5rem;
        background: white;
        border-radius: 10px;
        border: 2px solid #1e88e5;
        text-align: center;
        cursor: pointer;
        transition: transform 0.2s;
    }
    .action-card:hover {
        transform: scale(1.05);
    }
    .qr-display {
        text-align: center;
        padding: 2rem;
        background: #f5f5f5;
        border-radius: 10px;
    }
    .numeric-code {
        font-size: 2rem;
        font-weight: bold;
        color: #1e88e5;
        background: #fff3e0;
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'current_user' not in st.session_state:
    st.session_state.current_user = None
if 'prescriptions' not in st.session_state:
    st.session_state.prescriptions = []
if 'current_medicines' not in st.session_state:
    st.session_state.current_medicines = []
if 'page' not in st.session_state:
    st.session_state.page = 'home'
if 'otp_sent' not in st.session_state:
    st.session_state.otp_sent = False

# Mock user database with email addresses
USERS = {
    "123456789012": {"name": "Rahul Kumar", "email": "rahul@example.com"},
    "234567890123": {"name": "Priya Sharma", "email": "priya@example.com"},
    "345678901234": {"name": "Amit Patel", "email": "amit@example.com"},
    "456789012345": {"name": "Sneha Reddy", "email": "sneha@example.com"},
    "567890123456": {"name": "Rajesh Singh", "email": "rajesh@example.com"}
}

# Email configuration (using session state for security)
def send_otp_email(to_email, otp, user_name):
    """Send OTP via email using Gmail SMTP"""
    try:
        # Get email credentials from Streamlit secrets or use demo mode
        if 'email_config' in st.session_state:
            sender_email = st.session_state.email_config['email']
            sender_password = st.session_state.email_config['password']
        else:
            # Demo mode - just simulate sending
            st.session_state.demo_otp = otp
            return True, "demo"
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = to_email
        msg['Subject'] = '🔐 Medicine Dispenser - Your OTP Code'
        
        # Email body
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <div style="background: linear-gradient(90deg, #e3f2fd 0%, #bbdefb 100%); padding: 20px; border-radius: 10px;">
                <h2 style="color: #1e88e5;">💊 Medicine Dispenser</h2>
                <p>Hello <strong>{user_name}</strong>,</p>
                <p>Your One-Time Password (OTP) for login is:</p>
                <div style="background: #fff3e0; padding: 15px; border-radius: 5px; text-align: center; margin: 20px 0;">
                    <h1 style="color: #1e88e5; font-size: 32px; letter-spacing: 5px;">{otp}</h1>
                </div>
                <p>This OTP is valid for 5 minutes.</p>
                <p style="color: #666; font-size: 12px;">If you didn't request this OTP, please ignore this email.</p>
            </div>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        # Send email
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender_email, sender_password)
            server.send_message(msg)
        
        return True, "sent"
    
    except Exception as e:
        st.error(f"Error sending email: {str(e)}")
        # Fallback to demo mode
        st.session_state.demo_otp = otp
        return True, "demo"

def generate_otp():
    """Generate a 6-digit OTP"""
    return str(random.randint(100000, 999999))

# Initialize EasyOCR reader (cached to avoid reloading)
@st.cache_resource
def load_ocr_reader():
    return easyocr.Reader(['en'], gpu=False)

# Real OCR function with medicine extraction
def process_prescription_ocr(image):
    """Extract text from prescription image and parse medicines"""
    try:
        # Convert PIL image to numpy array
        img_array = np.array(image)
        
        # Load OCR reader
        reader = load_ocr_reader()
        
        # Perform OCR
        results = reader.readtext(img_array)
        
        # Extract all text
        full_text = ' '.join([text[1] for text in results])
        
        # Parse medicines from text
        medicines = parse_medicines_from_text(full_text)
        
        return medicines
    except Exception as e:
        st.error(f"OCR Error: {str(e)}")
        # Fallback to mock data if OCR fails
        return mock_ocr_fallback()

def parse_medicines_from_text(text):
    """Parse medicine information from extracted text"""
    medicines = []
    
    # Common medicine name patterns (you can expand this list)
    common_medicines = [
        'paracetamol', 'amoxicillin', 'azithromycin', 'ciprofloxacin',
        'metformin', 'aspirin', 'ibuprofen', 'omeprazole', 'vitamin',
        'crocin', 'dolo', 'calpol', 'augmentin', 'pantoprazole'
    ]
    
    # Split text into lines
    lines = text.lower().split('\n')
    words = text.lower().split()
    
    # Look for medicine names and dosage patterns
    for i, word in enumerate(words):
        for med_name in common_medicines:
            if med_name in word:
                # Found a medicine, try to extract dosage info
                dosage = extract_dosage(words, i)
                frequency = extract_frequency(words, i)
                duration = extract_duration(words, i)
                
                medicines.append({
                    'name': word.title(),
                    'dosage': dosage,
                    'frequency': frequency,
                    'duration': duration
                })
                break
    
    # If no medicines found, return default parsing
    if not medicines:
        # Try to extract any numbers followed by 'mg', 'ml', etc.
        pattern = r'(\d+\s*(?:mg|ml|g|mcg|iu))'
        dosages = re.findall(pattern, text.lower())
        
        if dosages:
            for i, dose in enumerate(dosages[:3]):  # Limit to 3 medicines
                medicines.append({
                    'name': f'Medicine {i+1}',
                    'dosage': dose,
                    'frequency': '2 times daily',
                    'duration': '5 days'
                })
    
    # If still no medicines, return at least one blank entry
    if not medicines:
        medicines.append({
            'name': 'Medicine 1',
            'dosage': '',
            'frequency': '',
            'duration': ''
        })
    
    return medicines

def extract_dosage(words, index):
    """Extract dosage from nearby words"""
    # Look in next 3 words for dosage pattern
    for i in range(index, min(index + 4, len(words))):
        if re.search(r'\d+\s*(?:mg|ml|g|mcg|iu)', words[i].lower()):
            return words[i]
    return '500mg'  # default

def extract_frequency(words, index):
    """Extract frequency from nearby words"""
    freq_patterns = ['once', 'twice', 'thrice', 'daily', 'times']
    for i in range(index, min(index + 6, len(words))):
        if any(pattern in words[i].lower() for pattern in freq_patterns):
            return ' '.join(words[i:min(i+3, len(words))])
    return '2 times daily'  # default

def extract_duration(words, index):
    """Extract duration from nearby words"""
    for i in range(index, min(index + 8, len(words))):
        if re.search(r'\d+\s*(?:day|days|week|weeks|month)', words[i].lower()):
            return words[i]
    return '5 days'  # default

def mock_ocr_fallback():
    """Fallback mock data if OCR fails"""
    return [
        {"name": "Medicine 1", "dosage": "", "frequency": "", "duration": ""},
        {"name": "Medicine 2", "dosage": "", "frequency": "", "duration": ""}
    ]

# Generate QR code
def generate_qr_code(data):
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(json.dumps(data))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    # Convert to PIL Image if needed
    if not isinstance(img, Image.Image):
        img = img.convert('RGB')
    return img

# Generate numeric code
def generate_numeric_code():
    return ''.join([str(random.randint(0, 9)) for _ in range(8)])

# Convert image to base64
def img_to_base64(img):
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

# Login page
def login_page():
    st.markdown("<div class='main-header'>💊 Medicine Dispenser - Login</div>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("### 🔐 Aadhar Authentication")
        
        # Email configuration section (collapsible)
        with st.expander("⚙️ Email Configuration (Optional - For Real OTP)"):
            st.info("💡 **Demo Mode:** Leave empty to use demo OTP (123456). Configure your Gmail to send real OTPs.")
            email_input = st.text_input("Your Gmail Address", key="config_email")
            password_input = st.text_input("Gmail App Password", type="password", key="config_password", 
                                          help="Not your regular password! Create an App Password at https://myaccount.google.com/apppasswords")
            
            if st.button("💾 Save Email Config"):
                if email_input and password_input:
                    st.session_state.email_config = {
                        'email': email_input,
                        'password': password_input
                    }
                    st.success("✅ Email configuration saved! OTPs will be sent to registered emails.")
                else:
                    st.warning("⚠️ Both fields required. Leave empty for demo mode.")
        
        with st.expander("📋 Test Users"):
            st.write("**Available Test Users:**")
            for aadhar, info in USERS.items():
                email_display = info.get('email', 'N/A')
                st.write(f"- **{info['name']}**")
                st.write(f"  Aadhar: `{aadhar}` | Email: `{email_display}`")
            
            if 'email_config' not in st.session_state:
                st.info("📧 **Demo Mode Active:** Use OTP `123456` for any user")
        
        st.markdown("---")
        
        aadhar = st.text_input("Enter Aadhar Number (12 digits)", max_chars=12)
        
        if st.button("📧 Send OTP", type="primary", use_container_width=True):
            if len(aadhar) == 12 and aadhar in USERS:
                # Generate OTP
                otp = generate_otp()
                
                # Store OTP and timestamp
                st.session_state.generated_otp = otp
                st.session_state.otp_timestamp = datetime.now()
                st.session_state.otp_sent = True
                st.session_state.temp_aadhar = aadhar
                
                # Send OTP via email
                user_email = USERS[aadhar].get('email', 'demo@example.com')
                user_name = USERS[aadhar]['name']
                
                with st.spinner("📤 Sending OTP..."):
                    success, mode = send_otp_email(user_email, otp, user_name)
                
                if success:
                    if mode == "demo":
                        st.success(f"✅ **Demo Mode:** OTP sent to {user_name}")
                        st.info(f"🔑 **Demo OTP:** `123456` (or use the generated OTP: `{otp}`)")
                    else:
                        st.success(f"✅ OTP sent to {user_email} for {user_name}")
                        st.info("📧 Check your email inbox (and spam folder)")
            else:
                st.error("❌ Invalid Aadhar number")
        
        if st.session_state.otp_sent:
            st.markdown("---")
            otp_input = st.text_input("Enter OTP", max_chars=6, type="password")
            
            if st.button("🔓 Verify & Login", type="primary", use_container_width=True):
                # Check if OTP is expired (5 minutes validity)
                if 'otp_timestamp' in st.session_state:
                    elapsed = (datetime.now() - st.session_state.otp_timestamp).total_seconds()
                    if elapsed > 300:  # 5 minutes
                        st.error("❌ OTP expired. Please request a new one.")
                        st.session_state.otp_sent = False
                        return
                
                # Verify OTP (accept both generated OTP and demo OTP)
                valid_otps = [st.session_state.get('generated_otp', ''), '123456']
                
                if otp_input in valid_otps:
                    st.session_state.authenticated = True
                    st.session_state.current_user = {
                        'aadhar': st.session_state.temp_aadhar,
                        'name': USERS[st.session_state.temp_aadhar]['name']
                    }
                    st.session_state.otp_sent = False
                    st.success("✅ Login successful!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Invalid OTP")

# Home page
def home_page():
    st.markdown(f"<div class='main-header'>💊 Welcome, {st.session_state.current_user['name']}!</div>", unsafe_allow_html=True)
    
    # Quick stats
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Prescriptions", len(st.session_state.prescriptions))
    with col2:
        st.metric("Status", "✅ Active")
    with col3:
        st.metric("Account", "Verified")
    
    st.markdown("---")
    
    # Action cards
    st.markdown("### 🎯 Quick Actions")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📤 Upload New Prescription", use_container_width=True):
            st.session_state.page = 'upload'
            st.rerun()
    
    with col2:
        if st.button("📋 View History", use_container_width=True):
            st.session_state.page = 'history'
            st.rerun()
    
    with col3:
        if st.button("👤 Profile Info", use_container_width=True):
            st.info(f"**Name:** {st.session_state.current_user['name']}\n\n**Aadhar:** {st.session_state.current_user['aadhar']}")

# Upload prescription page
def upload_page():
    st.markdown("<div class='main-header'>📤 Upload Prescription</div>", unsafe_allow_html=True)
    
    if st.button("⬅️ Back to Home"):
        st.session_state.page = 'home'
        st.rerun()
    
    st.info("📸 Upload a photo of your prescription or use your camera to capture it")
    
    uploaded_file = st.file_uploader("Choose prescription image", type=['jpg', 'jpeg', 'png', 'pdf'])
    
    # Camera input for mobile devices
    camera_photo = st.camera_input("📷 Or take a photo with your camera")
    
    image_to_process = uploaded_file or camera_photo
    
    if image_to_process:
        # Display preview
        st.markdown("### 👁️ Prescription Preview")
        if image_to_process.type != "application/pdf":
            image = Image.open(image_to_process)
            st.image(image, width=400)
        
        if st.button("🔍 Process Prescription", type="primary"):
            with st.spinner("🔄 Analyzing prescription with OCR... This may take 30-60 seconds on first run..."):
                # Convert to PIL Image if needed
                if image_to_process.type != "application/pdf":
                    image = Image.open(image_to_process)
                else:
                    st.error("PDF processing not yet supported. Please upload an image (JPG/PNG).")
                    return
                
                medicines = process_prescription_ocr(image)
                st.session_state.current_medicines = medicines
                st.session_state.page = 'edit'
                st.rerun()

# Edit medicines page
def edit_page():
    st.markdown("<div class='main-header'>✏️ Review & Edit Medicines</div>", unsafe_allow_html=True)
    
    if st.button("⬅️ Back"):
        st.session_state.page = 'upload'
        st.rerun()
    
    st.success("✅ Prescription processed successfully! Review the medicines below:")
    
    # Display and edit medicines
    for i, med in enumerate(st.session_state.current_medicines):
        with st.expander(f"💊 {med['name']}", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                med['name'] = st.text_input("Medicine Name", value=med['name'], key=f"name_{i}")
                med['dosage'] = st.text_input("Dosage", value=med['dosage'], key=f"dose_{i}")
            with col2:
                med['frequency'] = st.text_input("Frequency", value=med['frequency'], key=f"freq_{i}")
                med['duration'] = st.text_input("Duration", value=med['duration'], key=f"dur_{i}")
            
            if st.button(f"🗑️ Delete {med['name']}", key=f"del_{i}"):
                st.session_state.current_medicines.pop(i)
                st.rerun()
    
    # Add new medicine
    if st.button("➕ Add New Medicine"):
        st.session_state.current_medicines.append({
            "name": "New Medicine",
            "dosage": "",
            "frequency": "",
            "duration": ""
        })
        st.rerun()
    
    st.markdown("---")
    
    if len(st.session_state.current_medicines) > 0:
        if st.button("✅ Generate QR Code", type="primary", use_container_width=True):
            st.session_state.page = 'qr'
            st.rerun()
    else:
        st.warning("⚠️ Please add at least one medicine before generating QR code")

# QR code display page
def qr_page():
    st.markdown("<div class='main-header'>✅ QR Code Generated</div>", unsafe_allow_html=True)
    
    # Generate prescription ID
    prescription_id = datetime.now().strftime("%Y%m%d%H%M%S")
    numeric_code = generate_numeric_code()
    
    # Prepare data
    prescription_data = {
        "id": prescription_id,
        "patient": st.session_state.current_user['name'],
        "aadhar": st.session_state.current_user['aadhar'],
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "medicines": st.session_state.current_medicines,
        "code": numeric_code
    }
    
    # Save to history
    st.session_state.prescriptions.append(prescription_data)
    
    # Generate QR code
    qr_img = generate_qr_code(prescription_data)
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("### 📱 Scan QR Code")
        # Convert QR image to bytes for display
        buf = io.BytesIO()
        qr_img.save(buf, format='PNG')
        buf.seek(0)
        st.image(buf, width=300)
        
        # Download button
        buf2 = io.BytesIO()
        qr_img.save(buf2, format='PNG')
        st.download_button(
            label="💾 Download QR Code",
            data=buf2.getvalue(),
            file_name=f"prescription_{prescription_id}.png",
            mime="image/png"
        )
    
    with col2:
        st.markdown("### 🔢 Numeric Code")
        st.markdown(f"<div class='numeric-code'>{numeric_code}</div>", unsafe_allow_html=True)
        st.info("📝 Show this code to the pharmacist if you don't have a smartphone")
        
        st.markdown("### 📋 Prescription Summary")
        st.write(f"**ID:** {prescription_id}")
        st.write(f"**Date:** {prescription_data['date']}")
        st.write(f"**Medicines:** {len(st.session_state.current_medicines)}")
    
    # Medicine list
    st.markdown("---")
    st.markdown("### 💊 Medicine Details")
    df = pd.DataFrame(st.session_state.current_medicines)
    st.dataframe(df, use_container_width=True)
    
    st.markdown("---")
    st.success("🎉 QR Code generated successfully! Show this to the pharmacist.")
    
    if st.button("🏠 Back to Home", type="primary"):
        st.session_state.current_medicines = []
        st.session_state.page = 'home'
        st.rerun()

# History page
def history_page():
    st.markdown("<div class='main-header'>📋 Prescription History</div>", unsafe_allow_html=True)
    
    if st.button("⬅️ Back to Home"):
        st.session_state.page = 'home'
        st.rerun()
    
    if len(st.session_state.prescriptions) == 0:
        st.info("📭 No prescriptions found. Upload your first prescription to get started!")
    else:
        st.success(f"📊 Total Prescriptions: {len(st.session_state.prescriptions)}")
        
        # Display in reverse chronological order
        for prescription in reversed(st.session_state.prescriptions):
            with st.expander(f"🗓️ {prescription['date']} - {len(prescription['medicines'])} medicines"):
                col1, col2 = st.columns([1, 2])
                
                with col1:
                    qr_img = generate_qr_code(prescription)
                    buf = io.BytesIO()
                    qr_img.save(buf, format='PNG')
                    buf.seek(0)
                    st.image(buf, width=200)
                
                with col2:
                    st.write(f"**Prescription ID:** {prescription['id']}")
                    st.write(f"**Numeric Code:** {prescription['code']}")
                    st.write(f"**Date:** {prescription['date']}")
                    st.markdown("**Medicines:**")
                    df = pd.DataFrame(prescription['medicines'])
                    st.dataframe(df, use_container_width=True)

# Main app logic
def main():
    if not st.session_state.authenticated:
        login_page()
    else:
        # Sidebar
        with st.sidebar:
            st.markdown("### 🏥 Medicine Dispenser")
            st.markdown(f"**User:** {st.session_state.current_user['name']}")
            st.markdown("---")
            
            if st.button("🏠 Home", use_container_width=True):
                st.session_state.page = 'home'
                st.rerun()
            
            if st.button("📤 Upload Prescription", use_container_width=True):
                st.session_state.page = 'upload'
                st.rerun()
            
            if st.button("📋 History", use_container_width=True):
                st.session_state.page = 'history'
                st.rerun()
            
            st.markdown("---")
            
            if st.button("🚪 Logout", use_container_width=True):
                st.session_state.authenticated = False
                st.session_state.current_user = None
                st.session_state.page = 'home'
                st.rerun()
        
        # Display current page
        if st.session_state.page == 'home':
            home_page()
        elif st.session_state.page == 'upload':
            upload_page()
        elif st.session_state.page == 'edit':
            edit_page()
        elif st.session_state.page == 'qr':
            qr_page()
        elif st.session_state.page == 'history':
            history_page()

if __name__ == "__main__":
    main()