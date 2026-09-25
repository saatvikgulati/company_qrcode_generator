import streamlit as st
import segno
from PIL import Image
from pathlib import Path
import io
import os
import re
import itertools


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
# Helper functions
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


def validate_phone_number(phone):
    """
    Validate an international phone number.

    Expected format:
    +<country code><phone number>

    Example:
    +919876543210
    +971501234567
    +12125551234
    """

    phone = phone.strip()

    # Must start with +
    if not phone.startswith("+"):
        return False, "must include the country code and start with '+'."

    # Only + followed by digits
    if not re.fullmatch(r"\+[0-9]+", phone):
        return False, (
            "can contain only '+' followed by digits. "
            "Example: +919876543210"
        )

    # E.164 maximum length is 15 digits excluding +
    digit_count = len(phone) - 1

    if digit_count > 15:
        return False, "is too long. Maximum is 15 digits."

    # Basic minimum length
    if digit_count < 8:
        return False, "is not a valid international mobile number."

    return True, ""


def validate_email(p_email):
    """
    Validate that the email address belongs to totalmovements.com.
    """

    p_email = p_email.strip().lower()

    if not p_email:
        return True, ""

    # Basic email format + required domain
    if not re.fullmatch(
        r"[A-Za-z0-9._%+-]+@totalmovements\.com",
        p_email
    ):
        return False, (
            "Email address must be a valid @totalmovements.com email address. "
            "Example: name@totalmovements.com"
        )

    return True, ""


def looks_like_phone_number(value):
    """
    Heuristic used only for WeChat entries: does this value look like
    a phone number (digits, optional '+', spaces/dashes) rather than
    a WeChat ID such as 'wxid_xxxxxx'? Numbers get shown as a real
    contact entry; IDs go into Notes since a phone field shouldn't
    hold non-numeric text.
    """
    cleaned = re.sub(r"[\s\-]", "", value.strip())
    return bool(re.fullmatch(r"\+?[0-9]{6,15}", cleaned))


# ---------------------------------------------------------
# Dynamic mobile-number rows (kept OUTSIDE any st.form,
# since add/remove buttons need to rerun immediately)
# ---------------------------------------------------------

if "mobile_id_counter" not in st.session_state:
    st.session_state.mobile_id_counter = itertools.count(1)

if "mobile_ids" not in st.session_state:
    st.session_state.mobile_ids = [next(st.session_state.mobile_id_counter)]


def add_mobile_row():
    st.session_state.mobile_ids.append(next(st.session_state.mobile_id_counter))


def remove_mobile_row(mobile_id):
    st.session_state.mobile_ids.remove(mobile_id)
    st.session_state.pop(f"mobile_number_{mobile_id}", None)
    st.session_state.pop(f"mobile_type_{mobile_id}", None)


# ---------------------------------------------------------
# Contact details
# ---------------------------------------------------------

col1, col2 = st.columns(2)

with col1:
    first_name = st.text_input(
        "First Name",
        placeholder="John"
    )

with col2:
    last_name = st.text_input(
        "Last Name",
        placeholder="Doe"
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
)

presence = st.text_input(
    'Presence',
    value='INDIA | UAE | SAUDI | USA | MALAYSIA | INDONESIA | BANGLADESH'
)


# ---------------------------------------------------------
# Mobile numbers section
# ---------------------------------------------------------

st.markdown("**Mobile Numbers**")
st.caption(
    "Add one or more numbers with country code (e.g. +919876543210) "
    "and mark each as Work or WeChat."
)

for mobile_id in list(st.session_state.mobile_ids):

    # Look up this row's currently selected type (already updated in
    # session_state by the time this runs, even on the rerun triggered
    # by changing the selectbox itself) so we can adapt the number
    # field's placeholder/help text and, later, its validation rules.
    current_type = st.session_state.get(f"mobile_type_{mobile_id}", "Work")

    row_col1, row_col2, row_col3 = st.columns([3, 2, 1])

    with row_col1:
        if current_type == "WeChat":
            st.text_input(
                "Mobile No.",
                key=f"mobile_number_{mobile_id}",
                placeholder="wxid_xxxxxx or WeChat mobile number",
                help="WeChat ID or number — no country-code format required.",
            )
        else:
            st.text_input(
                "Mobile No.",
                key=f"mobile_number_{mobile_id}",
                placeholder="+91XXXXXXXXXX",
                help="Enter the number with country code, e.g. +919876543210",
            )

    with row_col2:
        st.selectbox(
            "Type",
            options=["Work", "WeChat"],
            key=f"mobile_type_{mobile_id}",
        )

    with row_col3:
        st.markdown("&nbsp;", unsafe_allow_html=True)  # align button with inputs
        if len(st.session_state.mobile_ids) > 1:
            st.button(
                "✖",
                key=f"remove_btn_{mobile_id}",
                on_click=remove_mobile_row,
                args=(mobile_id,),
                help="Remove this number"
            )

st.button("➕ Add another mobile number", on_click=add_mobile_row)

st.divider()

submitted = st.button("Generate Designer QR Code", type="primary")


# ---------------------------------------------------------
# Process form submission
# ---------------------------------------------------------

if submitted:

    # Normalize possible None values
    first_name = first_name or ""
    last_name = last_name or ""
    email = email or ""
    presence = presence or ""

    # Gather mobile entries from session state
    mobile_entries = []
    for mobile_id in st.session_state.mobile_ids:
        number = (st.session_state.get(f"mobile_number_{mobile_id}", "") or "").strip()
        mtype = st.session_state.get(f"mobile_type_{mobile_id}", "Work")
        if number:
            mobile_entries.append({"number": number, "type": mtype})

    # Validate required fields
    if not first_name or not last_name or not mobile_entries:

        st.error(
            "⚠️ First Name, Last Name, and at least one Mobile Number "
            "are required fields!"
        )

    else:
        errors = []

        # Only Work-type numbers are validated as international
        # phone numbers. WeChat entries can be an ID or a number in
        # any format, so no country-code check is applied to them.
        for entry in mobile_entries:
            if entry["type"] == "Work":
                phone_valid, phone_error = validate_phone_number(entry["number"])
                if not phone_valid:
                    errors.append(f"'{entry['number']}' (Work) {phone_error}")

        email_valid, email_error = validate_email(email)
        if not email_valid:
            errors.append(email_error)

        if errors:
            for err in errors:
                st.error(f"⚠️ {err}")
        else:
            try:
                # -------------------------------------------------
                # Build TEL lines.
                #
                # Work numbers: standard TYPE=CELL,WORK.
                #
                # WeChat numbers: TYPE=WECHAT only (no CELL alongside
                # it). If a standard type like CELL is included in
                # the same TYPE list, most Android contact apps match
                # that recognized token first and show "Mobile"
                # instead of the custom one. With only an unrecognized
                # type present, apps typically fall back to showing
                # the literal token as the label ("Wechat").
                #
                # WeChat IDs (non-numeric, e.g. "wxid_xxxxxx") aren't
                # valid phone field content, so those stay in NOTE
                # instead of becoming a TEL entry.
                # -------------------------------------------------

                tel_lines = []
                note_parts = []

                for entry in mobile_entries:
                    if entry["type"] == "WeChat":
                        if looks_like_phone_number(entry["number"]):
                            number = escape_vcard(entry["number"])
                            tel_lines.append(f"TEL;TYPE=WeChat:{number}\r\n")
                        else:
                            note_parts.append(f'WeChat ID: {entry["number"]}')
                    else:
                        number = escape_vcard(entry["number"])
                        tel_lines.append(f"TEL;TYPE=CELL,WORK:{number}\r\n")

                tel_block = "".join(tel_lines)

                if presence:
                    note_parts.append(f'Presence: {presence}')

                note = '\n'.join(note_parts)

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
                    f"{tel_block}"
                    f"EMAIL;TYPE=WORK:{escape_vcard(email)}\r\n"
                    f"URL:{escape_vcard(website)}\r\n"
                    f"ADR;TYPE=WORK:;;"
                    f"{escape_vcard(office_address)};;;;\r\n"
                    f"NOTE:{escape_vcard(note)}\r\n"
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
                logo_path = Path(__file__).resolve().parent / 'images' / 'logo.png'

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