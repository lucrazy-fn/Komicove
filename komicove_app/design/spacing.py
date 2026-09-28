"""Layout tokens shared by every redesigned desktop screen.

The references use three clear corner families.  Keeping them here prevents
buttons, fields and large panels from slowly drifting into unrelated styles.
"""

SIDEBAR_WIDTH = 246
CONTENT_PADDING = 30

RADIUS_SMALL = 10
RADIUS_MEDIUM = 15
RADIUS_LARGE = 22
RADIUS_XLARGE = 26
RADIUS_PILL = 999

# Backwards-compatible name used by a few older redesigned controls.
RADIUS = RADIUS_MEDIUM

# A strict 4 px spacing scale.  New UI should use these tokens instead of
# introducing one-off padding values.
SPACE = {
    "xxs": 4,
    "xs": 8,
    "sm": 12,
    "md": 16,
    "lg": 20,
    "xl": 24,
    "xxl": 32,
    "hero": 40,
}
