import streamlit as st
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io
import os
import tempfile 

# --- Helper Functions ---

# 1. EPUB to Text 
def epub_to_text(file_content):
    """从EPUB文件内容中提取纯文本"""
    tmp_path = ""
    try:
        # 创建一个带有 .epub 后缀的命名临时文件
        # delete=False 确保文件在 with 块结束后不会被删除，以便 ebooklib 可以访问它
        with tempfile.NamedTemporaryFile(delete=False, suffix=".epub") as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name # 获取临时文件的路径

        # 使用临时文件的路径来读取EPUB
        book = epub.read_epub(tmp_path)
        
        text_content = []
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                soup = BeautifulSoup(item.get_content(), 'html.parser')
                text_content.append(soup.get_text())
        return "\n".join(text_content)
    
    except Exception as e:
        return f"处理EPUB文件时出错: {e}"
        
    finally:
        # 清理工作：无论是否成功，都删除临时文件
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

# 2. PDF to Text (for text-based PDFs)
def pdf_to_text(file_content):
    """从基于文本的PDF文件中提取文本和目录"""
    try:
        doc = fitz.open(stream=file_content, filetype="pdf")
        
        toc = doc.get_toc()
        toc_text = "目录:\n"
        if not toc:
            toc_text += "未找到目录。\n"
        else:
            for level, title, page in toc:
                toc_text += f"{'  ' * (level - 1)}- {title} (页码 {page})\n"
        
        full_text = ""
        for page in doc:
            full_text += page.get_text()
            
        return full_text, toc_text
    except Exception as e:
        return f"处理PDF文件时出错: {e}", ""

# 3. PDF OCR (for scanned PDFs)
def pdf_ocr(file_content, progress_bar):
    """对扫描的PDF文件进行OCR处理，并提取目录"""
    try:
        doc = fitz.open(stream=file_content, filetype="pdf")
        
        toc = doc.get_toc()
        toc_text = "目录:\n"
        if not toc:
            toc_text += "未找到目录。\n"
        else:
            for level, title, page in toc:
                toc_text += f"{'  ' * (level - 1)}- {title} (页码 {page})\n"
        
        full_text = ""
        total_pages = len(doc)
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=300)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            page_text = pytesseract.image_to_string(img, lang='chi_sim+eng')
            full_text += f"\n--- Page {i+1} ---\n" + page_text
            progress_bar.progress((i + 1) / total_pages)
            
        return full_text, toc_text
    except Exception as e:
        return f"OCR处理PDF时出错: {e}", ""


# --- Streamlit App ---

st.set_page_config(page_title="文件转换器 Pro", layout="wide")

st.title("📚 文件转换器 Pro")
st.markdown("一个多功能文件转换工具，支持 EPUB、PDF 转 TXT")

if 'processed_text' not in st.session_state:
    st.session_state.processed_text = None
if 'file_name' not in st.session_state:
    st.session_state.file_name = None
if 'toc' not in st.session_state:
    st.session_state.toc = None
if 'secondary_text' not in st.session_state:
    st.session_state.secondary_text = None

uploaded_file = st.file_uploader("上传你的 EPUB 或 PDF 文件", type=["epub", "pdf"])

if uploaded_file is not None:
    file_content = uploaded_file.getvalue()
    file_name_base = os.path.splitext(uploaded_file.name)[0]

    if uploaded_file.name.endswith('.epub'):
        st.header("EPUB 处理选项")
        if st.button("将 EPUB 转换为 TXT"):
            with st.spinner("正在处理 EPUB 文件..."):
                result = epub_to_text(file_content)
                st.session_state.processed_text = result
                st.session_state.file_name = f"{file_name_base}_epub.txt"
                st.session_state.toc = None
                st.session_state.secondary_text = None

    elif uploaded_file.name.endswith('.pdf'):
        st.header("PDF 处理选项")
        pdf_mode = st.radio(
            "选择PDF处理模式:",
            ('提取文本 (适用于文本型PDF)', 'OCR识别 (适用于扫描型PDF)')
        )

        if pdf_mode == '提取文本 (适用于文本型PDF)':
            if st.button("开始提取文本"):
                with st.spinner("正在提取PDF文本..."):
                    text, toc = pdf_to_text(file_content)
                    st.session_state.processed_text = text
                    st.session_state.toc = toc
                    st.session_state.file_name = f"{file_name_base}_text.txt"
                    st.session_state.secondary_text = None
        
        else:
            st.info("OCR过程可能需要一些时间，特别是对于多页文档。")
            output_txt_additionally = st.checkbox("同时输出一份纯文本提取的TXT文件 (作为对比或备用)")

            if st.button("开始OCR识别"):
                progress_bar = st.progress(0)
                with st.spinner("正在进行OCR识别，请稍候..."):
                    ocr_text, toc = pdf_ocr(file_content, progress_bar)
                    st.session_state.processed_text = ocr_text
                    st.session_state.toc = toc
                    st.session_state.file_name = f"{file_name_base}_ocr.txt"

                    if output_txt_additionally:
                        text_only, _ = pdf_to_text(file_content)
                        st.session_state.secondary_text = text_only
                    else:
                        st.session_state.secondary_text = None
                progress_bar.empty()
    else:
        st.warning("上传的文件类型无法识别。请上传 .epub 或 .pdf 文件。")

if st.session_state.processed_text:
    st.success("处理完成！")
    
    if st.session_state.toc:
        with st.expander("查看提取的目录", expanded=False):
            st.text(st.session_state.toc)

    st.subheader("处理结果预览")
    st.text_area("内容", st.session_state.processed_text, height=400)
    st.download_button(
        label="下载主结果文件 (.txt)",
        data=st.session_state.processed_text.encode('utf-8'),
        file_name=st.session_state.file_name,
        mime='text/plain',
    )
    
    if st.session_state.secondary_text:
        st.subheader("额外的纯文本提取结果")
        st.text_area("内容 (纯文本提取)", st.session_state.secondary_text, height=200)
        st.download_button(
            label="下载纯文本提取文件 (.txt)",
            data=st.session_state.secondary_text.encode('utf-8'),
            file_name=f"{os.path.splitext(st.session_state.file_name)[0]}_extra_text.txt",
            mime='text/plain',
        )