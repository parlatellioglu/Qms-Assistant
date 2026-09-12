# RAG evaluation question set

Asistanın erişim (retrieval) davranışını farklı yönleriyle sınayan 20 örnek soru — 10 Türkçe, 10 İngilizce. Sorular departmanlara göre değil, RAG'in test edilen yeteneğine göre gruplanmıştır: nokta atışı bilgi, genel/kavramsal sentez, çapraz doküman karşılaştırması, süreç akışı, tablo/sunum (xlsx·pptx) ve kapsam dışı (fallback) soruları.

Kapsam: Sorular data klasöründeki CMMI dokümanlarına dayanır — CMMI_completed ve CMMI_xlsx_pptx dahil, CMMI_drafts hariç. Nokta atışı sorular indekslenmiş belgelerin gerçek içeriğine (ör. SAT/UAT test tabloları, SDLC sunumu) atıf yapar; son bölümdeki sorular ise bilinçli olarak kapsam dışıdır ve asistanın “bulamadım” dönüşünü (fallback) sınar. Her sorunun altındaki italik satır, o sorunun RAG'de neyi test ettiğini açıklar.

## Nokta Atışı — Spesifik Bilgi   ·   Pinpoint Retrieval

*İlgili dokümanlar:  SRS · TRF · SAT/UAT Plan · Traceability*

**1.  Bir SRS'te güvenlik gereksinimleri en az hangi başlıkları (kimlik doğrulama, yetkilendirme, şifreleme, denetim kaydı) kapsamalıdır?**
  
_Tek bir dokümanın (SRS) belirli bir bölümündeki kesin listeyi getirebiliyor mu?_

**2.  What exit criteria must be met before the SAT acceptance certificate is issued?**
  
_Does it pull a precise, section-level rule from one plan (SAT) rather than a general answer?_

**3.  TRF hangi iki rol tarafından imzalanır ve hangi aşamada temellenir (baseline)?**
  
_İki ayrı olguyu (imza rolleri + baseline aşaması) aynı belgeden isabetle çekebiliyor mu?_

**4.  Which record demonstrates bi-directional traceability between requirements and test cases?**
  
_Does it name the exact artifact instead of describing traceability in general?_

## Genel & Kavramsal   ·   Broad & Conceptual Synthesis

*İlgili dokümanlar:  SDLC · tüm doküman türleri*

**5.  CMMI tabanlı kalite süreci projelerde neyi amaçlar ve hangi ana aşamalardan oluşur?**
  
_Geniş, kavramsal bir soruyu birçok kaynaktan derleyip özetleyebiliyor mu?_

**6.  Give an overview of the full set of documents produced across a project's life cycle.**
  
_Can it synthesise a corpus-wide overview without drowning in one document's detail?_

**7.  Which quality-assurance (SQA) checkpoints occur throughout the process?**
  
_Does a broad question get a broad, well-scoped answer (altitude matching)?_

## Karşılaştırma & Çapraz Doküman   ·   Comparison & Cross-Document

*İlgili dokümanlar:  SAT Plan ↔ UAT Plan · BUR · TRF · SRS · DSAD · PMP*

**8.  SAT ile UAT arasındaki fark nedir; her biri neyi doğrular?**
  
_İki ayrı planı (SAT ve UAT) tek yanıtta karşılaştırabiliyor mu?_

**9.  How do the BUR, TRF, SRS and DSAD documents feed into one another?**
  
_Does it link four separate documents into one coherent chain?_

**10.  Compare the Prepared / Recommended / Approved sign-off roles across the PMP and the SRS.**
  
_Can it retrieve the same structure from two documents and contrast them?_

## Süreç & Sıradaki Adım   ·   Procedural & Next-Step

*İlgili dokümanlar:  SDLC · aşama geçişleri*

**11.  SRS'i yazıp onaylattım; süreçte sıradaki adım ve hangi doküman nedir?**
  
_Duruma göre bir sonraki adımı ve doğru çıktıyı önerebiliyor mu (akıl yürütme)?_

**12.  I've completed the detailed design (DSAD) — what must happen before development begins?**
  
_Does it surface phase-gate / entry conditions rather than a static definition?_

**13.  Sistem kabul testi (SAT) başarıyla geçti; UAT'ye geçmek için ne yapmalıyım?**
  
_Akış üzerinde konum bulup ('SAT bitti') doğru sonraki aşamayı gösterebiliyor mu?_

## Tablo & Sunum Verisi   ·   Structured Data (xlsx · pptx)

*İlgili dokümanlar:  SAT Cases (xlsx) · UAT Cases (xlsx) · SDLC Process (pptx)*

**14.  SAT test senaryolarına göre, bir hesabın kilitlenmesi için kaç ardışık hatalı OTP denemesi gerekir?**
  
_Bir xlsx tablosundaki tek bir hücrenin kesin değerini (3) getirebiliyor mu?_

**15.  According to the SAT test cases, what response-time target and sustained TPS capacity do the performance/load tests verify?**
  
_Does it read two numeric NFR values (≤2 s, 500 TPS) out of the spreadsheet rows?_

**16.  SAT senaryolarında KVKK açısından test ortamında üretim verisi nasıl kullanılmalıdır?**
  
_Tablo satırındaki niteliksel bir kuralı (veri maskeleme) doğru getirebiliyor mu?_

**17.  In the SDLC process slides, what are the high-level life-cycle phases from ideation to launch?**
  
_Can it retrieve an ordered list out of a PowerPoint deck (not a Word doc)?_

## Kapsam Dışı & Fallback   ·   Out-of-Scope & Negative

*İlgili dokümanlar:  — (yanıt korpusta yok)*

**18.  Bu projedeki mobil uygulamanın kod deposunun (repository) Git adresi nedir?**
  
_Korpusta olmayan bir bilgi için uydurmadan 'bulamadım' diyebiliyor mu?_

**19.  What is the production server IP address and database password for the deployment?**
  
_Does it refuse to invent sensitive details that appear nowhere in the documents?_

**20.  Ekip üyelerinin maaş bilgileri hangi belgede yer alıyor?**
  
_Alakasız/kapsam dışı soruda hatalı bir belgeye yönlendirmeden fallback veriyor mu?_
