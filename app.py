import streamlit as st
import pandas as pd
import io
import hashlib

# ==========================================
# 配置信息
# ==========================================
APP_TITLE = "Zuma 表格筛选工具"
APP_VERSION = "v1.3"  # 版本号更新
BUILD_DATE = "2026-01-12"

st.set_page_config(page_title=f"{APP_TITLE} {APP_VERSION}", layout="wide")
st.title(f"📊 {APP_TITLE} (统计增强 + ID生成版)")
st.caption(f"Version: {APP_VERSION} | Build: {BUILD_DATE}")

# ==========================================
# 1. 侧边栏：设置筛选条件
# ==========================================
st.sidebar.header("1. 设置筛选条件")

# Times 筛选
st.sidebar.subheader("Times (倍数) 范围")
st.sidebar.info("计算公式: Times = (Amount + 10000) / 10000")
min_times = st.sidebar.number_input("Times 最小值", value=0.0, step=0.1, format="%.2f")
max_times = st.sidebar.number_input("Times 最大值", value=1000.0, step=0.1, format="%.2f")

# LauncherNum 筛选
st.sidebar.subheader("LauncherNum (发射数) 范围")
min_launcher = st.sidebar.number_input("LauncherNum 最小值", value=0)
max_launcher = st.sidebar.number_input("LauncherNum 最大值", value=100)

# ==========================================
# 2. 全能读取函数 (含幽灵索引清洗)
# ==========================================
def super_reader(file):
    """
    尝试多种方式读取 Excel 或 CSV，并清洗数据。
    """
    df = None
    
    # --- A. 尝试读取 Excel ---
    try:
        # 读取所有 sheet
        all_sheets = pd.read_excel(file, sheet_name=None)
        # 寻找行数最多的 sheet 作为主数据
        max_rows = 0
        for name, sheet_df in all_sheets.items():
            if len(sheet_df) > max_rows:
                max_rows = len(sheet_df)
                df = sheet_df
    except:
        pass
    
    # --- B. 尝试读取 CSV (如果 Excel 失败) ---
    if df is None:
        methods = [
            (pd.read_csv, {}),
            (pd.read_csv, {'encoding': 'utf-8'}),
            (pd.read_csv, {'encoding': 'gbk'}),
            (pd.read_csv, {'on_bad_lines': 'skip'}),
        ]
        
        for reader, kwargs in methods:
            file.seek(0)
            try:
                temp_df = reader(file, **kwargs)
                if not temp_df.empty: 
                    df = temp_df
                    break
            except:
                continue

    # --- C. 数据清洗 (关键步骤) ---
    if df is not None and not df.empty:
        # 1. 清洗列名：转字符串并去除首尾空格
        df.columns = df.columns.astype(str).str.strip()
        
        # 2. 【核心修复】删除幽灵索引列
        # 删除所有包含 "Unnamed" 字样的列 (通常是 pandas 保存 index=True 产生的)
        cols_to_drop = [c for c in df.columns if 'Unnamed' in c]
        if cols_to_drop:
            df.drop(columns=cols_to_drop, inplace=True)
            
    return df

# ==========================================
# 3. 主界面逻辑
# ==========================================
st.header("2. 上传数据文件")
uploaded_files = st.file_uploader(
    "请上传 Excel 或 CSV 文件 (支持多文件)", 
    type=['xlsx', 'xls', 'csv'],
    accept_multiple_files=True
)

if uploaded_files:
    all_data_frames = []
    
    # --- 阶段一：读取与预处理 ---
    with st.spinner(f"正在读取并预处理 {len(uploaded_files)} 个文件..."):
        for file in uploaded_files:
            df = super_reader(file)
            
            if df is not None and not df.empty:
                try:
                    # 检查必要列是否存在
                    if 'Amount' in df.columns and 'LauncherNum' in df.columns:
                        # 计算 Times 列
                        df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce').fillna(0)
                        df['Times'] = (df['Amount'] + 10000) / 10000
                        all_data_frames.append(df)
                    else:
                        st.warning(f"跳过文件 {file.name}: 缺少 Amount 或 LauncherNum 列")
                except Exception as e:
                    st.error(f"处理文件 {file.name} 时