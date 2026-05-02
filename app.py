import streamlit as st
from generator import research_person, generate_email
import os
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="ARC 6014 E-posta Üretici",
    page_icon="🤖",
    layout="centered",
)

st.title("ARC 6014 Sponsorluk E-postası Üretici")
st.caption("Robert Koleji FRC Takımı için kişiselleştirilmiş Türkçe sponsorluk e-postaları")

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
        help="Kişi araştırması için kullanılır (exa.ai)",
    )
    st.divider()
    st.markdown("**ARC 6014**")
    st.markdown("İstanbul Robert Koleji FRC Robotics Takımı")
    st.markdown("[arc6014.com](https://arc6014.com)")

st.divider()

col1, col2 = st.columns(2)
with col1:
    first_name = st.text_input("Ad", placeholder="Ahmet")
with col2:
    last_name = st.text_input("Soyad", placeholder="Yılmaz")

linkedin_url = st.text_input(
    "LinkedIn URL",
    placeholder="https://www.linkedin.com/in/username/",
)

generate_btn = st.button("E-posta Oluştur", type="primary", use_container_width=True)

if generate_btn:
    if not first_name or not last_name:
        st.error("Ad ve soyad alanları zorunludur.")
    elif not linkedin_url or "linkedin.com" not in linkedin_url:
        st.error("Geçerli bir LinkedIn URL'si girin.")
    elif not openai_key:
        st.error("OpenAI API anahtarı gerekli.")
    elif not exa_key:
        st.error("Exa API anahtarı gerekli.")
    else:
        with st.spinner(f"{first_name} {last_name} araştırılıyor..."):
            try:
                research = research_person(first_name, last_name, linkedin_url, exa_key)
            except Exception as e:
                st.error(f"Araştırma sırasında hata oluştu: {e}")
                st.stop()

        with st.expander("Araştırma Sonuçları", expanded=False):
            st.markdown(research)

        with st.spinner("Kişiselleştirilmiş e-posta yazılıyor..."):
            try:
                email = generate_email(first_name, last_name, research, openai_key)
            except Exception as e:
                st.error(f"E-posta oluşturulurken hata oluştu: {e}")
                st.stop()

        st.success("E-posta oluşturuldu!")

        st.download_button(
            "E-postayı İndir (.txt)",
            email,
            file_name=f"{first_name}_{last_name}_sponsorluk.txt",
            mime="text/plain",
        )

        st.subheader("Oluşturulan E-posta")
        st.text_area("E-posta", email, height=500, label_visibility="collapsed")
