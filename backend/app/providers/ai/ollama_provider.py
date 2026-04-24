import json

import httpx

from app.providers.ai.base import AIEvaluation, AIProvider


class OllamaProvider(AIProvider):
    def __init__(self, endpoint: str, model: str) -> None:
        self.endpoint = endpoint
        self.model = model

    def _fallback(self, payload: dict) -> AIEvaluation:
        price = payload.get("current_price") or 0
        return AIEvaluation(
            fundamental_score=6,
            moat_score=6,
            moat_text="Lokaler KI-Provider (Fallback-Ausgabe, kein LLM-Aufruf).",
            fair_value_dcf=price * 1.08,
            fair_value_nav=price * 1.04,
            recommendation="risk_buy",
            recommendation_reason="Fallback-Ausgabe fuer lokalen Provider.",
            risk_notes="Lokale Modellqualitaet pruefen.",
            estimated_cost=0.0,
            is_fallback=True,
        )

    async def evaluate(self, payload: dict) -> AIEvaluation:
        prompt = (
            "Antworte nur als JSON mit den Feldern fundamental_score, moat_score, moat_text, "
            "fair_value_dcf, fair_value_nav, recommendation, recommendation_reason, risk_notes. "
            f"Eingabedaten: {json.dumps(payload, ensure_ascii=True)}"
        )
        body = {"model": self.model, "prompt": prompt, "stream": False, "format": "json"}
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(self.endpoint, json=body)
                response.raise_for_status()
                data = response.json()
            parsed = json.loads(data.get("response", "{}"))
            return AIEvaluation(
                fundamental_score=int(parsed.get("fundamental_score", 6)),
                moat_score=int(parsed.get("moat_score", 6)),
                moat_text=str(parsed.get("moat_text", "")),
                fair_value_dcf=float(parsed.get("fair_value_dcf") or 0),
                fair_value_nav=float(parsed.get("fair_value_nav") or 0),
                recommendation=str(parsed.get("recommendation", "none")),
                recommendation_reason=str(parsed.get("recommendation_reason", "")),
                risk_notes=str(parsed.get("risk_notes", "")),
                estimated_cost=0.0,
                is_fallback=False,
            )
        except Exception:
            return self._fallback(payload)
