from __future__ import annotations

import re
import sys


TOKENS = {
    "ink": "#0E1A2B",
    "amber": "#E8A33D",
    "amber-deep": "#A8791A",
    "paper": "#F5F1EA",
    "paper-deep": "#ECE6DA",
    "ink-60": "#5B6878",
    "ink-20": "#7A8494",
    "paper-on-ink-body": "rgba(245, 241, 234, 0.85)",
    "paper-on-ink-legend": "rgba(245, 241, 234, 0.7)",
}

PAIRS = [
    ("body text", "ink", "paper", 4.5),
    ("body text on cards", "ink", "paper-deep", 4.5),
    ("inverse body text", "paper-on-ink-body", "ink", 4.5),
    ("inverse legend text", "paper-on-ink-legend", "ink", 4.5),
    ("footer legend text", "paper-on-ink-legend", "ink", 4.5),
    ("secondary text", "ink-60", "paper", 4.5),
    ("secondary text on cards", "ink-60", "paper-deep", 4.5),
    ("primary button label", "paper", "ink", 4.5),
    ("signal label on amber-deep", "ink", "amber-deep", 4.5),
    ("ghost button hover label", "ink", "paper-deep", 4.5),
    ("hairline", "ink-20", "paper", 3.0),
    ("strong hairline", "ink", "paper", 3.0),
    ("signal indicator on paper", "amber-deep", "paper", 3.0),
    ("signal indicator on ink", "amber", "ink", 3.0),
    ("focus outline on paper", "amber-deep", "paper", 3.0),
    ("input underline", "ink", "paper", 3.0),
    ("input underline focused", "amber-deep", "paper", 3.0),
]


RGBA_PATTERN = re.compile(
    r"rgba\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*([0-9]*\.?[0-9]+)\s*\)"
)


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))


def token_to_rgb(token_name: str, background_name: str | None = None) -> tuple[int, int, int]:
    token_value = TOKENS[token_name]
    if token_value.startswith("#"):
        return hex_to_rgb(token_value)
    if token_value.startswith("rgba"):
        if background_name is None:
            raise ValueError(f"RGBA token {token_name} requires a background")
        match = RGBA_PATTERN.fullmatch(token_value)
        if match is None:
            raise ValueError(f"Unsupported RGBA token format: {token_value}")
        foreground_red, foreground_green, foreground_blue = (
            int(match.group(index)) for index in range(1, 4)
        )
        alpha = float(match.group(4))
        background_red, background_green, background_blue = token_to_rgb(background_name)
        blended = []
        for foreground_channel, background_channel in (
            (foreground_red, background_red),
            (foreground_green, background_green),
            (foreground_blue, background_blue),
        ):
            blended.append(
                round((alpha * foreground_channel) + ((1 - alpha) * background_channel))
            )
        return tuple(blended)
    raise ValueError(f"Unsupported token format: {token_value}")


def srgb_channel_to_linear(channel: int) -> float:
    srgb = channel / 255
    if srgb <= 0.03928:
        return srgb / 12.92
    return ((srgb + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb: tuple[int, int, int]) -> float:
    red, green, blue = rgb
    red_linear = srgb_channel_to_linear(red)
    green_linear = srgb_channel_to_linear(green)
    blue_linear = srgb_channel_to_linear(blue)
    return (0.2126 * red_linear) + (0.7152 * green_linear) + (0.0722 * blue_linear)


def contrast_ratio(
    foreground_name: str, background_name: str
) -> float:
    foreground_luminance = relative_luminance(token_to_rgb(foreground_name, background_name))
    background_luminance = relative_luminance(token_to_rgb(background_name))
    lighter = max(foreground_luminance, background_luminance)
    darker = min(foreground_luminance, background_luminance)
    return (lighter + 0.05) / (darker + 0.05)


def main() -> int:
    passed = 0
    total = len(PAIRS)

    for role, foreground_name, background_name, required_ratio in PAIRS:
        ratio = contrast_ratio(foreground_name, background_name)
        status = "PASS" if ratio >= required_ratio else "FAIL"
        if status == "PASS":
            passed += 1
        print(
            f"{role:<28} {foreground_name:<8} on {background_name:<10} "
            f"{ratio:>6.2f}:1  required {required_ratio:>3.1f}  {status}"
        )

    failures = total - passed
    print(f"{passed}/{total} pairs pass WCAG AA. {failures} failure(s).")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
