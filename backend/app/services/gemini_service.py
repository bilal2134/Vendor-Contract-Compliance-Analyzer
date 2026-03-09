from __future__ import annotations

from app.core.settings import get_settings

settings = get_settings()


class GeminiService:
    def __init__(self) -> None:
        self.enabled = False
        self.client = None
        self.backend = None
        if not settings.gemini_api_key:
            return
        try:
            from google import genai  # pragma: no cover - optional dependency

            self.client = genai.Client(api_key=settings.gemini_api_key)
            self.backend = "google-genai"
            self.enabled = True
            return
        except Exception:  # pragma: no cover - optional dependency
            self.client = None

        try:
            import google.generativeai as legacy_genai  # pragma: no cover - optional dependency

            legacy_genai.configure(api_key=settings.gemini_api_key)
            self.client = legacy_genai.GenerativeModel(settings.gemini_model)
            self.backend = "google-generativeai"
            self.enabled = True
        except Exception:  # pragma: no cover - defensive initialization
            self.client = None
            self.backend = None
            self.enabled = False

    def summarize_finding(self, requirement_text: str, evidence: list[str], fallback: str) -> str:
        if not self.enabled or self.client is None or not evidence:
            return fallback
        prompt = (
            "Summarize this procurement compliance finding in 2 concise sentences. "
            "Use only the provided requirement and evidence.\n\n"
            f"Requirement: {requirement_text}\n\nEvidence:\n- " + "\n- ".join(evidence)
        )
        try:
            if self.backend == "google-genai":
                response = self.client.models.generate_content(model=settings.gemini_model, contents=prompt)
            else:
                response = self.client.generate_content(prompt)
            text = getattr(response, "text", "") or fallback
            return text.strip() or fallback
        except Exception:
            return fallback


gemini_service = GeminiService()
