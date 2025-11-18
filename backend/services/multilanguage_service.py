"""
Multi-Language Support Service
Supports English, Hindi, and regional Indian languages
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class Language:
    """Language configuration"""
    code: str
    name: str
    native_name: str
    rtl: bool = False  # Right-to-left
    legal_support: bool = True


class MultiLanguageService:
    """
    Multi-language support for legal AI

    Supported languages:
    - English
    - Hindi
    - Tamil
    - Telugu
    - Marathi
    - Bengali
    - Gujarati
    - Kannada
    - Malayalam
    - Punjabi
    - Urdu
    - Odia
    """

    def __init__(self):
        self.languages = self._initialize_languages()
        self.translations = self._load_translations()

    def _initialize_languages(self) -> Dict[str, Language]:
        """Initialize supported languages"""

        return {
            "en": Language("en", "English", "English", legal_support=True),
            "hi": Language("hi", "Hindi", "हिन्दी", legal_support=True),
            "ta": Language("ta", "Tamil", "தமிழ்", legal_support=True),
            "te": Language("te", "Telugu", "తెలుగు", legal_support=True),
            "mr": Language("mr", "Marathi", "मराठी", legal_support=True),
            "bn": Language("bn", "Bengali", "বাংলা", legal_support=True),
            "gu": Language("gu", "Gujarati", "ગુજરાતી", legal_support=True),
            "kn": Language("kn", "Kannada", "ಕನ್ನಡ", legal_support=True),
            "ml": Language("ml", "Malayalam", "മലയാളം", legal_support=True),
            "pa": Language("pa", "Punjabi", "ਪੰਜਾਬੀ", legal_support=True),
            "ur": Language("ur", "Urdu", "اردو", rtl=True, legal_support=True),
            "or": Language("or", "Odia", "ଓଡ଼ିଆ", legal_support=True),
        }

    def _load_translations(self) -> Dict[str, Dict[str, str]]:
        """Load translation strings for UI"""

        return {
            "common": {
                "welcome": {
                    "en": "Welcome to Lawyer.ly",
                    "hi": "Lawyer.ly में आपका स्वागत है",
                    "ta": "Lawyer.ly க்கு வரவேற்கிறோம்",
                    "te": "Lawyer.ly కి స్వాగతం",
                },
                "search": {
                    "en": "Search",
                    "hi": "खोजें",
                    "ta": "தேடு",
                    "te": "వెతకండి",
                },
                "upload_document": {
                    "en": "Upload Document",
                    "hi": "दस्तावेज़ अपलोड करें",
                    "ta": "ஆவணத்தைப் பதிவேற்று",
                    "te": "డాక్యుమెంట్ను అప్‌లోడ్ చేయండి",
                }
            },
            "legal": {
                "case_law": {
                    "en": "Case Law",
                    "hi": "मामला कानून",
                    "ta": "வழக்கு சட்டம்",
                    "te": "కేసు చట్టం",
                },
                "statute": {
                    "en": "Statute",
                    "hi": "विधि",
                    "ta": "சட்டம்",
                    "te": "శాసనం",
                },
                "judgment": {
                    "en": "Judgment",
                    "hi": "निर्णय",
                    "ta": "தீர்ப்பு",
                    "te": "తీర్పు",
                }
            }
        }

    def get_supported_languages(self) -> List[Dict[str, Any]]:
        """Get list of supported languages"""

        return [
            {
                "code": lang.code,
                "name": lang.name,
                "native_name": lang.native_name,
                "rtl": lang.rtl,
                "legal_support": lang.legal_support
            }
            for lang in self.languages.values()
        ]

    def translate(
        self,
        key: str,
        lang_code: str,
        category: str = "common"
    ) -> str:
        """Get translation for a key"""

        if category in self.translations and key in self.translations[category]:
            translations = self.translations[category][key]
            return translations.get(lang_code, translations.get("en", key))

        return key

    async def translate_text(
        self,
        text: str,
        source_lang: str,
        target_lang: str
    ) -> str:
        """Translate text using AI/translation service"""

        if source_lang == target_lang:
            return text

        # Would use Azure Translator or Google Translate API
        logger.info(f"Translating from {source_lang} to {target_lang}")

        # Placeholder - in production use actual translation API
        return f"[Translated to {target_lang}]: {text}"

    def get_legal_terms(self, lang_code: str) -> Dict[str, str]:
        """Get legal terminology in specified language"""

        legal_terms = {
            "en": {
                "plaintiff": "Plaintiff",
                "defendant": "Defendant",
                "petition": "Petition",
                "judgment": "Judgment",
                "appeal": "Appeal",
                "writ": "Writ",
                "bail": "Bail",
                "evidence": "Evidence",
            },
            "hi": {
                "plaintiff": "वादी",
                "defendant": "प्रतिवादी",
                "petition": "याचिका",
                "judgment": "निर्णय",
                "appeal": "अपील",
                "writ": "रिट",
                "bail": "जमानत",
                "evidence": "साक्ष्य",
            },
            "ta": {
                "plaintiff": "வாதி",
                "defendant": "பிரதிவாதி",
                "petition": "மனு",
                "judgment": "தீர்ப்பு",
                "appeal": "மேல்முறையீடு",
                "writ": "ரிட்",
                "bail": "ஜாமீன்",
                "evidence": "சான்று",
            }
        }

        return legal_terms.get(lang_code, legal_terms["en"])


# Global instance
multilanguage_service = MultiLanguageService()
