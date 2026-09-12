import json
import os
import re
import urllib.request
from datetime import datetime
from typing import List, Dict

# RRF fusion scores are rank-based (best hit ~1.0 when a doc tops both the dense
# and sparse lists, ~0.5 when it tops only one, lower further down), not a
# normalized cosine similarity. So this is a heuristic gate: if the best retrieved
# document scores below the threshold (or nothing was retrieved), we treat the
# context as too weak and fall back to a general answer. Tune via env.
RELEVANCE_THRESHOLD = float(os.getenv("RAG_RELEVANCE_THRESHOLD", "0.5"))

# Shown to the user when the answer is not grounded in the company documents.
# One per supported answer language: the notice has to read in the same language as
# the answer it introduces, or a user asking in English gets a Turkish preamble on
# an English answer. Keyed by the codes detect_language() returns.
FALLBACK_NOTICES = {
    "tr": ("Yeterince ilgili bilgi bulamadığım için genel bir yanıt veriyorum "
           "(bu yanıt şirket dokümanlarına dayanmıyor olabilir):"),
    "en": ("I could not find enough relevant information in the documents, so this "
           "is a general answer (it may not be based on the company's documents):"),
}
DEFAULT_LANGUAGE = "tr"          # the corpus and most users are Turkish
# Kept as the Turkish notice for callers that reference a single string.
FALLBACK_NOTICE = FALLBACK_NOTICES[DEFAULT_LANGUAGE]


def fallback_notice(lang: str = DEFAULT_LANGUAGE) -> str:
    """The 'this answer isn't grounded' notice, in ``lang``."""
    return FALLBACK_NOTICES.get(lang, FALLBACK_NOTICES[DEFAULT_LANGUAGE])


def has_fallback_notice(answer: str) -> bool:
    """True if the answer already opens with any language's fallback notice."""
    return any(notice in answer for notice in FALLBACK_NOTICES.values())


# Characters unique to the Turkish alphabet, and short function words that are
# common in questions. Together these separate the two languages reliably on the
# one-sentence inputs we actually get, without pulling in a detection dependency.
_TR_CHARS = set("çğıöşüÇĞİÖŞÜ")
_TR_WORDS = {"ne", "nedir", "nasıl", "hangi", "kim", "kaç", "niçin", "neden", "mi",
             "mı", "mu", "mü", "ve", "ile", "için", "bir", "bu", "şu", "olan",
             "nelerdir", "yapmalıyım", "gerekir", "midir", "arasındaki", "hakkında"}
_EN_WORDS = {"what", "which", "how", "who", "when", "where", "why", "is", "are",
             "the", "of", "and", "to", "in", "for", "do", "does", "did", "can",
             "must", "should", "give", "compare", "list", "explain", "between"}


def detect_language(text: str) -> str:
    """Guess the language of a user question: ``"tr"`` or ``"en"``.

    Turkish-specific letters are near-decisive when present, so they are weighted
    heavily; otherwise the decision falls to function-word overlap, which handles
    Turkish written without diacritics ("kabul kriterleri nelerdir"). Ties and
    empty input resolve to Turkish — the corpus and the product's default audience.
    """
    if not text or not text.strip():
        return DEFAULT_LANGUAGE
    words = re.findall(r"[^\W\d_]+", text.lower(), flags=re.UNICODE)
    if not words:
        return DEFAULT_LANGUAGE
    tr = 2 * sum(1 for ch in text if ch in _TR_CHARS) + sum(1 for w in words if w in _TR_WORDS)
    en = sum(1 for w in words if w in _EN_WORDS)
    if tr == en == 0:
        return DEFAULT_LANGUAGE
    return "en" if en > tr else "tr"


# LLM model + context window, env-overridable so you can swap models without code
# changes (smaller model / context = faster on CPU, at some quality cost).
DEFAULT_MODEL = os.getenv("LLM_MODEL", "gemma4:e4b")  # default for general Q&A
NUM_CTX = int(os.getenv("LLM_NUM_CTX", "8192"))
# Keep the model resident between queries so each request doesn't reload several
# GB from cold (-1 = never unload; "30m" = keep 30 min). Big win for large models.
KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "30m")
# "Thinking" models (e.g. gemma4) emit a long hidden reasoning pass before the
# answer — slow and unnecessary for grounded RAG summarisation. Off by default.
THINK = os.getenv("LLM_THINK", "0").lower() in ("1", "true", "yes")
# Cap answer length (output tokens) to bound generation time; 0 = no cap.
NUM_PREDICT = int(os.getenv("LLM_NUM_PREDICT", "0"))

# Full-prompt debug log: every prompt sent to the LLM is appended to a local file
# (never shown in the UI) so you can inspect exactly what the model received for
# each question. On by default; disable with LOG_PROMPTS=0, relocate with
# PROMPT_LOG_PATH. Lives next to the other local data (gitignored).
_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
PROMPT_LOG_ENABLED = os.getenv("LOG_PROMPTS", "1").lower() in ("1", "true", "yes")
PROMPT_LOG_PATH = os.getenv("PROMPT_LOG_PATH", os.path.join(_DATA_DIR, "prompt_log.txt"))


def _log(message: str) -> None:
    """Lightweight stage log so you can follow what the LLM step is doing."""
    print(f"[llm] {message}", flush=True)


def _log_prompt(query: str, prompt: str, meta: dict) -> None:
    """Append the full prompt sent to the LLM to a local log file (not the UI).

    Lets you inspect exactly what the model received for each question. Appends a
    timestamped, delimited entry; fails silently so logging never breaks answering.
    Disable with LOG_PROMPTS=0.
    """
    if not PROMPT_LOG_ENABLED:
        return
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        head = (f"model={meta.get('model')} | grounded={meta.get('grounded')} | "
                f"top_score={meta.get('top_score')} | sources={meta.get('num_sources')}")
        entry = (f"\n{'=' * 100}\n{ts} | {head}\nSORU: {query}\n"
                 f"{'-' * 100}\n{prompt}\n{'=' * 100}\n")
        os.makedirs(os.path.dirname(PROMPT_LOG_PATH), exist_ok=True)
        with open(PROMPT_LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(entry)
    except Exception as exc:  # logging must never break the answer path
        _log(f"prompt log yazılamadı: {exc}")


def build_context(retrieved_docs: List[Dict]) -> str:
    context_parts = []
    for index, item in enumerate(retrieved_docs, start=1):
        doc = item.get("document", {})
        title = doc.get("title", "No Title")
        content = doc.get("content", "No Content")
        score = item.get("score")

        context_parts.append(
            f"SOURCE {index}\n"
            f"Title: {title}\n"
            f"Score: {score if score is not None else 'N/A'}\n"
            f"Content: {content}"
        )

    if not context_parts:
        return "No context available."

    return "\n\n---\n\n".join(context_parts)


def _top_score(retrieved_docs: List[Dict]) -> float:
    if not retrieved_docs:
        return 0.0
    return retrieved_docs[0].get("score") or 0.0


# Asymmetric conversation memory. User questions are short and carry the thread's
# intent (a date, a doc name, a constraint), so we keep many; assistant answers are
# long and re-derivable from retrieval, so we keep only the last few. The kept turns
# are then trimmed to a total character budget, so a long chat can't crowd out the
# retrieved documents in the context window.
HISTORY_USER_TURNS = int(os.getenv("CHAT_HISTORY_USER_TURNS", "10"))
HISTORY_ASSISTANT_TURNS = int(os.getenv("CHAT_HISTORY_ASSISTANT_TURNS", "2"))
HISTORY_CHAR_BUDGET = int(os.getenv("CHAT_HISTORY_CHAR_BUDGET", "2400"))
HISTORY_MAX_CHARS = int(os.getenv("CHAT_HISTORY_MSG_CHARS", "600"))
# How many raw messages the frontend should send for the backend to select from —
# enough that the last HISTORY_USER_TURNS user turns are reachable even interleaved.
HISTORY_RAW_CAP = int(os.getenv("CHAT_HISTORY_RAW_CAP", "40"))

# Rolling conversation summary. For long chats, turns that fall out of the recent
# window are compressed into a short "what this chat is about" block, regenerated
# every few turns and round-tripped through the frontend (the backend keeps no
# session). The recent window handles near context; the summary handles far context.
SUMMARY_EVERY_TURNS = int(os.getenv("CHAT_SUMMARY_EVERY_TURNS", "4"))
SUMMARY_MIN_TURNS = int(os.getenv("CHAT_SUMMARY_MIN_TURNS", "12"))
SUMMARY_MAX_CHARS = int(os.getenv("CHAT_SUMMARY_MAX_CHARS", "500"))


def _clip(text: str) -> str:
    """Whitespace-collapse a message and truncate it to the per-message cap."""
    text = " ".join((text or "").split())
    return text[:HISTORY_MAX_CHARS] + "…" if len(text) > HISTORY_MAX_CHARS else text


def format_history(history: List[Dict]) -> str:
    """Render recent chat turns as 'Kullanıcı:/Asistan:' lines for the prompt.

    ``history`` is a list of {"role": "user"|"assistant", "content": str}, oldest
    first. We keep the last HISTORY_USER_TURNS user questions and the last
    HISTORY_ASSISTANT_TURNS assistant answers, restore chronological order, then
    drop oldest-first until the block fits HISTORY_CHAR_BUDGET — never dropping the
    newest user turn (the current question's immediate context). Because user turns
    are short, the same budget reaches many more questions back than a symmetric
    turn window would.
    """
    if not history:
        return ""

    # (original index, role, clipped content) — index lets us restore order later.
    indexed = [(i, t.get("role"), _clip(t.get("content")))
               for i, t in enumerate(history)]
    indexed = [m for m in indexed if m[2]]

    users = [m for m in indexed if m[1] == "user"][-HISTORY_USER_TURNS:]
    assistants = [m for m in indexed if m[1] != "user"][-HISTORY_ASSISTANT_TURNS:]
    kept = sorted(users + assistants, key=lambda m: m[0])

    newest_user = users[-1][0] if users else None
    while kept and sum(len(c) for _, _, c in kept) > HISTORY_CHAR_BUDGET:
        victim = next((m for m in kept if m[0] != newest_user), None)
        if victim is None:  # only the newest user turn is left — keep it
            break
        kept.remove(victim)

    lines = []
    for _, role, content in kept:
        who = "Kullanıcı" if role == "user" else "Asistan"
        lines.append(f"{who}: {content}")
    return "\n".join(lines)


def _history_block(history_str: str) -> str:
    """Prompt fragment injecting prior turns; empty when there is no history."""
    if not history_str:
        return ""
    return (
        "Önceki konuşma (yalnızca bağlam için — kullanıcının yeni sorusu bu "
        "mesajlara atıfta bulunabilir):\n"
        f"{history_str}\n\n"
    )


def _summary_block(summary_str: str) -> str:
    """Prompt fragment injecting the rolling summary; empty when there is none.

    Placed before the recent-turns block so the model reads far context (the gist
    of older turns) first, then the near context (recent turns verbatim).
    """
    if not summary_str:
        return ""
    return (
        "Konuşmanın şimdiye kadarki özeti (daha eski turlardan — yalnızca bağlam "
        "için):\n"
        f"{summary_str.strip()}\n\n"
    )


_SUMMARY_PROMPT = """Talimat:
Bir kurumsal kalite asistanı ile kullanıcı arasındaki konuşmanın kısa bir
"özet notu" tutuyorsun. Amaç, eski turlar bağlamdan düştüğünde konuşmanın neyle
ilgili olduğunu birkaç cümlede hatırlamak.

Kurallar:
- Aşağıdaki mevcut özeti, yeni turlardaki bilgilerle güncelle.
- Konuşulan konuları, kullanıcının sorduğu belirli şeyleri ve varsa önemli
  kısıtları (tarih, doküman adı, proje, karar) koru.
- Cevapların içeriğini tekrar yazma; sadece konunun ne olduğunu özetle.
- En fazla {max_chars} karakter. Tek bir kısa paragraf.
- Özeti konuşmanın dilinde yaz ({lang_name}). Özet modele bağlam olarak
  verilir; kullanıcıya gösterilmez.
- Yalnızca özeti yaz, başka hiçbir şey ekleme.

Mevcut özet:
{previous}

Yeni turlar:
{turns}

Güncellenmiş özet:"""


def summarize_conversation(history: List[Dict], previous_summary: str = "",
                           model_name: str = None) -> str:
    """Fold recent turns into a rolling one-paragraph summary of the conversation.

    ``history`` is the usual [{role, content}] list, oldest first. This is an
    incremental update: the model receives the existing summary plus the newer
    turns and rewrites the summary, so cost stays flat as the chat grows. Returns
    the previous summary unchanged if the LLM is unreachable (never blocks a chat).
    """
    if not history:
        return previous_summary or ""

    turns = "\n".join(
        f"{'Kullanıcı' if t.get('role') == 'user' else 'Asistan'}: {_clip(t.get('content'))}"
        for t in history if _clip(t.get("content"))
    )
    if not turns:
        return previous_summary or ""

    # Summarise in the language the conversation is actually being held in — a
    # Turkish summary riding along an English thread reads as noise to the model.
    user_text = " ".join(t.get("content") or "" for t in history if t.get("role") == "user")
    lang = detect_language(user_text or turns)
    prompt = _SUMMARY_PROMPT.format(
        max_chars=SUMMARY_MAX_CHARS,
        lang_name="Türkçe" if lang == "tr" else "İngilizce",
        previous=(previous_summary.strip() or "(henüz özet yok)"),
        turns=turns,
    )
    try:
        summary = _ollama_generate(prompt, model_name)
    except Exception as e:  # summary is best-effort — keep the old one on failure
        _log(f"Özet oluşturulamadı: {e}")
        return previous_summary or ""

    summary = " ".join(summary.split())
    if len(summary) > SUMMARY_MAX_CHARS:
        summary = summary[:SUMMARY_MAX_CHARS].rstrip() + "…"
    return summary or (previous_summary or "")


def _build_grounded_prompt(context_str: str, query: str, history_str: str = "",
                           summary_str: str = "", lang: str = DEFAULT_LANGUAGE) -> str:
    notice = fallback_notice(lang)
    return f"""Talimat:
Sen bir kurumsal kalite yönetim sistemi danışmanısın. Şirketin kalite
prosedürleri, politikaları ve süreç dokümanlarına dayanarak soruları
yanıtlıyorsun.

Sana soruyla ilgili BİRDEN FAZLA doküman veriliyor. Her dokümanın
başlığı (Title) ve güven skoru (Score) belirtilmiştir.

Kurallar:
- Yanıtını yalnızca verilen dokümanlara dayandır. Kesinlikle hayali
  prosedür, politika veya süreç uydurma.
- Görüş veya tahmin belirtme; yalnızca dokümanda yazılı olanı aktar.
- Kullanıcının sorusu önceki konuşmaya atıfta bulunabilir ("o testler",
  "aynı proje", "bunlar" gibi). Bu ifadeleri önceki konuşmaya göre yorumla;
  ancak yanıtı yine yalnızca dokümanlara dayandır.
- Mümkün olan her yerde yanıtının hangi dokümana (başlık) dayandığını
  belirt. Örn: "Proje Yönetim Planı'na göre..."
- Tüm ilgili dokümanları kullan ve bilgileri birleştir. Hiçbir dokümanı
  görmezden gelme.
- Yanıtın özgüllüğünü sorunun özgüllüğüyle eşleştir: kullanıcı belirli bir
  projeden veya dokümandan söz ediyorsa (ör. bir proje adı vererek), o
  dokümandaki özel ayrıntıları — kişi adları, tarihler, sayısal hedefler —
  aynen aktar. Ancak soru genel bir süreç sorusuysa ve belirli bir proje adı
  GEÇMİYORSA, adımı genel biçimde anlat: görevleri kişi adlarına bağlama ve
  tek bir projeye özgü sayıları/tarihleri (ör. "%70", belirli bir tarih)
  verme; bunun yerine yalnızca genel süreç adımını söyle.
- Prosedür/madde içeren yanıtlarda, mümkünse adım numarası veya pozisyon
  bilgisi de ekle.
- Yanıtı net, profesyonel ve maddeler halinde yapılandır (gerektiğinde
  numaralandırılmış liste veya madde işaretleri kullan).
- KISA VE ÖZ ol. Soruyu doğrudan yanıtla; gereksiz giriş, açıklama veya
  bağlam cümlesi ekleme.
- Kullanıcı açıkça özet/özetleme istemediyse, yanıtın sonuna özet, sonuç veya
  tekrar paragrafı ("Özetle...", "Sonuç olarak...") EKLEME. (Kullanıcı özet
  istediyse, o zaman özet ver.)
- Aynı bilgiyi birden fazla kez verme. Her maddeyi tek satırda, dolgu cümle
  kurmadan yaz (örn. "SAT-TC01 — OTP ile giriş: Pass"; "Bu senaryo için
  yapılan test sonucunda ... olarak belirtilmiştir" gibi kalıplar kullanma).
- YANITIN DİLİ: kullanıcının sorusu hangi dildeyse o dilde yanıt ver — soru
  Türkçe ise Türkçe, İngilizce ise İngilizce. Dokümanlar başka bir dilde
  olabilir; bu yanıtın dilini değiştirmez, alıntıladığın terimleri özgün
  biçimiyle verebilirsin. Her durumda resmî ve kurumsal bir dil kullan.
- Dokümanda sorunun yanıtı bulunamıyorsa, yanıtına aynen şu cümleyle
  başla: "{notice}" ve ardından dokümanlarda bulamadığını
  belirtip genel bilgine dayanarak yardımcı ol.
- Kaynaklar arasında çelişki varsa, çelişkiyi belirt ve en güncel/
  yetkili dokümanı referans göster.

{_summary_block(summary_str)}{_history_block(history_str)}Bağlam:
{context_str}

Soru:
{query}

Cevap:"""


def _build_general_prompt(query: str, history_str: str = "", summary_str: str = "",
                          lang: str = DEFAULT_LANGUAGE) -> str:
    notice = fallback_notice(lang)
    return f"""Talimat:
Sen bir kurumsal kalite yönetim sistemi danışmanısın. Şirket
dokümanlarında bu soruyla ilgili yeterli bilgi bulunamadı.
Aşağıdaki kurallara uyarak genel bilgine dayanarak yanıt ver:
- Yanıtına aynen şu cümleyle başla: "{notice}"
- Kullanıcının sorusu önceki konuşmaya atıfta bulunabilir; bu ifadeleri
  önceki konuşmaya göre yorumla.
- Görüş veya tahmin belirtme, yalnızca genel kabul görmüş kalite
  yönetimi prensiplerini aktar.
- Kısa, öz ve yardımcı ol.
- YANITIN DİLİ: kullanıcının sorusu hangi dildeyse o dilde yanıt ver — soru
  Türkçe ise Türkçe, İngilizce ise İngilizce. Resmî ve kurumsal bir dil kullan.

{_summary_block(summary_str)}{_history_block(history_str)}Soru:
{query}

Cevap:"""


def generate_answer_with_meta(query: str, retrieved_docs: List[Dict], model_name: str = None,
                              history: List[Dict] = None, summary: str = ""):
    """Generate the answer and a process-trace dict (model, mode, scores).

    Returns (answer, meta). meta is safe to surface in the UI so users can see
    which model ran, whether the answer was grounded, and the gating score.
    ``history`` (recent chat turns) lets the model resolve references like
    "those tests" in a follow-up question.
    """
    model_name = model_name or DEFAULT_MODEL
    _log(f"Soru alındı: {query!r}")
    _log(f"Dokümanlar kontrol ediliyor ({len(retrieved_docs)} aday bulundu)...")

    top_score = _top_score(retrieved_docs)
    sufficient = bool(retrieved_docs) and top_score >= RELEVANCE_THRESHOLD
    _log(f"En yüksek ilgi skoru: {top_score:.3f} (eşik: {RELEVANCE_THRESHOLD})")

    history_str = format_history(history)
    # The answer follows the QUESTION's language, not the corpus's — the documents
    # may be Turkish while the user asks in English.
    lang = detect_language(query)
    meta = {
        "model": model_name,
        "num_ctx": NUM_CTX,
        "num_sources": len(retrieved_docs),
        "top_score": round(float(top_score), 3),
        "threshold": RELEVANCE_THRESHOLD,
        "grounded": bool(sufficient),
        "history_turns": len(history or []),
        "has_summary": bool(summary),
        "language": lang,
    }

    if sufficient:
        _log("Yeterli bağlam bulundu — dokümanlara dayalı yanıt üretiliyor.")
        prompt = _build_grounded_prompt(build_context(retrieved_docs), query, history_str, summary, lang)
    else:
        _log("Yeterli/ilgili doküman yok — genel yanıt moduna geçiliyor.")
        prompt = _build_general_prompt(query, history_str, summary, lang)

    _log_prompt(query, prompt, meta)

    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    url = f"{ollama_url}/api/generate"
    options = {
        "num_ctx": NUM_CTX,
        # Deterministic, faithful decoding: greedy (temperature 0) with a fixed
        # seed so the same query + retrieved context always yields the same
        # answer. Avoids run-to-run variance and reduces cross-source conflation
        # (e.g. mixing the SAT Plan's and SAT Cases' differing TC descriptions).
        "temperature": 0,
        "seed": 42,
    }
    if NUM_PREDICT > 0:
        options["num_predict"] = NUM_PREDICT
    data = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "keep_alive": KEEP_ALIVE,  # keep model resident → no per-query reload
        "think": THINK,            # skip the slow hidden reasoning pass by default
        "options": options,
    }

    _log(f"LLM'e istek gönderiliyor (model={model_name})...")
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )

        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            answer = result.get('response', '').strip()
    except Exception as e:
        _log(f"LLM çağrısı başarısız: {e}")
        meta["error"] = str(e)
        return "Could not generate an answer (the LLM service is unreachable).", meta

    _log(f"LLM yanıtı alındı ({len(answer)} karakter).")

    # When we fell back to general mode, guarantee the notice is present even if
    # the model didn't include it (the grounded prompt asks the model to add it
    # itself when the documents don't actually answer the question).
    if not sufficient and answer and not has_fallback_notice(answer):
        answer = f"{fallback_notice(lang)}\n\n{answer}"

    return answer, meta


def generate_answer(query: str, retrieved_docs: List[Dict], model_name: str = None) -> str:
    """Answer-only wrapper (used by scripts/query/ask_cmmi.py)."""
    answer, _meta = generate_answer_with_meta(query, retrieved_docs, model_name)
    return answer


def _ollama_options() -> dict:
    options = {"num_ctx": NUM_CTX, "temperature": 0, "seed": 42}
    if NUM_PREDICT > 0:
        options["num_predict"] = NUM_PREDICT
    return options


def _ollama_generate(prompt: str, model_name: str = None) -> str:
    """Blocking, non-streaming generate — returns the full response text.

    Used for short auxiliary generations (e.g. the rolling summary) that don't
    need token streaming. Deterministic decoding, same as the answer path.
    """
    model_name = model_name or DEFAULT_MODEL
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    data = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "keep_alive": KEEP_ALIVE,
        "think": THINK,
        "options": _ollama_options(),
    }
    req = urllib.request.Request(
        f"{ollama_url}/api/generate",
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode("utf-8"))
    return (result.get("response") or "").strip()


def prepare_answer(query: str, retrieved_docs: List[Dict], model_name: str = None,
                   history: List[Dict] = None, summary: str = ""):
    """Compute (model, meta, prompt) WITHOUT calling the LLM.

    Lets the streaming endpoint emit retrieval metadata + sources immediately,
    then stream the answer tokens that follow. ``history`` (recent chat turns)
    is folded into the prompt so follow-up questions resolve their references;
    ``summary`` (the rolling summary of older turns) carries far context.
    """
    model_name = model_name or DEFAULT_MODEL
    top_score = _top_score(retrieved_docs)
    sufficient = bool(retrieved_docs) and top_score >= RELEVANCE_THRESHOLD
    history_str = format_history(history)
    lang = detect_language(query)
    meta = {
        "model": model_name,
        "num_ctx": NUM_CTX,
        "num_sources": len(retrieved_docs),
        "top_score": round(float(top_score), 3),
        "threshold": RELEVANCE_THRESHOLD,
        "grounded": bool(sufficient),
        "history_turns": len(history or []),
        "has_summary": bool(summary),
        "language": lang,
    }
    prompt = (_build_grounded_prompt(build_context(retrieved_docs), query, history_str, summary, lang)
              if sufficient else _build_general_prompt(query, history_str, summary, lang))
    _log_prompt(query, prompt, meta)
    return model_name, meta, prompt


def stream_answer_tokens(prompt: str, model_name: str = None):
    """Yield answer text pieces as Ollama generates them (stream=True NDJSON)."""
    model_name = model_name or DEFAULT_MODEL
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    url = f"{ollama_url}/api/generate"
    data = {
        "model": model_name,
        "prompt": prompt,
        "stream": True,
        "keep_alive": KEEP_ALIVE,
        "think": THINK,
        "options": _ollama_options(),
    }
    _log(f"LLM'e akışlı istek gönderiliyor (model={model_name})...")
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as response:
        for raw in response:  # Ollama streams newline-delimited JSON objects
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw.decode("utf-8"))
            except Exception:
                continue
            piece = obj.get("response", "")
            if piece:
                yield piece
            if obj.get("done"):
                break
