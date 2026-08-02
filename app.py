import csv
import io
import os

import streamlit as st
from dotenv import load_dotenv

from generator import (
    find_companies,
    find_contacts,
    find_rc_alumni,
    generate_email,
    research_person,
)

load_dotenv()

st.set_page_config(
    page_title="ARC 6014 E-posta Üretici",
    page_icon="🤖",
    layout="centered",
)


# ── Config / secrets ──────────────────────────────────────────────────────────
def get_secret(name: str, default: str = "") -> str:
    """Read a value from Streamlit secrets, falling back to the environment."""
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return os.getenv(name, default)


def check_password() -> bool:
    """Gate the app behind a shared team password (APP_PASSWORD secret)."""
    app_password = get_secret("APP_PASSWORD")
    if not app_password:
        st.warning(
            "APP_PASSWORD ayarlanmadı — uygulama şifresiz çalışıyor. "
            "Yönetici: Streamlit secrets içine APP_PASSWORD ekleyin."
        )
        return True
    if st.session_state.get("auth_ok"):
        return True

    st.title("ARC 6014 E-posta Üretici")
    st.caption("Devam etmek için takım şifresini girin.")
    pw = st.text_input("Takım şifresi", type="password")
    if st.button("Giriş", type="primary"):
        if pw == app_password:
            st.session_state["auth_ok"] = True
            st.rerun()
        else:
            st.error("Yanlış şifre.")
    return False


if not check_password():
    st.stop()

# Keys are provided by the server (Streamlit secrets / env), never entered in the UI.
openai_key = get_secret("OPENAI_API_KEY")
exa_key = get_secret("EXA_API_KEY")
if not openai_key or not exa_key:
    st.error(
        "Sunucu yapılandırması eksik: OPENAI_API_KEY ve/veya EXA_API_KEY tanımlı değil. "
        "Yönetici: Streamlit secrets (veya .env) içine ekleyin."
    )
    st.stop()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    batch_count = len(st.session_state.get("batch_people", []))
    if batch_count:
        st.metric("Toplu listede", f"{batch_count} kişi")
        if st.button("Toplu Üretime Git", use_container_width=True):
            st.session_state["pending_tab"] = "Toplu Üretim"
            st.rerun()
        st.divider()
    st.markdown("**ARC 6014**")
    st.markdown("İstanbul Robert Koleji FRC Robotics Takımı")
    st.markdown("[arc6014.com](https://arc6014.com)")
    if st.session_state.get("auth_ok"):
        st.divider()
        if st.button("Çıkış", use_container_width=True):
            st.session_state.pop("auth_ok", None)
            st.rerun()

st.title("ARC 6014 Sponsorluk E-postası Üretici")
st.caption("Robert Koleji FRC Takımı için kişiselleştirilmiş Türkçe sponsorluk e-postaları")

# ── Session state defaults ────────────────────────────────────────────────────
if "batch_people" not in st.session_state:
    st.session_state["batch_people"] = []

# Apply any pending tab switch BEFORE the radio widget is instantiated
if "pending_tab" in st.session_state:
    st.session_state["active_tab"] = st.session_state.pop("pending_tab")
if "active_tab" not in st.session_state:
    st.session_state["active_tab"] = "Şirket Bul"

active_tab = st.radio(
    "Sekme",
    ["Şirket Bul", "RC Mezunları", "Toplu Üretim", "Direkt E-posta"],
    horizontal=True,
    key="active_tab",
    label_visibility="collapsed",
)

st.divider()


# ── Helpers ───────────────────────────────────────────────────────────────────
def _in_batch(linkedin_url: str) -> bool:
    return any(p["linkedin_url"] == linkedin_url for p in st.session_state["batch_people"])


def _render_person_row(person: dict, key_prefix: str):
    """Renders one person row with + Ekle and E-posta buttons."""
    col_p, col_add, col_email = st.columns([4, 1, 1])
    with col_p:
        st.markdown(f"**{person['name']}**")
        if person.get("title"):
            st.caption(person["title"])
        st.caption(person["linkedin_url"])
    with col_add:
        if _in_batch(person["linkedin_url"]):
            st.button("✓ Eklendi", key=f"{key_prefix}_add", disabled=True)
        else:
            if st.button("+ Ekle", key=f"{key_prefix}_add"):
                st.session_state["batch_people"].append(person)
                st.rerun()
    with col_email:
        if st.button("E-posta", key=f"{key_prefix}_email"):
            name_parts = person["name"].split(" ", 1)
            st.session_state["direct_first"] = name_parts[0]
            st.session_state["direct_last"] = name_parts[1] if len(name_parts) > 1 else ""
            st.session_state["direct_linkedin"] = person["linkedin_url"]
            st.session_state["pending_tab"] = "Direkt E-posta"
            st.rerun()
    st.divider()


def _norm(s: str) -> str:
    """Lowercase and strip Turkish diacritics for header matching."""
    table = str.maketrans("şŞıİğĞüÜöÖçÇ", "sSiIgGuUoOcC")
    return (s or "").strip().translate(table).lower()


def parse_prospect_csv(raw: str):
    """Parse a prospect sheet (CSV/TSV) into batch-people dicts.

    Recognized headers (Turkish, case/diacritic-insensitive): Şirket, Tam İsim,
    Contact Info (mail), Hitap, Telefon, Notlar. A leading unnamed column is
    treated as the assignee. Returns (people, warnings).
    """
    warnings = []
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    lines = raw.split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    if not lines:
        return [], ["Dosya boş."]

    header_line = lines[0]
    if "\t" in header_line:
        delim = "\t"
    elif header_line.count(";") > header_line.count(","):
        delim = ";"
    else:
        delim = ","

    rows = [r for r in csv.reader(lines, delimiter=delim)]
    if not rows:
        return [], ["Dosya okunamadı."]

    norm_header = [_norm(h) for h in rows[0]]

    def find_col(keywords):
        for idx, h in enumerate(norm_header):
            if any(k in h for k in keywords):
                return idx
        return None

    idx_company = find_col(["sirket", "company", "kurum", "firma"])
    idx_name = find_col(["tam isim", "ad soyad", "isim", "name", "kisi"])
    idx_email = find_col(["mail", "e-posta", "eposta", "email", "contact"])
    idx_sal = find_col(["hitap", "salutation"])
    idx_phone = find_col(["telefon", "phone", "gsm", "tel"])
    idx_notes = find_col(["not", "aciklama", "description"])
    idx_assignee = next((i for i, h in enumerate(norm_header) if not h), None)

    if idx_name is None:
        return [], ["'Tam İsim' sütunu bulunamadı. Başlık satırını kontrol edin."]
    if idx_email is None:
        warnings.append("E-posta sütunu bulunamadı; alıcı adresleri boş kalacak.")

    def cell(row, idx):
        return row[idx].strip() if idx is not None and idx < len(row) else ""

    people = []
    for row in rows[1:]:
        if not any(c.strip() for c in row):
            continue
        full_name = cell(row, idx_name)
        if not full_name:
            continue
        company = cell(row, idx_company)
        notes = cell(row, idx_notes)
        people.append({
            "name": full_name,
            "title": notes,
            "linkedin_url": "",
            "source": company,
            "company": company,
            "salutation": cell(row, idx_sal),
            "notes": notes,
            "email": cell(row, idx_email),
            "phone": cell(row, idx_phone),
            "assignee": cell(row, idx_assignee),
        })
    if not people:
        warnings.append("Veri satırı bulunamadı.")
    return people, warnings


# ── TAB: Şirket Bul ───────────────────────────────────────────────────────────
if active_tab == "Şirket Bul":

    # CONTACTS VIEW
    if "selected_company" in st.session_state:
        company = st.session_state["selected_company"]

        if st.button("← Geri"):
            for k in ("selected_company", "company_contacts"):
                st.session_state.pop(k, None)
            st.rerun()

        st.subheader(company["name"])
        st.caption(company["url"])

        if "company_contacts" not in st.session_state:
            with st.spinner("İletişim bilgileri aranıyor..."):
                try:
                    st.session_state["company_contacts"] = find_contacts(
                        company["name"], company["url"], exa_key
                    )
                except Exception as e:
                    st.error(f"Hata: {e}")
                    st.session_state["company_contacts"] = {"emails": [], "people": []}

        contacts = st.session_state["company_contacts"]
        emails_found = contacts.get("emails", [])
        people_found = contacts.get("people", [])

        if emails_found:
            st.markdown("**E-posta Adresleri**")
            for addr in emails_found:
                st.code(addr)

        if people_found:
            st.markdown("**LinkedIn'de Bulunan Kişiler**")
            for i, person in enumerate(people_found):
                person_with_source = {**person, "source": company["name"]}
                _render_person_row(person_with_source, f"cc_{i}")

        if not emails_found and not people_found:
            st.info("Bu şirket için iletişim bilgisi bulunamadı.")

    # SEARCH VIEW
    else:
        st.subheader("Şirket Ara")
        company_query = st.text_input(
            "Arama Sorgusu",
            placeholder="robotik otomasyon İstanbul",
            value="robotik otomasyon mühendislik İstanbul",
            key="company_query",
        )
        if st.button("Şirket Bul", type="primary", use_container_width=True):
            if not exa_key:
                st.error("Exa API anahtarı gerekli.")
            else:
                with st.spinner("Şirketler aranıyor..."):
                    try:
                        st.session_state["companies"] = find_companies(company_query, exa_key)
                    except Exception as e:
                        st.error(f"Hata: {e}")

        if "companies" in st.session_state and st.session_state["companies"]:
            companies = st.session_state["companies"]
            st.divider()
            st.markdown(f"**{len(companies)} şirket bulundu:**")
            for i, company in enumerate(companies):
                col_info, col_btn = st.columns([4, 1])
                with col_info:
                    st.markdown(f"**{company['name']}**")
                    st.caption(company["url"])
                    if company["description"]:
                        st.markdown(company["description"][:200])
                with col_btn:
                    if st.button("Seç", key=f"select_{i}"):
                        st.session_state["selected_company"] = company
                        st.rerun()
                st.divider()


# ── TAB: RC Mezunları ─────────────────────────────────────────────────────────
elif active_tab == "RC Mezunları":
    st.subheader("Robert Koleji Mezunlarını Ara")
    st.caption("LinkedIn'de RC mezunlarını bulur — şirkete sponsorluk önerisi için ideal hedef kitle.")

    alumni_filter = st.text_input(
        "Filtre (isteğe bağlı)",
        placeholder="CEO, teknoloji, finans...",
        key="alumni_filter",
    )
    if st.button("Mezunları Bul", type="primary", use_container_width=True):
        if not exa_key:
            st.error("Exa API anahtarı gerekli.")
        else:
            with st.spinner("RC mezunları aranıyor..."):
                try:
                    st.session_state["alumni_results"] = find_rc_alumni(alumni_filter, exa_key)
                except Exception as e:
                    st.error(f"Hata: {e}")

    if "alumni_results" in st.session_state:
        alumni = st.session_state["alumni_results"]
        if alumni:
            st.divider()
            st.markdown(f"**{len(alumni)} mezun bulundu:**")
            for i, person in enumerate(alumni):
                _render_person_row(person, f"al_{i}")
        else:
            st.info("Sonuç bulunamadı.")


# ── TAB: Toplu Üretim ─────────────────────────────────────────────────────────
elif active_tab == "Toplu Üretim":
    with st.expander("CSV / tablo içe aktar", expanded=not st.session_state["batch_people"]):
        st.caption(
            "Sütunlar: **Şirket, Tam İsim, Contact Info (mail), Hitap, Telefon, Notlar** "
            "(baştaki isimsiz sütun 'atanan' olarak alınır). Sekme, virgül veya noktalı "
            "virgülle ayrılmış dosyalar desteklenir."
        )
        uploaded = st.file_uploader(
            "CSV / TSV dosyası", type=["csv", "tsv", "txt"], key="batch_csv"
        )
        replace_existing = st.checkbox("Mevcut listenin yerine koy", value=False)
        if uploaded is not None and st.button("İçe Aktar", key="import_csv"):
            data = uploaded.getvalue()
            raw = None
            for enc in ("utf-8-sig", "cp1254", "iso-8859-9"):
                try:
                    raw = data.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            if raw is None:
                raw = data.decode("utf-8", errors="replace")

            people, warnings = parse_prospect_csv(raw)
            if not people:
                st.error("Dosyadan geçerli kişi okunamadı. Sütun başlıklarını kontrol edin.")
                for w in warnings:
                    st.warning(w)
            else:
                if replace_existing:
                    st.session_state["batch_people"] = people
                    added = len(people)
                else:
                    existing = st.session_state["batch_people"]
                    seen = {(p.get("name", ""), p.get("company", "")) for p in existing}
                    added = 0
                    for p in people:
                        key = (p.get("name", ""), p.get("company", ""))
                        if key not in seen:
                            existing.append(p)
                            seen.add(key)
                            added += 1
                st.session_state.pop("batch_results", None)
                st.success(f"{added} kişi içe aktarıldı.")
                for w in warnings:
                    st.warning(w)
                st.rerun()

    batch = st.session_state["batch_people"]

    if not batch:
        st.info(
            "Henüz kimse eklenmedi.  \n"
            "**Şirket Bul** veya **RC Mezunları** sekmesinden kişilerin yanındaki **+ Ekle** butonuna tıklayın."
        )
    else:
        st.markdown(f"**{len(batch)} kişi seçildi:**")

        for i, person in enumerate(batch):
            col_p, col_del = st.columns([5, 1])
            with col_p:
                st.markdown(f"**{person['name']}**")
                parts = [person.get("title", ""), person.get("source", "")]
                st.caption(" · ".join(p for p in parts if p))
                st.caption(person.get("linkedin_url") or person.get("email", ""))
            with col_del:
                if st.button("Kaldır", key=f"remove_{i}"):
                    st.session_state["batch_people"].pop(i)
                    st.session_state.pop("batch_results", None)
                    st.rerun()

        st.divider()

        col_gen, col_clear = st.columns([3, 1])
        with col_gen:
            generate_all = st.button("Tümünü Oluştur", type="primary", use_container_width=True)
        with col_clear:
            if st.button("Listeyi Temizle", use_container_width=True):
                st.session_state["batch_people"] = []
                st.session_state.pop("batch_results", None)
                st.rerun()

        if generate_all:
            if not openai_key or not exa_key:
                st.error("OpenAI ve Exa API anahtarları gerekli.")
            else:
                results = []
                progress_bar = st.progress(0)
                status_text = st.empty()

                for i, person in enumerate(batch):
                    name_parts = person["name"].split(" ", 1)
                    first = name_parts[0]
                    last = name_parts[1] if len(name_parts) > 1 else ""

                    company = person.get("company", "") or person.get("source", "")
                    status_text.text(f"({i + 1}/{len(batch)}) {person['name']} araştırılıyor...")
                    try:
                        research = research_person(
                            first, last, person.get("linkedin_url", ""), exa_key, company=company
                        )
                    except Exception as e:
                        research = f"Araştırma başarısız: {e}"

                    status_text.text(f"({i + 1}/{len(batch)}) {person['name']} için e-posta yazılıyor...")
                    try:
                        email_text = generate_email(
                            first, last, research, openai_key,
                            company=company,
                            salutation=person.get("salutation", ""),
                            notes=person.get("notes", "") or person.get("title", ""),
                        )
                    except Exception as e:
                        email_text = f"E-posta oluşturulamadı: {e}"

                    results.append({**person, "first": first, "last": last, "email_text": email_text})
                    progress_bar.progress((i + 1) / len(batch))

                status_text.success(f"{len(results)} e-posta oluşturuldu!")
                st.session_state["batch_results"] = results

        if "batch_results" in st.session_state:
            results = st.session_state["batch_results"]

            # Build CSV
            out = io.StringIO()
            writer = csv.writer(out, quoting=csv.QUOTE_ALL)
            writer.writerow([
                "Atanan", "Şirket", "Ad", "Soyad", "Hitap",
                "Alıcı E-posta", "Not", "Kaynak", "LinkedIn URL", "Üretilen E-posta",
            ])
            for r in results:
                writer.writerow([
                    r.get("assignee", ""),
                    r.get("company", "") or r.get("source", ""),
                    r.get("first", ""),
                    r.get("last", ""),
                    r.get("salutation", ""),
                    r.get("email", ""),
                    r.get("notes", "") or r.get("title", ""),
                    r.get("source", ""),
                    r.get("linkedin_url", ""),
                    r.get("email_text", ""),
                ])

            st.download_button(
                "CSV İndir",
                out.getvalue(),
                file_name="arc6014_sponsorluk_emailleri.csv",
                mime="text/csv",
                type="primary",
                use_container_width=True,
            )

            st.markdown("**Önizleme:**")
            for i, r in enumerate(results):
                label = r["name"]
                if r.get("company") or r.get("source"):
                    label += f" — {r.get('company') or r.get('source')}"
                elif r.get("title"):
                    label += f" — {r['title']}"
                with st.expander(label):
                    if r.get("email"):
                        st.caption(f"Alıcı: {r['email']}")
                    st.text_area(
                        "E-posta",
                        r["email_text"],
                        height=300,
                        key=f"preview_{i}",
                        label_visibility="collapsed",
                    )


# ── TAB: Direkt E-posta ───────────────────────────────────────────────────────
else:
    st.subheader("Direkt E-posta Oluştur")

    col1, col2 = st.columns(2)
    with col1:
        first_name_d = st.text_input("Ad", placeholder="Ahmet", key="direct_first")
    with col2:
        last_name_d = st.text_input("Soyad", placeholder="Yılmaz", key="direct_last")

    linkedin_url_d = st.text_input(
        "LinkedIn URL",
        placeholder="https://www.linkedin.com/in/username/",
        key="direct_linkedin",
    )

    if st.button("E-posta Oluştur", type="primary", use_container_width=True, key="direct_gen"):
        if not first_name_d or not last_name_d:
            st.error("Ad ve soyad alanları zorunludur.")
        elif not linkedin_url_d or "linkedin.com" not in linkedin_url_d:
            st.error("Geçerli bir LinkedIn URL'si girin.")
        elif not openai_key:
            st.error("OpenAI API anahtarı gerekli.")
        elif not exa_key:
            st.error("Exa API anahtarı gerekli.")
        else:
            with st.spinner(f"{first_name_d} {last_name_d} araştırılıyor..."):
                try:
                    research = research_person(first_name_d, last_name_d, linkedin_url_d, exa_key)
                except Exception as e:
                    st.error(f"Araştırma sırasında hata: {e}")
                    st.stop()

            with st.expander("Araştırma Sonuçları", expanded=False):
                st.markdown(research)

            with st.spinner("E-posta yazılıyor..."):
                try:
                    email = generate_email(first_name_d, last_name_d, research, openai_key)
                except Exception as e:
                    st.error(f"E-posta oluşturulurken hata: {e}")
                    st.stop()

            st.success("E-posta oluşturuldu!")
            st.download_button(
                "E-postayı İndir (.txt)",
                email,
                file_name=f"{first_name_d}_{last_name_d}_sponsorluk.txt",
                mime="text/plain",
            )
            st.text_area("E-posta", email, height=500, label_visibility="collapsed")
