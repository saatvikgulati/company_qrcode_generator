import streamlit as st
import segno
from PIL import Image
import json
import io
import os


# ---------------------------------------------------------
# Page configuration
# ---------------------------------------------------------

st.set_page_config(
    page_title="Contact QR Generator",
    page_icon="🪪",
    layout="centered"
)

st.title("🪪 Contact Details QR Code Generator")
st.write(
    "Fill out your information below to generate a scan-and-save "
    "contact vCard QR code."
)

BRAND_RED = "#B31F41"


# ---------------------------------------------------------
# Helper function
# ---------------------------------------------------------

def escape_vcard(value):
    """Escape special characters for a vCard 3.0 field."""
    if not value:
        return ""

    return (
        str(value)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
        .replace("\r", "")
    )


# ---------------------------------------------------------
# Contact form
# ---------------------------------------------------------

with st.form("contact_form", clear_on_submit=False):
    
    col1, col2 = st.columns(2)

    with col1:
        first_name = st.text_input(
            "First Name",
            placeholder="John"
        )

        mobile = st.text_input(
            "Mobile No.",
            placeholder="+91 XXXXX XXXXX"
        )

    with col2:
        last_name = st.text_input(
            "Last Name",
            placeholder="Doe"
        )

        wechat = st.text_input(
            "WeChat ID",
            placeholder="wxid_xxxxxx"
        )

    email = st.text_input(
        "Email Address",
        placeholder="name@totalmovements.com"
    )

    website = st.text_input(
        "Website",
        value="https://totalmovements.com",
        disabled=True
    )

    office_address = st.text_area(
        "Office Address",
        value=(
            "402, Malhotra Chambers, Arvind Vithal Gandhi Chowk, "
            "B.S.D. Marg, Off Govandi Station Road, Mumbai 400088, "
            "Maharashtra, India"
        ),
        disabled=True
    )

    presence = st.text_input(
        'Presence',
        value='INDIA | UAE | SAUDI | USA | MALAYSIA | INDONESIA | BANGLADESH'
    )

    submitted = st.form_submit_button(
        "Generate Designer QR Code"
    )


# ---------------------------------------------------------
# Process form submission
# ---------------------------------------------------------

if submitted:

    # Normalize possible None values
    first_name = first_name or ""
    last_name = last_name or ""
    mobile = mobile or ""
    wechat = wechat or ""
    email = email or ""
    presence = presence or ""

    # Validate required fields
    if not first_name or not last_name or not mobile:

        st.error(
            "⚠️ First Name, Last Name, and Mobile Number "
            "are required fields!"
        )

    else:

        try:

            # -------------------------------------------------
            # Build vCard 3.0
            # -------------------------------------------------

            vcard_data = (
                "BEGIN:VCARD\r\n"
                "VERSION:3.0\r\n"
                f"N:{escape_vcard(last_name)};"
                f"{escape_vcard(first_name)};;;\r\n"
                f"FN:{escape_vcard(first_name)} "
                f"{escape_vcard(last_name)}\r\n"
                f"TEL;TYPE=CELL:{escape_vcard(mobile)}\r\n"
                f"EMAIL;TYPE=INTERNET:{escape_vcard(email)}\r\n"
                f"URL:{escape_vcard(website)}\r\n"
                f"ADR;TYPE=WORK:;;"
                f"{escape_vcard(office_address)};;;;\r\n"
                f"NOTE:{escape_vcard(
                    'WeChat ID: ' + wechat +
                    '\\nPresence: ' + presence
                )}\r\n"
                "END:VCARD\r\n"
            )

            # -------------------------------------------------
            # Generate QR
            # -------------------------------------------------

            qr = segno.make(
                vcard_data,
                error="H",
                micro=False
            )

            # -------------------------------------------------
            # Render QR to PNG
            # -------------------------------------------------

            qr_buffer = io.BytesIO()

            qr.save(
                qr_buffer,
                kind="png",
                scale=10,
                border=4,
                dark=BRAND_RED,
                light="#FFFFFF"
            )

            qr_buffer.seek(0)

            qr_img = Image.open(qr_buffer).convert("RGBA")

            # -------------------------------------------------
            # Add center logo
            # -------------------------------------------------

            logo_path = "images/logo.png"

            if os.path.exists(logo_path):

                logo = Image.open(logo_path).convert("RGBA")

                # Logo approximately 18% of QR width
                max_logo_width = int(qr_img.width * 0.18)
                max_logo_height = int(qr_img.height * 0.18)

                logo.thumbnail(
                    (max_logo_width, max_logo_height),
                    Image.Resampling.LANCZOS
                )

                # White background around logo
                padding = 12

                logo_bg = Image.new(
                    "RGBA",
                    (
                        logo.width + padding * 2,
                        logo.height + padding * 2
                    ),
                    "white"
                )

                logo_bg.alpha_composite(
                    logo,
                    (padding, padding)
                )

                # Center logo
                x = (qr_img.width - logo_bg.width) // 2
                y = (qr_img.height - logo_bg.height) // 2

                qr_img.alpha_composite(
                    logo_bg,
                    (x, y)
                )

            else:

                st.warning(
                    "⚠️ 'logo.png' was not detected. "
                    "Generated a QR code without the center logo."
                )

            # -------------------------------------------------
            # Convert final image to PNG bytes
            # -------------------------------------------------

            img_buffer = io.BytesIO()

            qr_img.save(
                img_buffer,
                format="PNG"
            )

            img_bytes = img_buffer.getvalue()

            # -------------------------------------------------
            # Store QR in session state
            # -------------------------------------------------

            st.session_state["qr_image"] = img_bytes
            st.session_state["qr_filename"] = (
                f"TotalMovements_"
                f"{first_name}_{last_name}_QR.png"
            )
            st.session_state["qr_caption"] = (
                f"Total Movements Card: "
                f"{first_name} {last_name}"
            )

            st.success(
                "✅ QR Code generated successfully!"
            )

        except Exception as e:

            st.error(
                f"An unexpected technical problem occurred: {e}"
            )


# ---------------------------------------------------------
# DISPLAY QR + DOWNLOAD BUTTON
# IMPORTANT: OUTSIDE st.form()
# ---------------------------------------------------------

if "qr_image" in st.session_state:

    st.image(
        st.session_state["qr_image"],
        caption=st.session_state["qr_caption"],
        width=320
    )

    st.download_button(
        label="📥 Download Branded QR Code (PNG)",
        data=st.session_state["qr_image"],
        file_name=st.session_state["qr_filename"],
        mime="image/png"
    )