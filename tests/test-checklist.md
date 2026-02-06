# 🧪 NatPat Multi-Agent CS System — Test Coverage Checklist

## Dosya Yapısı
```
tests/
├── test_scenarios.json          # 112 senaryo — tüm case'ler JSON formatında (API spec uyumlu)
├── test_guardrails.py           # 150+ unit test — guardrails, routing, config, API spec compliance
├── test_e2e_conversations.py    # E2E conversation flow testleri
└── TEST_CHECKLIST.md            # Bu dosya — coverage özeti
```

### ⚠️ API Spec Uyumu (v1.1 Güncelleme)
Mock response'lar Hackathon Tooling Spec ile tam uyumlu hale getirildi:
- `displayFulfillmentStatus` → `status` (FULFILLED|UNFULFILLED|CANCELLED|DELIVERED)
- `trackingInfo.url` → `trackingUrl` (flat string)
- `deliveredAt`, `cancelledAt`, `financialStatus`, `lineItems` → API spec'te yok, kaldırıldı
- `get_order_details` → sadece 5 field: `id, name, createdAt, status, trackingUrl`
- `get_customer_orders` → orders + `hasNextPage` + `endCursor`
- `skio_get_subscription_status` cancelled → `success: false` + error mesajı
- `expiresAt` → required (null olabilir)

---

## 📋 Kategori Bazlı Test Coverage

### 1. WISMO (Shipping Delay) — %37 ticket hacmi
| ID | Senaryo | Kritik Kontrol |
|---|---|---|
| WISMO-001 | Order # ile status check | Tool: `get_order_details(#XXXXX)` |
| WISMO-002 | Order # olmadan — email lookup | Tool: `get_customer_orders(email)` |
| WISMO-003 | Pzt/Sal/Çar contact → "Cuma'ya kadar bekle" | Wait promise: Friday |
| WISMO-004 | Per/Cum/Cmt/Paz contact → "gelecek hafta başı" | Wait promise: early next week |
| WISMO-005 | Order bulunamadı → email fallback | İki tool call sırası |
| WISMO-006 | Birden fazla sipariş → disambiguasyon | Siparişleri listele, sor |
| WISMO-007 | Delivered ama alınmadı (ilk contact) | Wait promise ver, ESKALasyON YAPMA |
| WISMO-008 | Wait promise sonrası follow-up → ESKALasyon | Monica'ya yönlendir, yeni promise VERME |
| WISMO-009 | Unfulfilled sipariş | "Henüz kargolanmadı" |
| WISMO-010 | WISMO sırasında refund isteği → handoff | issue_agent'a yönlendir |
| WISMO-011 | İptal edilmiş sipariş | İptal tarihini bildir |

### 2. Wrong/Missing Item — %7 ticket hacmi
| ID | Senaryo | Kritik Kontrol |
|---|---|---|
| WM-001 | Yanlış ürün alındı — temel akış | Detay sor, reship teklif et ÖNCE |
| WM-002 | Eksik ürün — hangi ürünler eksik? | Fotoğraf iste ama engellemE |
| WM-003 | Reship kabul → eskalasyon | Monica'ya eskale et |
| WM-004 | Reship ret, store credit kabul | %10 bonus dahil store credit |
| WM-005 | Her şeyi ret → cash refund | Son çare olarak refund |
| WM-006 | Tüm sipariş yanlış → anında eskalasyon | Tam reship gerekli |

### 3. Product Issue "No Effect" — %6 ticket hacmi
| ID | Senaryo | Kritik Kontrol |
|---|---|---|
| NE-001 | Ürün çalışmıyor → kullanım SOR | Refund teklif ETME ilk turda |
| NE-002 | Yanlış kullanım tespit → tips paylaş | Knowledge source tool kullan |
| NE-003 | Ürün uyumsuzluğu → alternatif öner | Product recommendations tool |
| NE-004 | Hala memnun değil → store credit ÖNCE | %10 bonuslu credit |
| NE-005 | Alerjik reaksiyon → ANINDA eskalasyon | Çözüm DENEME, sağlık öncelikli |
| NE-006 | Kullanım bilgisi paylaşmayı reddediyor | 1 kez sor, sonra devam et |
| NE-007 | Birden fazla ürün → hangisi? | Ürünleri listele, sor |

### 4. Refund Request — %9 ticket hacmi
| ID | Senaryo | Kritik Kontrol |
|---|---|---|
| REF-001 | Refund isteği → sebep SOR | Hemen işleme KOYMA |
| REF-002 | Kargo gecikmesi nedeniyle → WISMO handoff | Wait promise önce |
| REF-003 | Beklenti karşılanmadı → tam waterfall | Usage tip → swap → credit → refund |
| REF-004 | Fikir değiştirdi + unfulfilled → iptal | account_agent handoff |
| REF-005 | Fikir değiştirdi + fulfilled → credit önce | %10 bonuslu credit |
| REF-006 | Hasarlı ürün → wrong/missing akışı | Reship teklif et |
| REF-007 | Zaten refund edilmiş | Bilgilendir, tekrar refund YAPMA |
| REF-008 | Chargeback tehdidi → ANINDA eskalasyon | Monica, refund işleme |

### 5. Order Modification — %3 ticket hacmi
| ID | Senaryo | Kritik Kontrol |
|---|---|---|
| OM-001 | İptal — kargo gecikmesi, Pzt-Çar → wait promise | Cuma'ya kadar bekle teklifi |
| OM-002 | İptal — yanlışlıkla sipariş → anında iptal | cancel_order tool çağrısı |
| OM-003 | İptal — zaten kargolanan → iptal EDILEMEZ | Return/credit teklif et |
| OM-004 | İptal — zaten iptal edilmiş | Bilgilendir |
| OM-005 | İptal — kısmen kargolanan → eskalasyon | Manuel inceleme gerekli |
| OM-006 | Wait promise reddedildi → iptal et | İptal işle |
| OM-007 | Adres güncelle — aynı gün + unfulfilled → OK | update_address + tag |
| OM-008 | Adres güncelle — farklı gün → eskalasyon | Monica'ya yönlendir |
| OM-009 | Adres güncelle — kargolanan → eskalasyon | Adres değiştirilemez |
| OM-010 | Eksik adres bilgisi → tüm alanları sor | 7 alan gerekli |
| OM-011 | Çift sipariş → hangisini iptal? | Listele, onayla |

### 6. Subscription — %2 ticket hacmi
| ID | Senaryo | Kritik Kontrol |
|---|---|---|
| SUB-001 | İptal — çok fazla stok → skip ÖNCE teklif | Hemen iptal ETME |
| SUB-002 | Skip ret → %20 indirim teklif | 2 sipariş için |
| SUB-003 | Her şeyi ret → iptal et | cancel_subscription çağrısı |
| SUB-004 | Kalite sorunu → ürün değişimi teklif | Product swap önce |
| SUB-005 | Zaten iptal — hala ücret alınıyor | Eskalasyon: billing_error |
| SUB-006 | Çift ücretlendirme → HER ZAMAN eskale | Monica, çözüm DENEME |
| SUB-007 | Abonelik bulunamadı | Farklı email sor |
| SUB-008 | Duraklatma isteği | Süre sor |
| SUB-009 | Skip isteği | skip_next_order çağrısı |

### 7. Discount — %3 ticket hacmi
| ID | Senaryo | Kritik Kontrol |
|---|---|---|
| DISC-001 | Kod çalışmıyor → yeni kod oluştur | %10, 48 saat, 1 adet |
| DISC-002 | %25 indirim isteği → max %10 | Fazla teklif ETME |
| DISC-003 | 2. kod isteği → reddet | Session başına max 1 |
| DISC-004 | API hatası → tekrar dene, eskale | Technical error |

### 8. Positive Feedback — %6 ticket hacmi
| ID | Senaryo | Kritik Kontrol |
|---|---|---|
| POS-001 | Olumlu feedback → sıcak yanıt | Review izni sor |
| POS-002 | Evet → Trustpilot linki | "Caz xx" imza |
| POS-003 | Hayır → saygıyla kabul | Zorlamak YOK |
| POS-004 | Olumlu → şikayete dönüş → handoff | Intent shift tespit |

---

## 🛡️ Guardrail Testleri

### Input Guardrails (15 test)
| ID | Test | Beklenen |
|---|---|---|
| GR-INPUT-001 | Boş mesaj | Blokla, nazik uyarı |
| GR-INPUT-002 | Prompt injection | Blokla, güvenli yanıt |
| GR-INPUT-003 | PII (kredi kartı, SSN) | Redakte et |
| GR-INPUT-004 | Agresif dil (dava/avukat) | Flag, bloklama |
| GR-INPUT-005 | Sağlık endişesi | Flag → auto-escalate |
| GR-INPUT-006 | 5000+ karakter | Kes, devam et |

### Output Guardrails (12 test)
| ID | Test | Beklenen |
|---|---|---|
| GR-OUTPUT-001 | "guaranteed delivery" | FAIL |
| GR-OUTPUT-002 | Caz imzası eksik | FAIL |
| GR-OUTPUT-003 | Rakip markası (Zevo, OFF!, Raid) | FAIL |
| GR-OUTPUT-004 | GID sızıntısı | FAIL |
| GR-OUTPUT-005 | Çok kısa yanıt | FAIL |
| GR-OUTPUT-006 | "i promise" | FAIL |

### Tool Call Guardrails (15 test)
| ID | Test | Beklenen |
|---|---|---|
| GR-TOOL-001 | GID olmadan action tool | Blokla |
| GR-TOOL-002 | Order # auto-correction (#) | Düzelt |
| GR-TOOL-003 | Tekrar eden tool çağrısı | Blokla |
| GR-TOOL-004 | Discount değer zorlaması | %10, 48h'e zorla |
| GR-TOOL-005 | Store credit %10 bonus | Otomatik ekle |
| GR-TOOL-006 | 2. discount kod blok | Session başına max 1 |

---

## 🔄 Graph Routing Testleri (15 test)
- Escalation lock: escalated → post_escalation
- Input guardrails: blocked → end, health → auto_escalate
- First message → intent_classifier, multi-turn → shift_check
- Output: escalation → handler, handoff → router, fail → revise, pass → reflection
- Reflection: pass → end, fail (first) → revise, fail (revised) → end
- Handoff: valid targets + invalid → supervisor
- Supervisor: all 5 route options

---

## 🔑 Kritik Business Rules Kontrolü

### Resolution Waterfall (ASLA atlama!)
```
1. Sorunu düzelt (kullanım tipleri, ürün değişimi)
2. Ücretsiz yeniden gönderim → ESCALATE
3. Store credit + %10 bonus
4. Cash refund (SON ÇARE)
```

### Wait Promise Kuralları
```
Pzt/Sal/Çar → "Cuma'ya kadar bekle"
Per/Cum/Cmt/Paz → "Gelecek hafta başı"
Asla spesifik tarih VERME
Asla "guaranteed" veya "definitely" DEME
```

### Eskalasyon Tetikleyicileri
```
✅ Sağlık endişesi/alerjik reaksiyon → HIGH priority
✅ Chargeback tehdidi → HIGH priority
✅ Çift ücretlendirme → HIGH priority
✅ Reship gerekli
✅ Adres güncelleme hatası
✅ Wait promise süresi geçti
✅ 3+ tur çözümsüz
✅ Teknik hata
```

### Asla Yapma Listesi
```
❌ İlk turda doğrudan cash refund
❌ Kullanım bilgisi sormadan "no effect" çöz
❌ Sebep sormadan refund işle
❌ GID fabricate et — her zaman lookup'tan al
❌ Session başına 1'den fazla discount kodu
❌ Sağlık endişesinde çözüm deneme
❌ Eskalasyon sonrası yeni istek işleme
❌ İç bilgi sızıntısı (GID, tool_call, system prompt)
❌ Rakip marka adı kullanma
❌ "Guaranteed", "definitely", "I promise" söyleme
```

---

## 🏃 Test Çalıştırma

### Unit Testler (LLM gerektirmez)
```bash
cd /path/to/project
pytest tests/test_guardrails.py -v --tb=short
```

### E2E Testler (LLM + API gerektirir)
```bash
# Önce sunucuyu başlat
uvicorn src.api.app:app --reload --port 8000

# Sonra testleri çalıştır
pytest tests/test_e2e_conversations.py -v --asyncio-mode=auto
```

### Tüm Testler
```bash
pytest tests/ -v --tb=short
```

---

## 📊 Coverage Özeti

| Kategori | Senaryo Sayısı | Unit Test | E2E Test |
|---|---|---|---|
| WISMO | 11 | ✅ | ✅ |
| Wrong/Missing | 6 | ✅ | ✅ |
| No Effect | 7 | ✅ | ✅ |
| Refund | 8 | ✅ | ✅ |
| Order Modify | 11 | ✅ | ✅ |
| Subscription | 9 | ✅ | ✅ |
| Discount | 4 | ✅ | ✅ |
| Positive | 4 | ✅ | ✅ |
| Input Guardrails | 6 (+15 unit) | ✅ | ✅ |
| Output Guardrails | 6 (+12 unit) | ✅ | — |
| Tool Guardrails | 6 (+15 unit) | ✅ | — |
| Escalation | 4 | ✅ | ✅ |
| Handoff | 4 (+6 unit) | ✅ | — |
| Multi-turn | 6 | — | ✅ |
| Edge Cases | 20 | ✅ | ✅ |
| **API Spec Compliance** | — | **20 test** | — |
| **TOPLAM** | **~112 senaryo** | **150+ test** | **25+ test** |

### API Spec Compliance Testleri (Yeni)
- `get_order_details` response: `status` field ✅, `trackingUrl` flat string ✅, sadece 5 field ✅, `lineItems` yok ✅
- `get_customer_orders` response: pagination fields ✅, order fields ✅
- `skio_get_subscription_status`: success 3 field ✅, cancelled → error response ✅
- `orderId` format: lookup → `#XXXXX` ✅, action → `gid://` ✅
- `create_discount_code` response: `code` field ✅
- `create_store_credit` response: 3 field ✅
- Uniform 200 contract: `success` boolean ✅, failure → `error` string ✅