"""
Configuration and constant values for the Contact QR Generator app.

Kept separate from app.py so org-specific details (branding, default
address, validation rules, QR settings) can be updated without touching
the application logic.
"""

# ---------------------------------------------------------
# Branding
# ---------------------------------------------------------

BRAND_RED = "#B31F41"


# ---------------------------------------------------------
# Default / fixed contact details shown in the form
# ---------------------------------------------------------

DEFAULT_WEBSITE = "https://totalmovements.com"

DEFAULT_OFFICE_ADDRESS = (
    "402, Malhotra Chambers, Arvind Vithal Gandhi Chowk, "
    "B.S.D. Marg, Off Govandi Station Road, Mumbai 400088, "
    "Maharashtra, India"
)

# NOTE: this is a starting value only — the field remains editable by
# the user in the UI (st.text_input pre-fills it via `value=`, it does
# not lock it the way `disabled=True` does for the website field).
DEFAULT_PRESENCE = "INDIA | UAE | SAUDI | USA | MALAYSIA | INDONESIA | BANGLADESH"


# ---------------------------------------------------------
# Validation rules
# ---------------------------------------------------------

# Email addresses must belong to this domain.
ALLOWED_EMAIL_DOMAIN = "totalmovements.com"

# Maximum number of mobile-number rows a user can add.
MAX_MOBILE_ROWS = 5


# ---------------------------------------------------------
# QR code generation
# ---------------------------------------------------------

# Error-correction level. "Q" (~25% recovery) still leaves enough
# headroom for the center logo overlay while producing a noticeably
# less dense/cramped code than "H" (~30%), especially once the vCard
# carries several numbers + notes.
QR_ERROR_CORRECTION = "Q"
QR_SCALE = 10
QR_BORDER = 4
QR_LIGHT_COLOR = "#FFFFFF"


# ---------------------------------------------------------
# Logo overlay
# ---------------------------------------------------------

LOGO_RELATIVE_PATH = ("images", "logo.png")  # relative to app.py's directory
LOGO_SIZE_RATIO = 0.18   # logo width/height as a fraction of the QR width
LOGO_PADDING = 12        # white padding (px) around the logo before compositing