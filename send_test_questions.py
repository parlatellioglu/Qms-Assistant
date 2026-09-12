#!/usr/bin/env python3
"""
send_test_questions.py — Kurumsal Kalite Asistanı için toplu soru/yanıt test aracı.

Bir soru dosyasındaki her satırı sırayla asistanın /chat ucuna gönderir ve
soru + yanıt + meta bilgisini (model, grounded, top_score, kaynak belgeler,
süreler) bir günlük dosyasına yazar. UI'a hiç dokunmaz.

Yalnızca Python standart kütüphanesini kullanır — hiçbir 'pip install' gerekmez,
başka bir bilgisayarda olduğu gibi çalışır (Python 3.8+).

Örnek kullanım:
    python3 send_test_questions.py
    python3 send_test_questions.py --url http://localhost:8013 \
        --questions rag_test_questions.txt --delay 1

Varsayılan olarak her soru BAĞIMSIZ gönderilir (geçmiş taşınmaz), böylece her
test yalıtılmış olur. Soruları tek bir sohbet gibi (önceki sorular hatırlanarak)
zincirlemek için --conversation ekleyin.

Çıktılar rag_test_logs/ klasörüne yazılır (yoksa oluşturulur; adlar zaman damgalı):
    rag_test_logs/rag_test_<zaman>.log    insan-okur transkript
    rag_test_logs/rag_test_<zaman>.jsonl  satır başına bir JSON kaydı (sonradan analiz için)
"""
import argparse
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request

# Tüm test günlükleri bu klasöre yazılır (yoksa oluşturulur).
LOG_DIR = "rag_test_logs"


def load_questions(path):
    """Dosyadan soruları okur. Boş satırlar ve # ile başlayan satırlar atlanır."""
    questions = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            questions.append(s)
    return questions


def get_model(url, timeout):
    """Backend /config ucundan aktif model adını okur; alınamazsa None döner."""
    req = urllib.request.Request(url.rstrip("/") + "/config", method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            cfg = json.loads(resp.read().decode("utf-8"))
        return cfg.get("model")
    except Exception:
        return None


def ask(url, query, history, timeout):
    """Asistanın /chat ucuna tek bir soru gönderir; (yanıt_dict, hata) döner."""
    payload = {"query": query, "history": history, "summary": ""}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url.rstrip("/") + "/chat",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
        return json.loads(body), None
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8")[:500]
        except Exception:
            pass
        return None, f"HTTP {e.code}: {e.reason} {detail}".strip()
    except urllib.error.URLError as e:
        return None, f"Bağlantı hatası: {e.reason} (sunucu {url} adresinde çalışıyor mu?)"
    except Exception as e:  # timeout, JSON hatası vb.
        return None, f"{type(e).__name__}: {e}"


def fmt_meta(meta):
    """Meta sözlüğünü tek satırlık okunur bir özete çevirir."""
    if not meta:
        return "meta yok"
    parts = []
    for key in ("model", "grounded", "top_score", "num_sources", "top_k"):
        if key in meta and meta[key] is not None:
            parts.append(f"{key}={meta[key]}")
    if meta.get("source_ids"):
        parts.append("sources=" + ",".join(str(s) for s in meta["source_ids"]))
    for key in ("retrieval_ms", "generation_ms", "total_ms"):
        if key in meta and meta[key] is not None:
            parts.append(f"{key}={meta[key]}")
    return " | ".join(parts)


def main():
    ap = argparse.ArgumentParser(description="Asistana toplu soru gönderip yanıtları loglar.")
    ap.add_argument("--url", default="http://localhost:8013",
                    help="Backend taban adresi (varsayılan: http://localhost:8013)")
    ap.add_argument("--questions", default="rag_test_questions.txt",
                    help="Soru dosyası; satır başına bir soru (varsayılan: rag_test_questions.txt)")
    ap.add_argument("--out", default=None,
                    help="Günlük dosyası tabanı (uzantısız). Varsayılan: "
                         "rag_test_logs/rag_test_<zaman>")
    ap.add_argument("--delay", type=float, default=0.0,
                    help="Sorular arası bekleme (saniye), sunucuyu yormamak için (varsayılan: 0)")
    ap.add_argument("--timeout", type=float, default=300.0,
                    help="Her istek için zaman aşımı (saniye). CPU üretimi yavaş olabilir (varsayılan: 300)")
    ap.add_argument("--conversation", action="store_true",
                    help="Soruları tek bir sohbet gibi zincirle (geçmişi taşı). "
                         "Varsayılan: her soru bağımsız.")
    args = ap.parse_args()

    try:
        questions = load_questions(args.questions)
    except FileNotFoundError:
        print(f"HATA: soru dosyası bulunamadı: {args.questions}", file=sys.stderr)
        sys.exit(1)

    if not questions:
        print(f"HATA: {args.questions} içinde soru yok.", file=sys.stderr)
        sys.exit(1)

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    # --out verilmezse çıktılar rag_test_logs/ klasörüne yazılır; verilirse
    # (klasör içeren tam bir yol olabilir) olduğu gibi kullanılır.
    if args.out:
        base = args.out
    else:
        os.makedirs(LOG_DIR, exist_ok=True)
        base = os.path.join(LOG_DIR, f"rag_test_{stamp}")
    # --out bir alt klasör içeriyorsa o klasörün de var olduğundan emin ol.
    parent = os.path.dirname(base)
    if parent:
        os.makedirs(parent, exist_ok=True)
    log_path = base + ".log"
    jsonl_path = base + ".jsonl"

    model = get_model(args.url, timeout=min(args.timeout, 30)) or "bilinmiyor"

    print(f"Sunucu     : {args.url}")
    print(f"Model      : {model}")
    print(f"Soru sayısı: {len(questions)}")
    print(f"Mod        : {'zincirli sohbet' if args.conversation else 'bağımsız sorular'}")
    print(f"Günlük     : {log_path}")
    print(f"JSONL      : {jsonl_path}")
    print("-" * 70)

    history = []  # yalnızca --conversation modunda kullanılır
    ok = 0
    fail = 0
    run_start = time.perf_counter()

    with open(log_path, "w", encoding="utf-8") as log, \
         open(jsonl_path, "w", encoding="utf-8") as jl:
        header = (f"Kurumsal Kalite Asistanı — Toplu Test\n"
                  f"Başlangıç: {dt.datetime.now().isoformat(timespec='seconds')}\n"
                  f"Model: {model}\n"
                  f"Sunucu: {args.url}  |  Soru sayısı: {len(questions)}  |  "
                  f"Mod: {'zincirli' if args.conversation else 'bağımsız'}\n")
        log.write(header + "=" * 90 + "\n")
        log.flush()

        for i, q in enumerate(questions, 1):
            print(f"[{i}/{len(questions)}] {q[:70]}{'…' if len(q) > 70 else ''}")
            t0 = time.perf_counter()
            resp, err = ask(args.url, q, history if args.conversation else None, args.timeout)
            elapsed = time.perf_counter() - t0
            ts = dt.datetime.now().isoformat(timespec="seconds")

            if err:
                fail += 1
                print(f"    ✗ HATA: {err}  ({elapsed:.1f}s)")
                log.write(f"\n[{i}] {ts}  ({elapsed:.1f}s)\nSORU: {q}\nHATA: {err}\n"
                          + "-" * 90 + "\n")
                jl.write(json.dumps({"index": i, "timestamp": ts, "question": q,
                                     "error": err, "elapsed_s": round(elapsed, 2)},
                                    ensure_ascii=False) + "\n")
                log.flush(); jl.flush()
                if args.delay:
                    time.sleep(args.delay)
                continue

            ok += 1
            answer = resp.get("answer", "")
            meta = resp.get("meta") or {}
            print(f"    ✓ {fmt_meta(meta)}  ({elapsed:.1f}s)")

            log.write(f"\n[{i}] {ts}  ({elapsed:.1f}s)\n"
                      f"META: {fmt_meta(meta)}\n"
                      f"SORU: {q}\n"
                      f"YANIT:\n{answer}\n" + "-" * 90 + "\n")
            log.flush()

            jl.write(json.dumps({"index": i, "timestamp": ts, "question": q,
                                 "answer": answer, "meta": meta,
                                 "elapsed_s": round(elapsed, 2)},
                                ensure_ascii=False) + "\n")
            jl.flush()

            # Zincirli modda geçmişi büyüt (soru + yanıt).
            if args.conversation:
                history.append({"role": "user", "content": q})
                history.append({"role": "assistant", "content": answer})

            if args.delay:
                time.sleep(args.delay)

        total = time.perf_counter() - run_start
        summary = (f"\nBitti: {ok} başarılı, {fail} hatalı, toplam {len(questions)} soru. "
                   f"Süre: {total:.1f}s.\n")
        log.write("=" * 90 + summary)

    print("-" * 70)
    print(f"Bitti: {ok} başarılı, {fail} hatalı. Toplam süre {total:.1f}s.")
    print(f"Transkript: {log_path}")
    print(f"JSONL     : {jsonl_path}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nKullanıcı tarafından durduruldu. Yazılan kısım günlükte kalır.", file=sys.stderr)
        sys.exit(130)
