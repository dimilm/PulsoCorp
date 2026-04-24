import json

import httpx

from app.providers.ai.base import AIEvaluation, AIProvider


class OpenAIProvider(AIProvider):
    def __init__(self, endpoint: str, model: str, api_key: str | None = None) -> None:
        self.endpoint = endpoint
        self.model = model
        self.api_key = api_key

    def _fallback(self, payload: dict) -> AIEvaluation:
        score = 7 if payload.get("burggraben") else 5
        discount = payload.get("dcf_discount_pct") or 0
        recommendation = "buy" if discount < 0 else "risk_buy"
        price = payload.get("current_price") or 0
        return AIEvaluation(
            fundamental_score=score,
            moat_score=score,
            moat_text="Heuristischer Score (kein LLM-Aufruf).",
            fair_value_dcf=price * 1.12,
            fair_value_nav=price * 1.06,
            recommendation=recommendation,
            recommendation_reason="Heuristische Empfehlung basierend auf Bewertungsabschlag.",
            risk_notes="Fallback aktiv, da Providerantwort nicht genutzt werden konnte.",
            estimated_cost=0.0,
            is_fallback=True,
        )

    async def evaluate(self, payload: dict) -> AIEvaluation:
        if not self.api_key:
            return self._fallback(payload)
        prompt = (
            "Du bist ein Aktienanalyse-Assistent. Erstelle nur JSON mit den Feldern: "
            "fundamental_score (0-10 int), moat_score (0-10 int), moat_text (string), "
            "fair_value_dcf (number), fair_value_nav (number), recommendation ('buy'|'risk_buy'|'none'), "
            "recommendation_reason (string), risk_notes (string). "
            f"Eingabedaten: {json.dumps(payload, ensure_ascii=True)}"
        )
        body = {
            "model": self.model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": "Antworte strikt als valides JSON-Objekt."},
                {"role": "user", "content": prompt},
            ],
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            async with httpx.AsyncClient(timeout=45) as client:
                response = await client.post(self.endpoint, headers=headers, json=body)
                response.raise_for_status()
                raw = response.json()["choices"][0]["message"]["content"]
            parsed = json.loads(raw)
            return AIEvaluation(
                fundamental_score=int(parsed.get("fundamental_score", 5)),
                moat_score=int(parsed.get("moat_score", 5)),
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
