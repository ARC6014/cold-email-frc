# ARC 6014 Sponsorluk E-postası Üretici

Robert Koleji FRC Takımı (ARC 6014) için kişiselleştirilmiş **Türkçe sponsorluk
e-postaları** üreten Streamlit uygulaması. Exa ile aday hakkında araştırma yapar,
OpenAI ile e-postayı yazar.

## Özellikler

- **Şirket Bul** — Exa ile şirket ara, iletişim e-postaları ve LinkedIn kişilerini bul.
- **RC Mezunları** — LinkedIn'de Robert Koleji / Robert College mezunlarını ara.
- **Toplu Üretim** — Kişi listesi için toplu e-posta üret; sonuçları CSV indir.
  - **CSV içe aktar**: mevcut aday tablonuzu yükleyin (aşağıdaki sütun düzeni).
- **Direkt E-posta** — Tek bir kişi için ad/soyad/LinkedIn ile e-posta üret.

## CSV içe aktarma formatı

Sekme (tab), virgül veya noktalı virgülle ayrılmış dosyalar; başlıklar Türkçe ve
büyük/küçük harf + Türkçe karakter duyarsız eşleşir:

| (atanan) | Şirket | Tam İsim | Contact Info (mail) | Hitap | Telefon | Notlar |
|----------|--------|----------|---------------------|-------|---------|--------|
| Aslı Ceylan | Tüpraş | Begüm Batmanoğlı | begum.batmanoglu@tupras.com.tr | Begüm Hanım | | Rc mezunu |

- **Tam İsim** zorunludur. Diğerleri isteğe bağlı.
- **Hitap** e-postanın açılış hitabı olarak kullanılır.
- **Notlar** (rol, "Rc mezunu" vb.) kişiselleştirme bağlamı olarak modele verilir.
- LinkedIn URL gerekmez — araştırma **isim + şirket** ile yapılır.

## Kurulum (yerel)

```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # anahtarları doldur
streamlit run app.py
```

`.env` de kullanılabilir (`OPENAI_API_KEY`, `EXA_API_KEY`, `APP_PASSWORD`);
uygulama önce `st.secrets`, sonra ortam değişkenlerine bakar.

## Streamlit Community Cloud'a deploy

1. Repoyu GitHub'a push edin.
2. [share.streamlit.io](https://share.streamlit.io) → **New app** → repo + `app.py`.
3. **App → Settings → Secrets** kısmına şunları girin:

   ```toml
   OPENAI_API_KEY = "sk-..."
   EXA_API_KEY = "exa-..."
   APP_PASSWORD = "takım-şifresi"
   ```

4. Deploy. Uygulama açılışta **takım şifresi** ister.

## Güvenlik notları

- API anahtarları **arayüzde girilmez**; yalnızca sunucudaki secrets/env'den okunur.
- `APP_PASSWORD` ayarlanmazsa uygulama şifresiz çalışır ve uyarı gösterir — herkese
  açık bir URL'de mutlaka ayarlayın (aksi halde krediler herkese açık olur).
- `.streamlit/secrets.toml` ve `.env` git'e **eklenmez** (`.gitignore`'da).

## Dosyalar

- `app.py` — Streamlit arayüzü, şifre kapısı, CSV içe/dışa aktarma.
- `generator.py` — Exa araştırma + OpenAI e-posta üretimi.
- `.streamlit/config.toml` — Streamlit ayarları.
- `.streamlit/secrets.toml.example` — secrets şablonu.
