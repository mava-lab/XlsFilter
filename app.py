import streamlit as st
import pandas as pd
import io
import hashlib

# ==========================================
# 配置信息
# ==========================================
APP_TITLE = "Zuma 表格筛选工具"
APP_VERSION = "v1.3.1"
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
        all_sheets = pd.read_excel(file, sheet_name=None)
        max_rows = 0
        for name, sheet_df in all_sheets.items():
            if len(sheet_df) > max_rows:
                max_rows = len(sheet_df)
                df = sheet_df
    except:
        pass
    
    # --- B. 尝试读取 CSV ---
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

    # --- C. 数据清洗 ---
    if df is not None and not df.empty:
        # 清洗列名
        df.columns = df.columns.astype(str).str.strip()
        
        # 删除幽灵索引列 (Unnamed)
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
                    if 'Amount' in df.columns and 'LauncherNum' in df.columns:
                        df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce').fillna(0)
                        df['Times'] = (df['Amount'] + 10000) / 10000
                        all_data_frames.append(df)
                    else:
                        st.warning(f"跳过文件 {file.name}: 缺少 Amount 或 LauncherNum 列")
                except Exception as e:
                    # 修复点：确保这行代码在同一行
                    st.error(f"处理文件 {file.name} 时出错: {e}")

    # --- 阶段二：合并与统计 ---
    if all_data_frames:
        master_df = pd.concat(all_data_frames, ignore_index=True)
        
        # 统计面板
        st.markdown("### 📈 数据全貌统计")
        st.info("这里展示的是所有上传文件合并后的原始数据统计。")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("📦 总数据行数", f"{len(master_df):,} 行")
        c2.metric("✖️ Times 范围", f"{master_df['Times'].min():.2f} ~ {master_df['Times'].max():.2f}")
        c3.metric("🚀 LauncherNum 范围", f"{master_df['LauncherNum'].min()} ~ {master_df['LauncherNum'].max()}")
        
        st.divider()

        # --- 阶段三：筛选与生成 ---
        st.markdown("### 🔍 数据筛选与生成")
        
        if st.button("👉 按左侧条件开始筛选并导出", type="primary"):
            
            # 1. 执行筛选
            filtered_df = master_df[
                (master_df['Times'] >= min_times) & 
                (master_df['Times'] <= max_times) & 
                (master_df['LauncherNum'] >= min_launcher) & 
                (master_df['LauncherNum'] <= max_launcher)
            ].copy()
            
            if not filtered_df.empty:
                with st.spinner('正在生成 MD5 和 Batch ID...'):
                    
                    # A. 生成 MD5
                    def calculate_md5(row):
                        row_str = "".join(row.astype(str).values)
                        return hashlib.md5(row_str.encode('utf-8')).hexdigest()
                    
                    filtered_df['Row_MD5'] = filtered_df.apply(calculate_md5, axis=1)

                    # B. 生成 Batch_ID
                    avg_val = (min_times + max_times) / 2
                    prefix_int = int(round(avg_val * 100))
                    prefix_str = str(prefix_int).zfill(6)
                    
                    ids = []
                    WIDTH_INDEX = 6
                    for i in range(len(filtered_df)):
                        idx_str = str(i + 1).zfill(WIDTH_INDEX)
                        ids.append(f"{prefix_str}{idx_str}")
                    
                    filtered_df['Batch_ID'] = ids

                    # C. 列重排
                    all_cols = list(filtered_df.columns)
                    priority_cols = ['Batch_ID', 'Row_MD5']
                    other_cols = [c for c in all_cols if c not in priority_cols]
                    
                    if 'Times' in other_cols and 'Amount' in other_cols:
                        other_cols.remove('Times')
                        idx_amount = other_cols.index('Amount')
                        other_cols.insert(idx_amount + 1, 'Times')
                    
                    final_order = priority_cols + other_cols
                    filtered_df = filtered_df[final_order]

                # 4. 结果展示
                st.success(f"✅ 处理完成！生成 {len(filtered_df)} 行数据。")
                
                col_res1, col_res2 = st.columns(2)
                col_res1.metric("筛选后行数", len(filtered_df))
                col_res1.metric("保留比例", f"{len(filtered_df)/len(master_df):.2%}")
                
                st.dataframe(filtered_df.head(100), height=400)
                
                st.download_button(
                    label="📥 下载结果 (CSV)",
                    data=filtered_df.to_csv(index=False).encode('utf-8-sig'),
                    file_name=f"Filtered_{min_times}_{max_times}.csv",
                    mime="text/csv"
                )
            else:
                st.warning("⚠️ 筛选结果为空。")
    else:
        st.error("❌ 未读取到有效数据，请检查上传文件格式。")
else:
    st.info("👈 请在左侧栏上传文件以开始使用。")