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

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Ayarlar")
    openai_key = st.text_input(
        "OpenAI API Key",
        value=os.getenv("OPENAI_API_KEY", ""),
        type="password",
        help="E-posta üretimi için kullanılır",
    )
    exa_key = st.text_input(
        "Exa API Key",
        value=os.getenv("EXA_API_KEY", ""),
        type="password",
        help="Araştırma için kullanılır (exa.ai)",
    )
    st.divider()
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
                st.caption(person["linkedin_url"])
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

                    status_text.text(f"({i + 1}/{len(batch)}) {person['name']} araştırılıyor...")
                    try:
                        research = research_person(first, last, person["linkedin_url"], exa_key)
                    except Exception as e:
                        research = f"Araştırma başarısız: {e}"

                    status_text.text(f"({i + 1}/{len(batch)}) {person['name']} için e-posta yazılıyor...")
                    try:
                        email_text = generate_email(first, last, research, openai_key)
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
            writer.writerow(["Ad", "Soyad", "Pozisyon", "Kaynak", "LinkedIn URL", "E-posta"])
            for r in results:
                writer.writerow([
                    r.get("first", ""),
                    r.get("last", ""),
                    r.get("title", ""),
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
            for r in results:
                label = r["name"]
                if r.get("title"):
                    label += f" — {r['title']}"
                with st.expander(label):
                    st.text_area(
                        "E-posta",
                        r["email_text"],
                        height=300,
                        key=f"preview_{r['linkedin_url']}",
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
