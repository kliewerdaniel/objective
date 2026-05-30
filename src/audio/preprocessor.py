"""TTS text pre-processing: abbreviation expansion, number normalization, pause insertion."""

import re


class TTSProcessor:
    """Prepares text for TTS synthesis by expanding abbreviations,
    normalizing numbers and symbols, and adding natural pause markers."""

    ABBREVIATION_MAP = {
        "e.g.": "for example",
        "i.e.": "that is",
        "vs.": "versus",
        "approx.": "approximately",
        "dept.": "department",
        "govt.": "government",
        "est.": "estimated",
        "cont.": "continued",
        "info.": "information",
        "admin.": "administration",
        "org.": "organization",
        "assn.": "association",
        "dept": "department",
        "govt": "government",
        "est": "estimated",
        "cont": "continued",
    }

    MONTH_ABBREV = {
        "Jan.": "January", "Feb.": "February", "Mar.": "March",
        "Apr.": "April", "Jun.": "June", "Jul.": "July",
        "Aug.": "August", "Sep.": "September", "Oct.": "October",
        "Nov.": "November", "Dec.": "December",
    }

    def preprocess(self, text: str) -> str:
        text = self._strip_non_speech(text)
        text = self._expand_abbreviations(text)
        text = self._expand_month_abbrevs(text)
        text = self._normalize_dollars(text)
        text = self._normalize_percentages(text)
        text = self._normalize_dates(text)
        text = self._normalize_numbers(text)
        text = self._normalize_pauses(text)
        return text

    def _expand_abbreviations(self, text: str) -> str:
        for abbr, expansion in self.ABBREVIATION_MAP.items():
            if abbr.endswith("."):
                text = re.sub(
                    r'\b' + re.escape(abbr) + r'(?=\s|$|[,.!?;])',
                    expansion, text, flags=re.IGNORECASE,
                )
            else:
                text = re.sub(
                    r'\b' + re.escape(abbr) + r'\b',
                    expansion, text, flags=re.IGNORECASE,
                )
        return text

    def _expand_month_abbrevs(self, text: str) -> str:
        for abbr, expansion in self.MONTH_ABBREV.items():
            text = re.sub(
                r'\b' + re.escape(abbr) + r'(?=\s|$|[,.!?;])',
                expansion, text,
            )
        return text

    def _normalize_numbers(self, text: str) -> str:
        # Spell out standalone digits 0-20 as words for natural TTS
        # Process largest first to avoid partial matches
        replacements = [
            (20, "twenty"), (19, "nineteen"), (18, "eighteen"),
            (17, "seventeen"), (16, "sixteen"), (15, "fifteen"),
            (14, "fourteen"), (13, "thirteen"), (12, "twelve"),
            (11, "eleven"), (10, "ten"),
            (9, "nine"), (8, "eight"), (7, "seven"), (6, "six"),
            (5, "five"), (4, "four"), (3, "three"), (2, "two"),
            (1, "one"), (0, "zero"),
        ]
        for num, word in replacements:
            text = re.sub(r'\b' + str(num) + r'\b', word, text)
        return text

    def _normalize_percentages(self, text: str) -> str:
        return re.sub(r'(\d+)%', r'\1 percent', text)

    def _normalize_dollars(self, text: str) -> str:
        # $X million/billion/trillion
        text = re.sub(
            r'(?<!\w)\$(\d+(?:\.\d+)?)\s*(million|billion|trillion)\b',
            lambda m: f"{m.group(1)} {m.group(2)} dollars",
            text, flags=re.IGNORECASE,
        )
        # $X standalone
        text = re.sub(
            r'(?<!\w)\$(\d+(?:\.\d+)?)\b',
            lambda m: f"{m.group(1)} dollars",
            text,
        )
        return text

    def _normalize_dates(self, text: str) -> str:
        # ISO date: 2026-05-29 -> "May 29th, 2026"
        text = re.sub(r'(\d{4})-(\d{2})-(\d{2})', self._replace_iso_date, text)
        return text

    def _replace_iso_date(self, m: re.Match) -> str:
        months = [
            "", "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ]
        year = m.group(1)
        month = int(m.group(2))
        day = int(m.group(3))
        suffix = "th" if 11 <= day <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
        return f"{months[month]} {day}{suffix}, {year}"

    def _normalize_pauses(self, text: str) -> str:
        # Ellipsis -> comma-like pause
        text = text.replace("...", ",")
        # Multiple exclamation/question marks -> single
        text = re.sub(r'!{2,}', '!', text)
        text = re.sub(r'\?{2,}', '?', text)
        return text

    def _strip_non_speech(self, text: str) -> str:
        # Remove markdown-style links
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        # Remove bare URLs
        text = re.sub(r'https?://\S+', '', text)
        # Remove angle-bracket tags
        text = re.sub(r'<[^>]+>', '', text)
        # Collapse whitespace
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
