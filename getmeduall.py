import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import time
from io import BytesIO
from docx import Document
from docx.shared import Inches
import pandas as pd

# === 単元情報の読み込み ===
@st.cache_data
def load_unit_mapping(uploaded_file):
    df = pd.read_csv(uploaded_file)
    return dict(zip(df['問題番号'], df['単元名']))

# === ページ取得関数 ===
def get_page_text(url, qid, unit_map, get_images=True):
    try:
        resp = requests.get(url)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, 'html.parser')
        category = unit_map.get(qid, soup.find('span', class_='button-small-line').text.strip() if soup.find('span', class_='button-small-line') else '分野名なし')
        problem = soup.find('div', class_='quiz-body mb-64')
        choices = [f"{c.find('span', class_='choice-header').text.strip()} {c.find_all('span')[1].text.strip()}"
                   for c in soup.find_all('div', class_='box-select')]
        h4s = soup.find_all('h4')
        ans = h4s[0].text.strip() if h4s else '解答なし'
        expl = soup.find('div', class_='explanation').text.strip() if soup.find('div', class_='explanation') else '解説なし'
        imgs = []
        if get_images:
            for d in soup.find_all('div', class_='box-quiz-image mb-32'):
                img = d.find('img')
                if img and img.get('src'):
                    imgs.append(img['src'].replace('thumb_', ''))
        return {
            "category": category,
            "problem": problem.text.strip() if problem else '問題文なし',
            "choices": choices,
            "answer": ans,
            "question_id": qid,
            "explanation": expl,
            "images": imgs
        }
    except:
        return None

# === Word生成関数 ===
def create_word_doc(pages, year, label, include_images=True):
    doc = Document()
    doc.add_heading(f'{year}年 医師国家試験問題（{label}）', 0)
    doc.add_paragraph(f"取得問題数: {len(pages)}問")
    for i, p in enumerate(pages, 1):
        doc.add_heading(f"問題{ i } {p['question_id']}", level=2)
        doc.add_paragraph(f"単元: {p['category']}")
        doc.add_paragraph(p['problem'])
        if include_images and p['images']:
            for url in p['images']:
                try:
                    r = requests.get(url)
                    if r.status_code == 200:
                        img_stream = BytesIO(r.content)
                        doc.add_picture(img_stream, width=Inches(2.5))
                except:
                    pass
        doc.add_paragraph("選択肢：")
        for c in p['choices']:
            doc.add_paragraph(c)
        doc.add_paragraph(p['answer'])
        doc.add_paragraph("解説: " + p['explanation'])
        doc.add_page_break()
    fn = f"{year}_{label}_medu4.docx"
    doc.save(fn)
    return fn

# === セクションごとの取得関数 ===
def scrape_sections(year, sections, unit_map, include_images=True):
    collected = []
    for sec_idx, sec in enumerate(sections):
        st.markdown(f"### ▶️ セクション {sec} を取得中...")
        bar = st.progress(0)
        fail_count = 0
        for i, num in enumerate(range(1, 81)):
            qid = f"{year}{sec}{num}"
            url = f"https://medu4.com/{qid}"
            data = get_page_text(url, qid, unit_map, get_images=include_images)
            if data:
                collected.append(data)
                fail_count = 0
            else:
                fail_count += 1
                if fail_count >= 3:
                    st.warning(f"⚠ {sec}セクションで3問連続失敗 → スキップします")
                    break
            bar.progress((i + 1) / 80)
            time.sleep(0.15)
        bar.empty()
    return collected

# === Streamlit UI ===
st.title("🩺 国試問題取得ツール + 単元分類 (from CSV)")

uploaded_file = st.file_uploader("問題番号と単元名のCSVをアップロード", type=["csv"])
year = st.text_input("年度を入力（例: 100）")
include_images = st.checkbox("画像も取得する", value=True)

if uploaded_file and year:
    unit_map = load_unit_mapping(uploaded_file)
    col1, col2 = st.columns(2)

    with col1:
        if st.button("A〜Cセクション取得"):
            ac_sections = ['A', 'B', 'C']
            with st.spinner("A〜Cセクションを取得中..."):
                ac_data = scrape_sections(year, ac_sections, unit_map, include_images)
                if ac_data:
                    fn_ac = create_word_doc(ac_data, year, "A-C", include_images)
                    st.success("✅ A〜Cセクション完了！")
                    with open(fn_ac, "rb") as f:
                        st.download_button("A〜CのWordファイルをダウンロード", f, file_name=fn_ac)

    with col2:
        if st.button("D〜Iセクション取得"):
            di_sections = ['D', 'E', 'F', 'G', 'H', 'I']
            with st.spinner("D〜Iセクションを取得中..."):
                di_data = scrape_sections(year, di_sections, unit_map, include_images)
                if di_data:
                    fn_di = create_word_doc(di_data, year, "D-I", include_images)
                    st.success("✅ D〜Iセクション完了！")
                    with open(fn_di, "rb") as f:
                        st.download_button("D〜IのWordファイルをダウンロード", f, file_name=fn_di)
