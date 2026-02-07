# test_results_20260207_070355 için teknik değerlendirme

> Not: Repoda `test_results_20260207_070355.log` ve `test_failures_20260207_070355.log` dosyaları bulunamadığı için aynı kapsamda doğrulama amacıyla testler yeniden çalıştırıldı.

## 1) Genel durum (yeniden çalıştırılan sonuç)

- Toplam: **13 failed**, **24 error**, **165 passed**.
- Yani sistemin önemli bir kısmı çalışıyor; fakat özellikle **E2E async test kurulumu** ve **mock API bağımlılığı** tarafında kırılma var.

## 2) Parça parça kök neden analizi

### A. E2E async testleri neden ERROR veriyor?

Belirti:
- `tests/test_e2e_conservations.py` içindeki async fixture (`async_client`) setup aşamasında hata veriyor.
- `pytest.mark.asyncio` için `UnknownMarkWarning` oluşuyor.

Muhtemel neden:
- Projede `pytest-asyncio` bağımlılığı requirements içinde tanımlı değil.
- Async fixture `@pytest.fixture` ile tanımlı; pytest 9 ile birlikte bu kullanım plugin olmadan sorun çıkarıyor.

Kod göstergeleri:
- Tüm dosya `pytest.mark.asyncio` ile işaretli.
- `async_client` async fixture olarak tanımlı.

Sonuç:
- Bu durumda konuşma kalite kontrolleri (`assert_response_quality`) hiç çalışmadan test setup'ta düşüyor; yani "cevap iyi mi" sorusu bu test setinde şu an teknik olarak doğrulanamıyor.

### B. mock-api testleri neden FAILED?

Belirti:
- `mock-api/test_mock_api.py` testleri `localhost:8080` bağlantı hatası ile düşüyor (`Connection refused`).

Muhtemel neden:
- Test dosyası mock server'ın dışarıda ayakta olmasını bekliyor.
- Bu çalıştırmada ilgili servis ayağa kaldırılmadan pytest koşturulmuş.

Kod göstergeleri:
- `BASE = "http://localhost:8080/hackhaton"`
- `ADMIN = "http://localhost:8080/admin"`
- `reset()` çağrıları doğrudan bu adrese istek atıyor.

Sonuç:
- Bu test FAIL'leri ürün cevabının kalitesinden çok **test ortamı/servis orkestrasyonu** kaynaklı.

### C. "Model soruları istenildiği gibi cevaplıyor mu?"

Elde edilen sinyal:
- İzole/unit ve senaryo bazlı 165 testin geçmesi, routing/guardrail/handoff/escalation mantığının önemli bölümünün beklenen davranışta olduğunu gösteriyor.
- Ancak E2E konuşma akışları teknik kurulum nedeniyle çalışmadığından gerçek "cevap kalitesi" için kritik senaryolar doğrulanamıyor.

Yorum:
- Şu anki kırılma "cevap kalitesi kesin kötü" demek için yeterli kanıt değil.
- Daha güçlü bulgu: **değerlendirme altyapısı eksik/yarım** olduğu için kaliteyi ölçen testler tamamlanamıyor.

## 3) Problem düzgün cevap verememe ise olası nedenler

E2E düzgün çalıştırıldıktan sonra da kötü cevaplar görülürse öncelikli şüpheli alanlar:

1. **Model erişimi/anahtar/config**
   - LLM erişimi yoksa fallback davranışları düşük kalite üretebilir.
2. **Prompt/guardrail çatışması**
   - Çok katı output guardrail, doğal/yardımcı cevabı aşırı kesebilir.
3. **Intent confidence eşikleri**
   - Eşikler agresifse yanlış agente routing olur, cevap alakasızlaşır.
4. **Tool veri bağımlılığı**
   - Shopify/Skio/mock veri eksikse ajanlar eksik bağlamla yanıtlar.
5. **Revision/reflection döngüsü**
   - Revizyon katmanı fazla müdahale edip netliği düşürebilir.

## 4) Hızlı aksiyon planı

1. `pytest-asyncio` bağımlılığını ekle.
2. E2E async fixture kullanımını pytest 9 ile uyumlu hale getir (`pytest_asyncio.fixture` + `pytest.ini` ile marker/asyncio_mode).
3. mock-api server'ı testten önce otomatik ayağa kaldır (veya testte skip/health-check gate).
4. Sonra sadece E2E konuşma testlerini yeniden koşturup kaliteyi senaryo bazında raporla.

Bu sıralama ile önce test altyapısı stabilize edilir; ardından "cevaplar gerçekten istenildiği gibi mi" sorusuna güvenilir şekilde karar verilir.
