import re

from openai import OpenAI
from exa_py import Exa

TEAM_CONTEXT = """
ARC 6014, İstanbul'daki Robert Koleji'nde yer alan bir FIRST Robotics Competition (FRC) takımıdır.
2016 yılında kurulan takım, mühendislik ve teknoloji konusunda heyecanlı lise öğrencilerinden oluşmaktadır.

Önemli Başarılar:
- 2018 İstanbul Bölgesel Yarışması'nda finalist olarak "Wildcard Award" kazandı ve Houston,
  Texas'taki FRC Dünya Şampiyonası'na katıldı
- FIRST Impact Award (Bölgesel), Team Spirit Award, Innovation in Control Award, Imagery Award,
  Entrepreneurship Award ve FIRST Dean's List Finalist Award sahibi
- Archimedes ve Newton Divisionlarında FRC Dünya Şampiyonası'na katıldı
- "In//equality in STEM" konferansı düzenleyerek STEM alanındaki eşitsizliklere dikkat çekti

FIRST Robotics hakkında:
FIRST (For Inspiration and Recognition of Science and Technology), dünya genelinde gençleri STEM
konularında motive eden uluslararası bir organizasyondur. FRC, lise öğrencilerinin 6 hafta içinde
endüstriyel boyutlarda robotlar tasarlayıp inşa ettiği prestijli bir yarışmadır. Takımlar hem
teknik hem de profesyonel becerilerini geliştirerek gerçek dünya mühendislik deneyimi kazanır.

Sponsorluk Karşılıkları:
- Robot ve yarışma kıyafetlerinde şirket logosu
- Web sitesinde ve sosyal medyada kalıcı tanıtım
- Şirkete özel robotik demonstrasyonları ve STEM atölyeleri
- Yerel ve uluslararası yarışma medyasında görünürlük
- STEM topluluğuyla networking ve marka bilinirliği
"""


def find_contacts(company_name: str, company_url: str, exa_api_key: str) -> dict:
    """Find email addresses and LinkedIn profiles for a company."""
    exa = Exa(api_key=exa_api_key)
    emails = []
    people = []
    seen_emails = set()

    # 1. Crawl company pages for email addresses
    base = company_url.rstrip("/")
    pages = [base, f"{base}/iletisim", f"{base}/contact", f"{base}/hakkimizda", f"{base}/about"]
    try:
        result = exa.get_contents(pages, text={"max_characters": 3000})
        for r in result.results:
            if r.text:
                found = re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", r.text)
                for email in found:
                    if email not in seen_emails and not email.lower().endswith((".png", ".jpg")):
                        seen_emails.add(email)
                        emails.append(email)
    except Exception:
        pass

    # 2. Search LinkedIn for people at this company
    try:
        results = exa.search(
            f'"{company_name}" site:linkedin.com/in',
            type="auto",
            num_results=5,
            contents={"text": {"max_characters": 400}, "highlights": True},
        )
        for r in results.results:
            raw = r.title or ""
            name = raw.replace("| LinkedIn", "").strip()
            title = ""
            if " - " in name:
                parts = name.split(" - ")
                name = parts[0].strip()
                title = parts[1].strip() if len(parts) > 1 else ""
            if name:
                people.append({"name": name, "title": title, "linkedin_url": r.url})
    except Exception:
        pass

    return {"emails": emails, "people": people}


def find_rc_alumni(query_extra: str, exa_api_key: str, num_results: int = 10) -> list[dict]:
    """Search for Robert Koleji / Robert College alumni on LinkedIn via Exa."""
    exa = Exa(api_key=exa_api_key)
    query = '"Robert Koleji" OR "Robert College" site:linkedin.com/in'
    if query_extra.strip():
        query += f" {query_extra.strip()}"
    results = exa.search(
        query,
        type="auto",
        num_results=num_results,
        contents={"text": {"max_characters": 500}, "highlights": True},
    )
    people = []
    for r in results.results:
        raw = r.title or ""
        name = raw.replace("| LinkedIn", "").strip()
        title = ""
        if " - " in name:
            parts = name.split(" - ")
            name = parts[0].strip()
            title = parts[1].strip() if len(parts) > 1 else ""
        if name:
            people.append({
                "name": name,
                "title": title,
                "linkedin_url": r.url,
                "source": "RC Mezunu",
            })
    return people


def find_companies(query: str, exa_api_key: str, num_results: int = 8) -> list[dict]:
    """Search for companies related to a query using Exa."""
    exa = Exa(api_key=exa_api_key)
    results = exa.search(
        query,
        type="auto",
        num_results=num_results,
        contents={"text": {"max_characters": 800}, "highlights": True},
    )
    companies = []
    for r in results.results:
        desc = ""
        if hasattr(r, "highlights") and r.highlights:
            desc = r.highlights[0]
        elif r.text:
            desc = r.text[:200]
        companies.append({
            "name": r.title or r.url,
            "url": r.url,
            "description": desc,
        })
    return companies


def research_person(first_name: str, last_name: str, linkedin_url: str, exa_api_key: str) -> str:
    """Gather public info about the prospect using Exa."""
    exa = Exa(api_key=exa_api_key)
    name = f"{first_name} {last_name}"
    sections = []

    # 1. Livecrawl the LinkedIn URL directly
    try:
        result = exa.get_contents(
            [linkedin_url],
            text={"max_characters": 6000},
            highlights=True,
        )
        if result.results:
            r = result.results[0]
            content_parts = []
            if r.text and len(r.text.strip()) > 100:
                content_parts.append(r.text.strip())
            elif hasattr(r, "highlights") and r.highlights:
                content_parts.append("\n".join(r.highlights))
            if content_parts:
                sections.append("## LinkedIn Profil İçeriği\n" + "\n".join(content_parts))
    except Exception:
        pass

    # 2. People-category search (LinkedIn index)
    try:
        people = exa.search(
            name,
            type="auto",
            num_results=5,
            contents={"text": {"max_characters": 2000}, "highlights": True},
        )
        if people.results:
            items = []
            for r in people.results:
                chunk = f"**{r.title}** — {r.url}\n"
                if r.text and len(r.text.strip()) > 50:
                    chunk += r.text.strip()[:1500]
                elif hasattr(r, "highlights") and r.highlights:
                    chunk += "\n".join(r.highlights[:4])
                items.append(chunk)
            if items:
                sections.append("## Kişi Arama Sonuçları\n\n" + "\n\n---\n\n".join(items))
    except Exception:
        pass

    # 3. General web search for news, interviews, company pages
    try:
        web = exa.search(
            f"{name}",
            type="auto",
            num_results=5,
            contents={"highlights": True},
        )
        if web.results:
            items = []
            for r in web.results:
                chunk = f"**{r.title}** — {r.url}\n"
                if hasattr(r, "highlights") and r.highlights:
                    chunk += "\n".join(r.highlights[:4])
                items.append(chunk)
            if items:
                sections.append("## Genel Web Sonuçları\n\n" + "\n\n---\n\n".join(items))
    except Exception:
        pass

    if not sections:
        return f"{name} hakkında kamuya açık herhangi bir bilgiye ulaşılamadı."

    return "\n\n".join(sections)


def generate_email(first_name: str, last_name: str, research: str, openai_api_key: str) -> str:
    """Generate a hyper-personalized Turkish sponsorship email."""
    client = OpenAI(api_key=openai_api_key)

    prompt = f"""
ARC 6014 FRC Robotics Takımı adına {first_name} {last_name} için bir sponsorluk e-postası yazacaksın.

TAKIM BİLGİSİ:
{TEAM_CONTEXT}

SPONSOR ADAYI: {first_name} {last_name}

ARAŞTIRMA SONUÇLARI:
{research}

GÖREV:
Yukarıdaki araştırma sonuçlarını kullanarak tamamen Türkçe, son derece kişiselleştirilmiş bir
sponsorluk e-postası yaz.

KURALLAR:
1. E-posta tamamen Türkçe olmalı
2. Kişinin pozisyonuna, şirketine ve arka planına göre kişiselleştirilmiş olmalı — genel bir
   şablon gibi hissettirmemeli
3. Kişinin şirketinin veya kariyer geçmişinin ARC 6014'ün misyon ve değerleriyle nasıl
   örtüştüğünü doğal bir şekilde vurgula
4. Samimi, profesyonel ve sıcak bir ton kullan; robotik ve STEM'e olan tutkuyu yansıt
5. 300-400 kelime arasında tut
6. Konu satırı dahil et — dikkat çekici ve kişiye özel olmalı
7. Açık bir eylem çağrısı (CTA) içermeli (örn. kısa bir toplantı veya robot demonstrasyonu teklifi)
8. Takımın başarılarını abartmadan doğal biçimde yerleştir

FORMAT (tam olarak bu yapıyı kullan):
Konu: [konu satırı]

[e-posta gövdesi]

Saygılarımla,
ARC 6014 Takımı
Robert Koleji, İstanbul
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "Sen ARC 6014 FRC Robotics Takımı adına sponsorluk e-postaları yazan "
                    "deneyimli bir iletişim uzmanısın. Şablondan uzak, araştırma verilerine "
                    "dayanan, gerçekten kişiye özel Türkçe e-postalar yazarsın. Yazdığın email sadece bir kişiye yazılmış gibi durmalı."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=1500,
    )

    return response.choices[0].message.content
