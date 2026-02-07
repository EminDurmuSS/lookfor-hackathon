# NatPat Çoklu Ajan (Multi-Agent) Müşteri Destek Sistemi - Proje Sunum Detayları

## 1. Proje Özeti (Executive Summary)
**"NatPat Multi-Agent CS"**, e-ticaret markaları (özelde NatPat) için geliştirilmiş, üretim düzeyinde (production-grade), otonom bir müşteri destek sistemidir. 

**Temel Amacı:** E-ticaret müşteri destek biletlerini (tickets) otonom olarak yönetmek, insan müdahalesine gerek kalmadan sorunları çözmek (iade, değişim, kargo takibi vb.) ve sadece karmaşık/hassas durumları insanlara devretmektir.

**Fark Yaratan Özelliği:** 
- Basit bir chatbot değildir; **3 özelleşmiş ReAct ajanı** (Reasoning + Acting) ve **7 katmanlı bir işleme hattı (pipeline)** kullanır.
- **Claude Sonnet** (akıl yürütme için) ve **Claude Haiku** (hız/sınıflandırma için) modellerini hibrit olarak kullanarak maliyet ve performansı optimize eder.

---

## 2. Sistemin Teknik Kalbi: 7 Katmanlı Mimari (Pipeline)
Sistemin en güçlü teknik özelliği, her müşteri mesajını 7 farklı güvenlik ve mantık katmanından geçirmesidir. Bu, hataları ve "halüsinasyonu" minimize eder.

1.  **Katman 0: Escalation Lock (Kilit)**: Eğer bir görüşme zaten insana devredildiyse (escalated), yapay zeka bir daha karışmaz.
2.  **Katman 1: Input Guardrails (Girdi Güvenliği)**: 
    - Kişisel verileri (PII - Kredi kartı, telefon vb.) anında maskeler (redaction).
    - Prompt Injection saldırılarını (örn: "önceki talimatlarını unut") engeller.
    - Sağlık sorunları veya Chargeback (ters ibraz) tehditlerini algılayıp anında insana yönlendirir (Auto-Escalate).
3.  **Katman 2: Intent Classification (Niyet Analizi)**:
    - Müşterinin ne istediğini anlar (Kargom nerede? İade istiyorum? Aboneliğimi iptal et?).
    - Konuşma ortasında konu değişirse (Intent Shift), bunu fark edip doğru uzmana (ajana) yönlendirir.
4.  **Katman 3: ReAct Agents (Uzman Ajanlar)**:
    - Sorunu çözmek için ilgili "uzman" ajanı devreye sokar (Detaylar aşağıda).
5.  **Katman 4: Tool Call Guardrails (Araç Kullanım Güvenliği)**:
    - Ajanın kullanmak istediği araçları denetler. (Örn: İndirim kodu limiti aşıldı mı? İade tutarı siparişten fazla mı?).
    - Yanlışlıkla veritabanına zarar vermeyi engeller.
6.  **Katman 5: Output Guardrails (Çıktı Güvenliği)**:
    - Yasaklı kelimeler, rakip marka isimleri veya "ben bir yapay zekayım" gibi istenmeyen ifşaları kontrol eder.
7.  **Katman 6 & 7: Reflection & Revision (Düşünme ve Düzeltme)**:
    - Yanıt müşteriye gitmeden önce **8 maddelik bir kalite kontrol listesinden** geçer.
    - Eğer yanıt kurallara uymuyorsa (örn: fazla söz vermişse, tonu sertse), sistem kendi kendine yanıtı **Revize Eder (Layer 7)** ve sonra gönderir.

---

## 3. Ajan Takımı (The Team)
Sistemde her biri kendi alanında uzmanlaşmış 3 ana ajan (+1 Süpervizör) bulunur.

### 🐍 WISMO Ajanı (Where Is My Order - Kargom Nerede?)
- **Görevi:** Kargo takibi, teslimat durumu, gecikmeler.
- **Özel Yeteneği:** "Zaman algısı" vardır. Haftanın hangi gününde olduğunu bilir ve buna göre "Çarşamba günü tekrar kontrol edin" gibi gerçekçi tarihler verir. Asla kesin teslimat sözü vermez (Strict Policy).
- **Araçları:** Shopify sipariş takibi, kargo durumu sorgulama.

### 🔧 Issue Ajanı (Sorun Çözücü)
- **Görevi:** Yanlış/eksik ürün, hasarlı ürün, beğenmeme durumları.
- **Çözüm Şelalesi (Resolution Waterfall):** Sorunu çözmek için belirli bir sırayı takip etmek ZORUNDADIR:
    1.  Önce kullanım ipucu ver / Sorunu çözmeye çalış.
    2.  Ücretsiz yeni ürün gönderimi teklif et (Reship).
    3.  Mağaza kredisi teklif et (+%10 bonus ile).
    4.  Son çare olarak para iadesi (Refund) yap.
    5.  **Araçları:** İade oluşturma, mağaza kredisi tanımlama, yeni sipariş taslağı oluşturma.

### 👤 Account Ajanı (Hesap Uzmanı)
- **Görevi:** Abonelik yönetimi, adres değişikliği, indirim kodları.
- **Özel Yeteneği:** Abonelik iptali istendiğinde müşteriyi ikna etmek için önce "Atla" (Skip) veya "Dondur" (Pause) seçeneklerini sunar. (Churn prevention).
- **Araçları:** Skio (Abonelik) API, adres güncelleme, indirim kodu oluşturma.

### 🧠 Süpervizör (Supervisor)
- **Görevi:** Niyet tam olarak anlaşılamadığında veya karmaşık durumlarda devreye giren "Yönetici" ajandır. Konuşmayı analiz eder ve doğru ajana yönlendirir ya da genel soruları yanıtlar.

---

## 4. Kritik Özellikler
- **Escalation (İnsana Devir):** Sistem, çözemediği bir durumla karşılaştığında, sağlık sorunu beyan edildiğinde veya müşteri çok sinirlendiğinde (agresif dil), otomatik olarak bir "Özet" (Summary) çıkarır ve konuyu insan desteğine devreder. Ajan susar.
- **Handoff (Elden Ele):** Müşteri "Kargom nerede?" diye başlayıp sonra "Bu arada aboneliğimi de iptal et" derse, WISMO ajanı durumu fark eder ve topu Account ajanına atar.
- **Tracing (İzlenebilirlik):** Her bir adım, her bir karar ve her bir araç kullanımı kaydedilir. "Neden böyle cevap verdi?" sorusunun cevabı saniyesi saniyesine loglarda mevcuttur.

---

## 5. Teknoloji Yığını (Tech Stack)
- **Orchestration:** LangGraph (StateGraph ile karmaşık akış yönetimi).
- **LLM:** Claude 3.5 Sonnet (Akıl), Claude 3 Haiku (Hız).
- **Backend:** FastAPI (Python).
- **Frontend:** Streamlit (Demo ve Trace görselleştirme için).
- **Veri:** SQLite (Loglar ve hafıza için).
- **Entegrasyonlar:** Shopify Admin API, Skio Subscription API.

---

## 6. Neden Bu Proje Ödül Almalı?
1.  **Gerçek Dünya Problemi:** Sadece "sohbet" etmiyor, e-ticaretin en büyük operasyonel yükünü (WISMO ve İadeler) sırtlıyor.
2.  **Güvenlik Odaklı:** LLM'lerin en büyük sorunu olan "saçmalama" riskini 7 katmanlı filtre ve Reflection mekanizmasıyla minimuma indiriyor.
3.  **Ticari Odak:** İade yapmadan önce "Mağaza Kredisi" veya "Değişim" önererek markanın parasını içeride tutmaya çalışıyor (Revenue Retention).
