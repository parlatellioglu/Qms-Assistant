# RAG evaluation — answer key · Cevap Anahtarı

`TEST-QUESTIONS.md` içindeki 20 sorunun, **data klasöründeki CMMI belgelerine
göre** asistanın üretmesi beklenen doğru cevapları. Her madde: beklenen cevabın özü
ve dayandığı kaynak (belge + bölüm). Kaynaklar: `CMMI_completed` + `CMMI_xlsx_pptx`
(taslaklar hariç).

> Not: Örnek proje "Mobil Self-Servis Uygulaması (MSS)" üzerinedir; aşağıdaki somut
> değerler (roller, isimler, sayılar) belgelerin gerçek içeriğinden alınmıştır.

---

## Nokta Atışı — Spesifik Bilgi · Pinpoint Retrieval

**1. Bir SRS'te güvenlik gereksinimleri en az hangi başlıkları kapsamalıdır?**
Beklenen: Kimlik doğrulama ve yetkilendirme (**OAuth2/JWT + rol tabanlı yetkilendirme**),
şifreleme (**beklemede AES-256, iletimde TLS 1.2+**), ödeme verisinde **tokenizasyon ve
PCI-DSS uyumu**, ve tüm finansal işlemlerde **denetim kaydı (audit log)**.
Kaynak: SRS (CMMI-IT-005), §3 "Security Requirements".

**2. What exit criteria must be met before the SAT acceptance certificate is issued?**
Expected: **All critical/high-severity defects closed and ≥95% of test cases passed**
(with performance expectations met: ≤2 s response, 500 TPS, ≥99.5% success).
Source: SAT Plan (CMMI-IT-007), §10 "Acceptance Criteria" (Exit Criteria) & §12 Sign-off.

**3. TRF hangi iki rol tarafından imzalanır ve hangi aşamada temellenir (baseline)?**
Beklenen: TRF üç aşamalı imza bloğuyla onaylanır — **Hazırlayan: Proje Yöneticisi**
(Kişi 1), **Öneren: Yazılım Mimarı** (Kişi 2), **Onaylayan: Genel Müdür
Yardımcısı** (Kişi 4). Belge **v1.0'da, onaylanıp yayımlandığında temellenir
(baseline)**.
Kaynak: TRF (CMMI-IT-001) imza bloğu + Revizyon Geçmişi ("Onaylandı ve yayımlandı (baseline)").
_(Soru "iki rol" varsayıyor; belgede sign-off üç rollüdür — asistanın gerçek rolleri vermesi beklenir.)_

**4. Which record demonstrates bi-directional traceability between requirements and test cases?**
Expected: The **Traceability Matrix** — the SRS references it as
**"İzlenebilirlik Matrisi: MSS-Traceability-Matrix v1.0"**, linking requirements to
their test cases.
Source: SRS (CMMI-IT-005), traceability reference.

---

## Genel & Kavramsal · Broad & Conceptual

**5. CMMI tabanlı kalite süreci projelerde neyi amaçlar ve hangi ana aşamalardan oluşur?**
Beklenen: Amaç, teslimatın CMMI/SDLC prosedürüne göre tutarlı, izlenebilir ve
denetlenebilir biçimde yürütülmesi. Ana yaşam döngüsü aşamaları: **Ideation → Scoping
→ Build Case → Project Planning → Requirements Development (SRS) → Design (DSAD) →
Development → Testing & Validation → Launch → Post Launch**.
Kaynak: SDLC Process (pptx), "High Level / Overview of Solution Delivery Cycle".

**6. Give an overview of the full set of documents produced across a project's life cycle.**
Expected: A synthesis naming the document set and its purpose, e.g. **BUR** (business
unit requirements), **TRF** (technical requirements form), **Tech Reco**, **SRS**
(software requirements), **PMP** (project management plan), **DSAD** (detailed system &
architecture design), **SAT/UAT Plans**, **SAT/UAT Cases**, **SAT/UAT Certificates**,
and the **Close-out Report** — each tied to a lifecycle phase.
Source: whole CMMI_completed set + SDLC deck.

**7. Which quality-assurance (SQA) checkpoints occur throughout the process?**
Expected: **Reviews** (peer reviews and MPR gate reviews G1–G6), **sign-off/approval**
on each deliverable, **baselining** of signed deliverables, **milestone / phase-gate
reviews**, **defect logging with severity**, and **traceability checks**.
Source: SDLC review process + the sign-off/revision blocks across documents.

---

## Karşılaştırma & Çapraz Doküman · Comparison & Cross-Document

**8. SAT ile UAT arasındaki fark nedir; her biri neyi doğrular?**
Beklenen: **SAT**, uygulamayı **sistem ve entegrasyon açısından teknik gereksinimlere**
göre doğrular; **UAT**, **iş birimi ve son kullanıcı açısından işlevsel gereksinimlere**
göre doğrular. İkisi de aynı plan yapısını (Objectives, Test Cases, Acceptance Criteria,
Sign-off …) izler.
Kaynak: SAT Plan (CMMI-IT-007) §1 ve UAT Plan (CMMI-IT-008) §1 "Objectives".

**9. How do the BUR, TRF, SRS and DSAD documents feed into one another?**
Expected: **BUR** captures business-unit requirements → **TRF** turns them into a
technical requirements form → **SRS** specifies the software requirements → **DSAD**
details the system & architecture design. Each is an input to the next, with
requirements traced through the chain.
Source: BUR/TRF/SRS/DSAD purpose sections + lifecycle order in the SDLC deck.

**10. Compare the Prepared / Recommended / Approved sign-off roles across the PMP and the SRS.**
Expected: Both use the same three-tier block, but the roles differ.
- **PMP**: Prepared — **Proje Yöneticisi** (Kişi 1); Recommended — **Yazılım Mimarı**
  (Kişi 2); Approved — **Genel Müdür Yardımcısı** (Kişi 4).
- **SRS**: Prepared — **İş Analisti** (Kişi 6); Recommended — **Yazılım Mimarı**
  (Kişi 2); Approved — **Proje Yöneticisi** (Kişi 1).
Common: identical Prepared/Recommended/Approved structure; the architect recommends both.
Source: PMP (CMMI-IT-003) & SRS (CMMI-IT-005) sign-off blocks.

---

## Süreç & Sıradaki Adım · Procedural & Next-Step

**11. SRS'i yazıp onaylattım; süreçte sıradaki adım ve hangi doküman nedir?**
Beklenen: Requirements Development'tan sonra **Design (Tasarım)** aşamasına geçilir;
üretilecek belge **DSAD (Detaylı Sistem ve Mimari Tasarım)**'dır.
Kaynak: SDLC Process (pptx) yaşam döngüsü sırası.

**12. I've completed the detailed design (DSAD) — what must happen before development begins?**
Expected: The **DSAD must be reviewed, signed off and baselined** (design-phase exit /
development entry criteria met); only then does **Development** begin (with supplier
monitoring).
Source: SDLC lifecycle (Design → Development) + deliverable sign-off/baseline practice.

**13. Sistem kabul testi (SAT) başarıyla geçti; UAT'ye geçmek için ne yapmalıyım?**
Beklenen: SAT çıkış kriterleri sağlanıp **SAT sertifikası** düzenlendikten sonra
**UAT**'ye geçilir: UAT planı/senaryoları iş birimi ve son kullanıcılarla yürütülür,
ardından **UAT sertifikası** alınır.
Kaynak: SAT Plan / UAT Plan + SDLC Testing & Validation → Launch akışı.

---

## Tablo & Sunum Verisi · Structured Data (xlsx · pptx)

**14. SAT test senaryolarına göre, bir hesabın kilitlenmesi için kaç ardışık hatalı OTP denemesi gerekir?**
Beklenen: **3** (üç ardışık hatalı OTP denemesinden sonra hesap geçici olarak kilitlenir).
Kaynak: SAT Cases (CMMI-IT-009, xlsx), **SAT-TC03**.

**15. According to the SAT test cases, what response-time target and sustained TPS capacity do the performance/load tests verify?**
Expected: Response time **≤ 2 s** (SAT-TC12, measured ~1.4 s) and **500 TPS** sustained
capacity with **≥99.5% success** (SAT-TC13, measured 99.7%).
Source: SAT Cases (CMMI-IT-009, xlsx), SAT-TC12 & SAT-TC13.

**16. SAT senaryolarında KVKK açısından test ortamında üretim verisi nasıl kullanılmalıdır?**
Beklenen: Üretim verisi **maskelenmeden kullanılamaz**; test ortamında tüm kişisel
veriler **maskelenmiş** görünür (maskelenmiş üretim verisi + sentetik test aboneleri).
Kaynak: SAT Cases (CMMI-IT-009, xlsx), **SAT-TC14**; SAT Plan §9 Test Data.

**17. In the SDLC process slides, what are the high-level life-cycle phases from ideation to launch?**
Expected: **IDEATION, SCOPING, BUILD CASE, DEVELOPMENT, TESTING & VALIDATION, LAUNCH**
(the detailed cycle also inserts Project Planning, Requirements Development, Design, and
Post Launch).
Source: SDLC Process (pptx), "High Level Solutions Delivery Life Cycle" slide.

---

## Kapsam Dışı & Fallback · Out-of-Scope & Negative

> Bu üç sorunun cevabı belgelerde **yoktur**. Doğru davranış: uydurmadan, dürüst
> "bulamadım / belgelerde bu bilgi yok" dönüşünü vermek.

**18. Bu projedeki mobil uygulamanın kod deposunun (repository) Git adresi nedir?**
Beklenen: **Fallback.** Belgelerde depo/Git adresi geçmez; asistan bilgiyi bulamadığını
belirtmeli, adres uydurmamalı.

**19. What is the production server IP address and database password for the deployment?**
Expected: **Fallback / refusal.** No such secret exists in the corpus; the assistant must
say it cannot find it and must not fabricate an IP or password.

**20. Ekip üyelerinin maaş bilgileri hangi belgede yer alıyor?**
Beklenen: **Fallback.** Maaş bilgisi hiçbir belgede yer almaz; asistan bunu belirtmeli,
alakasız bir belgeye yönlendirme yapmamalı.
