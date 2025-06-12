import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import time
from io import BytesIO
from docx import Document
from docx.shared import Inches

# ページ取得関数
def get_page_text(url, get_images=True):
    try:
        resp = requests.get(url)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, 'html.parser')
        category = soup.find('span', class_='button-small-line')
        problem = soup.find('div', class_='quiz-body mb-64')
        choices = [f"{c.find('span', class_='choice-header').text.strip()} {c.find_all('span')[1].text.strip()}"
                   for c in soup.find_all('div', class_='box-select')]
        h4s = soup.find_all('h4')
        ans = h4s[0].text.strip() if h4s else '解答なし'
        qid = re.search(r'([0-9]{3}[A-Za-z][0-9]+)', h4s[1].text).group(1) if len(h4s) >=2 else '問題番号なし'
        expl = soup.find('div', class_='explanation').text.strip() if soup.find('div', class_='explanation') else '解説なし'
        imgs = []
        if get_images:
            for d in soup.find_all('div', class_='box-quiz-image mb-32'):
                img = d.find('img')
                if img and img.get('src'):
                    imgs.append(img['src'].replace('thumb_', ''))
        return {
            "category": category.text.strip() if category else '分野名なし',
            "problem": problem.text.strip() if problem else '問題文なし',
            "choices": choices,
            "answer": ans,
            "question_id": qid,
            "explanation": expl,
            "images": imgs
        }
    except:
        return None

# Word生成関数
def create_word_doc(pages, year, include_images=True):
    doc = Document()
    doc.add_heading(f'{year}年 医師国家試験問題', 0)
    doc.add_paragraph(f"取得問題数: {len(pages)}問")
    for i, p in enumerate(pages, 1):
        doc.add_heading(f"問題{ i } {p['question_id']}", level=2)
        doc.add_paragraph(f"分野: {p['category']}")
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
    fn = f"{year}_medu4.docx"
    doc.save(fn)
    return fn

# UI
st.title("🩺 国試問題取得ツール")

year = st.text_input("年度を入力してください（例: 100）")
include_images = st.checkbox("画像も取得する", value=True)

if st.button("開始") and year:
    sections = [chr(ord('A') + i) for i in range(9)]  # A〜I
    all_pages = []
    with st.spinner("問題を収集中…"):
        for sec in sections:
            st.write(f"→ セクション {year}{sec} の取得開始")
            fail_count = 0
            for num in range(1, 81):  # 1〜80
                qid = f"{year}{sec}{num}"
                url = f"https://medu4.com/{qid}"
                data = get_page_text(url, get_images=include_images)
                if data:
                    all_pages.append(data)
                    st.write(f"✅ {qid} を取得")
                    fail_count = 0  # 成功したらリセット
                else:
                    st.write(f"❌ {qid} が見つかりません")
                    fail_count += 1
                    if fail_count >= 3:
                        st.write(f"⚠ 3問連続失敗 → セクション {sec} をスキップします")
                        break
                time.sleep(0.2)
    filename = create_word_doc(all_pages, year, include_images)
    st.success("✅ 完了しました！")
    with open(filename, "rb") as f:
        st.download_button("Wordファイルをダウンロード", f, file_name=filename)
