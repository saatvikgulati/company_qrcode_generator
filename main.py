import streamlit as st
import segno
from PIL import Image
from pathlib import Path
from dataclasses import dataclass
import io
import os
import re

import config


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


# ---------------------------------------------------------
# General helpers
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
    Validate that the email address belongs to the allowed domain.
    """

    p_email = p_email.strip().lower()

    if not p_email:
        return True, ""

    # Basic email format + required domain
    pattern = r"[A-Za-z0-9._%+-]+@" + re.escape(config.ALLOWED_EMAIL_DOMAIN)
    if not re.fullmatch(pattern, p_email):
        return False, (
            f"Email address must be a valid @{config.ALLOWED_EMAIL_DOMAIN} "
            f"email address. Example: name@{config.ALLOWED_EMAIL_DOMAIN}"
        )

    return True, ""


# ---------------------------------------------------------
# MobileEntry: one mobile-number row, with the formatting/
# validation rules for that single entry attached to it
# ---------------------------------------------------------

@dataclass
class MobileEntry:
    number: str
    type: str  # "Work" or "WeChat"

    def looks_like_phone_number(self):
        """
        Heuristic used only for WeChat entries: does this value look
        like a phone number (digits, optional '+', spaces/dashes)
        rather than a WeChat ID such as 'wxid_xxxxxx'? Numbers get
        shown as a real contact entry; IDs go into Notes since a
        phone field shouldn't hold non-numeric text.
        """
        cleaned = re.sub(r"[\s\-]", "", self.number.strip())
        return bool(re.fullmatch(r"\+?[0-9]{6,15}", cleaned))

    def is_dialable(self):
        """Would this entry end up as an actual TEL line in the vCard?"""
        return self.type == "Work" or self.looks_like_phone_number()

    def validate(self):
        """
        Only Work-type numbers are validated as international phone
        numbers. WeChat entries can be an ID or a number in any
        format, so no country-code check is applied to them.
        """
        if self.type == "Work":
            return validate_phone_number(self.number)
        return True, ""

    def to_tel_line(self):
        """
        The TEL line for this entry, or None if it belongs in NOTE
        instead (a non-numeric WeChat ID).

        WeChat numbers get TYPE=WeChat only (no CELL alongside it) so
        contact apps show the custom "WeChat" label instead of
        matching the recognized CELL token and showing "Mobile".
        """
        if self.type == "WeChat":
            if self.looks_like_phone_number():
                return f"TEL;TYPE=WeChat:{escape_vcard(self.number)}\r\n"
            return None
        return f"TEL;TYPE=CELL,WORK:{escape_vcard(self.number)}\r\n"

    def note_line(self):
        """A NOTE contribution for this entry (WeChat IDs only), else None."""
        if self.type == "WeChat" and not self.looks_like_phone_number():
            return f"WeChat ID: {self.number}"
        return None

    def dedup_key(self):
        """Key used to detect duplicate entries, ignoring spaces/dashes/case."""
        normalized_number = re.sub(r"[\s\-]", "", self.number.strip()).lower()
        return self.type, normalized_number


def dedupe_mobile_entries(entries):
    """
    Remove duplicate mobile entries (same type + same number, ignoring
    spaces/dashes/case) so the vCard doesn't end up with repeated TEL
    lines from accidental double entry.
    """
    seen = set()
    deduped = []
    for entry in entries:
        key = entry.dedup_key()
        if key not in seen:
            seen.add(key)
            deduped.append(entry)
    return deduped


def gather_mobile_entries():
    """Collect non-empty mobile entries from session state, de-duplicated."""
    entries = []
    for i in st.session_state.mobile_ids:
        number = (st.session_state.get(f"mobile_number_{i}", "") or "").strip()
        mtype = st.session_state.get(f"mobile_type_{i}", "Work")
        if number:
            entries.append(MobileEntry(number=number, type=mtype))
    return dedupe_mobile_entries(entries)


# ---------------------------------------------------------
# VCardBuilder: holds the full set of contact fields and
# knows how to validate itself and produce vCard 3.0 text
# ---------------------------------------------------------

class VCardBuilder:

    def __init__(self, f_name, l_name, email_addr, c_website, address,
                 pres, mobiles):
        self.first_name = f_name
        self.last_name = l_name
        self.email = email_addr
        self.website = c_website
        self.office_address = address
        self.presence = pres
        self.mobile_entries = mobiles  # list[MobileEntry], already de-duped

    def validate(self):
        """Return a list of error messages; an empty list means the data is ready to build."""
        if not self.first_name or not self.last_name or not self.mobile_entries:
            return [
                "First Name, Last Name, and at least one Mobile Number "
                "are required fields!"
            ]

        error_s= []

        for entry in self.mobile_entries:
            valid, error = entry.validate()
            if not valid:
                error_s.append(f"'{entry.number}' ({entry.type}) {error}")

        email_valid, email_error = validate_email(self.email)
        if not email_valid:
            error_s.append(email_error)

        # A vCard whose only mobile entries are non-numeric WeChat IDs
        # (routed to NOTE, not TEL) would end up with no dialable
        # number at all — require at least one entry that resolves to
        # an actual TEL line.
        if not any(entry.is_dialable() for entry in self.mobile_entries):
            error_s.append(
                "At least one mobile number must be a dialable number "
                "(a Work number, or a WeChat number rather than a WeChat ID)."
            )

        return error_s

    def _build_tel_block_and_note(self):
        tel_lines = [
            line for entry in self.mobile_entries
            if (line := entry.to_tel_line()) is not None
        ]
        note_parts = [
            line for entry in self.mobile_entries
            if (line := entry.note_line()) is not None
        ]

        if self.presence:
            note_parts.append(f"Presence: {self.presence}")

        return "".join(tel_lines), "\n".join(note_parts)

    def build(self):
        """Assemble and return the full vCard 3.0 text. Call validate() first."""
        tel_block, note = self._build_tel_block_and_note()

        return (
            "BEGIN:VCARD\r\n"
            "VERSION:3.0\r\n"
            f"N:{escape_vcard(self.last_name)};"
            f"{escape_vcard(self.first_name)};;;\r\n"
            f"FN:{escape_vcard(self.first_name)} "
            f"{escape_vcard(self.last_name)}\r\n"
            f"{tel_block}"
            f"EMAIL;TYPE=WORK:{escape_vcard(self.email)}\r\n"
            f"URL:{escape_vcard(self.website)}\r\n"
            f"ADR;TYPE=WORK:;;"
            f"{escape_vcard(self.office_address)};;;;\r\n"
            f"NOTE:{escape_vcard(note)}\r\n"
            "END:VCARD\r\n"
        )


# ---------------------------------------------------------
# QRRenderer: turns vCard text into a branded PNG, with the
# center-logo overlay
# ---------------------------------------------------------

class QRRenderer:

    def __init__(self, error_correction, scale, border, dark_color, light_color,
                 logo_p, logo_size_ratio, logo_padding):
        self.error_correction = error_correction
        self.scale = scale
        self.border = border
        self.dark_color = dark_color
        self.light_color = light_color
        self.logo_path = logo_p
        self.logo_size_ratio = logo_size_ratio
        self.logo_padding = logo_padding

    @classmethod
    def from_config(cls, logo_p):
        """Build a renderer using the shared settings from config.py."""
        return cls(
            error_correction=config.QR_ERROR_CORRECTION,
            scale=config.QR_SCALE,
            border=config.QR_BORDER,
            dark_color=config.BRAND_RED,
            light_color=config.QR_LIGHT_COLOR,
            logo_p=logo_p,
            logo_size_ratio=config.LOGO_SIZE_RATIO,
            logo_padding=config.LOGO_PADDING,
        )

    def _compose_logo(self, qr_img):
        """Paste a white-padded, centered logo onto qr_img in place."""
        logo = Image.open(self.logo_path).convert("RGBA")

        max_logo_width = int(qr_img.width * self.logo_size_ratio)
        max_logo_height = int(qr_img.height * self.logo_size_ratio)
        logo.thumbnail((max_logo_width, max_logo_height), Image.Resampling.LANCZOS)

        padding = self.logo_padding
        logo_bg = Image.new(
            "RGBA",
            (logo.width + padding * 2, logo.height + padding * 2),
            "white"
        )
        logo_bg.alpha_composite(logo, (padding, padding))

        x = (qr_img.width - logo_bg.width) // 2
        y = (qr_img.height - logo_bg.height) // 2
        qr_img.alpha_composite(logo_bg, (x, y))

    def render(self, vcard_d):
        """
        Generate the branded QR PNG for the given vCard text.
        Returns (img_bytes, logo_found) so the caller can warn the
        user if the logo file was missing.
        """
        qr = segno.make(vcard_d, error=self.error_correction, micro=False)

        qr_buffer = io.BytesIO()
        qr.save(
            qr_buffer,
            kind="png",
            scale=self.scale,
            border=self.border,
            dark=self.dark_color,
            light=self.light_color
        )
        qr_buffer.seek(0)

        qr_img = Image.open(qr_buffer).convert("RGBA")

        logo_f = os.path.exists(self.logo_path)
        if logo_f:
            self._compose_logo(qr_img)

        img_buffer = io.BytesIO()
        qr_img.save(img_buffer, format="PNG")

        return img_buffer.getvalue(), logo_f


# ---------------------------------------------------------
# Dynamic mobile-number rows (kept OUTSIDE any st.form,
# since add/remove buttons need to rerun immediately)
# ---------------------------------------------------------

if "next_mobile_id" not in st.session_state:
    st.session_state.next_mobile_id = 1

if "mobile_ids" not in st.session_state:
    st.session_state.mobile_ids = [st.session_state.next_mobile_id]
    st.session_state.next_mobile_id += 1


def add_mobile_row():
    if len(st.session_state.mobile_ids) < config.MAX_MOBILE_ROWS:
        st.session_state.mobile_ids.append(st.session_state.next_mobile_id)
        st.session_state.next_mobile_id += 1


def remove_mobile_row(i):
    st.session_state.mobile_ids.remove(i)
    st.session_state.pop(f"mobile_number_{i}", None)
    st.session_state.pop(f"mobile_type_{i}", None)


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
    placeholder=f"name@{config.ALLOWED_EMAIL_DOMAIN}"
)

website = st.text_input(
    "Website",
    value=config.DEFAULT_WEBSITE,
    disabled=True
)

office_address = st.text_area(
    "Office Address",
    value=config.DEFAULT_OFFICE_ADDRESS,
)

presence = st.text_input(
    "Presence",
    value=config.DEFAULT_PRESENCE,
    help="Editable — update this list if the company's presence changes.",
)


# ---------------------------------------------------------
# Mobile numbers section
# ---------------------------------------------------------

st.markdown("**Mobile Numbers**")
st.caption(
    "Add one or more numbers with country code (e.g. +919876543210) "
    "and mark each as Work or WeChat. "
    f"Maximum {config.MAX_MOBILE_ROWS} numbers."
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

st.button(
    "➕ Add another mobile number",
    on_click=add_mobile_row,
    disabled=len(st.session_state.mobile_ids) >= config.MAX_MOBILE_ROWS,
)

st.divider()

submitted = st.button("Generate Designer QR Code", type="primary")


# ---------------------------------------------------------
# Process form submission
# ---------------------------------------------------------

if submitted:

    first_name = (first_name or "").strip()
    last_name = (last_name or "").strip()
    email = email or ""
    presence = presence or ""

    mobile_entries = gather_mobile_entries()

    vcard_builder = VCardBuilder(
        f_name=first_name,
        l_name=last_name,
        email_addr=email,
        c_website=website,
        address=office_address,
        pres=presence,
        mobiles=mobile_entries,
    )
    errors = vcard_builder.validate()

    if errors:
        for err in errors:
            st.error(f"⚠️ {err}")
    else:
        try:
            vcard_data = vcard_builder.build()

            logo_path = Path(__file__).resolve().parent.joinpath(
                *config.LOGO_RELATIVE_PATH
            )
            qr_renderer = QRRenderer.from_config(logo_path)
            img_bytes, logo_found = qr_renderer.render(vcard_data)

            if not logo_found:
                st.warning(
                    "⚠️ 'logo.png' was not detected. "
                    "Generated a QR code without the center logo."
                )

            st.session_state["qr_image"] = img_bytes
            st.session_state["qr_filename"] = (
                f"TotalMovements_{first_name}_{last_name}_QR.png"
            )
            st.session_state["qr_caption"] = (
                f"Total Movements Card: {first_name} {last_name}"
            )

            st.success("✅ QR Code generated successfully!")

        except Exception as e:
            st.error(f"An unexpected technical problem occurred: {e}")


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