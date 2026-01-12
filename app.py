import streamlit as st
import pandas as pd
import io
import hashlib
import zipfile  # 新增：用于打包多个文件

# ==========================================
# 配置信息
# ==========================================
APP_TITLE = "Zuma 表格筛选工具"
APP_VERSION = "v2.0 (Batch Process)"
BUILD_DATE = "2026-01-12"

st.set_page_config(page_title=f"{APP_TITLE} {APP_VERSION}", layout="wide")
st.title(f"📊 {APP_TITLE} (批量拆分版)")
st.caption(f"Version: {APP_VERSION} | Build: {BUILD_DATE}")

# ==========================================
# 0. Session State 初始化 (用于管理多组筛选条件)
# ==========================================
if 'filter_rules' not in st.session_state:
    # 默认初始化一组规则
    st.session_state.filter_rules = [
        {"id": 1, "min_t": 0.0, "max_t": 1000.0, "min_l": 0, "max_l": 100}
    ]

# 辅助函数：添加新规则
def add_rule():
    new_id = len(st.session_state.filter_rules) + 1
    st.session_state.filter_rules.append(
        {"id": new_id, "min_t": 0.0, "max_t": 100.0, "min_l": 0, "max_l": 100}
    )

# 辅助函数：删除最后一条规则
def remove_rule():
    if len(st.session_state.filter_rules) > 1:
        st.session_state.filter_rules.pop()

# ==========================================
# 1. 侧边栏：批量筛选配置
# ==========================================
st.sidebar.header("1. 批量筛选配置")
st.sidebar.info("💡 你可以添加多组条件，程序将一次性拆分出对应的多个文件。")

# 规则管理按钮
col_btn1, col_btn2 = st.sidebar.columns(2)
col_btn1.button("➕ 增加拆分规则", on_click=add_rule, type="primary")
col_btn2.button("➖ 删除最后一条", on_click=remove_rule)

st.sidebar.markdown("---")

# 动态渲染所有规则的输入框
# 注意：在循环中生成组件必须指定唯一的 key
for i, rule in enumerate(st.session_state.filter_rules):
    idx = i + 1
    with st.sidebar.expander(f"📂 文件 {idx} 配置 (Rule {idx})", expanded=True):
        c1, c2 = st.columns(2)
        rule['min_t'] = c1.number_input(f"Times Min", value=rule['min_t'], step=0.1, key=f"t_min_{idx}")
        rule['max_t'] = c2.number_input(f"Times Max", value=rule['max_t'], step=0.1, key=f"t_max_{idx}")
        
        c3, c4 = st.columns(2)
        rule['min_l'] = c3.number_input(f"Launch Min", value=rule['min_l'], step=1, key=f"l_min_{idx}")
        rule['max_l'] = c4.number_input(f"Launch Max", value=rule['max_l'], step=1, key=f"l_max_{idx}")

# ==========================================
# 2. 核心逻辑：读取与处理 (带缓存 + 清洗)
# ==========================================
def super_reader(file):
    """底层读取逻辑"""
    df = None
    try:
        all_sheets = pd.read_excel(file, sheet_name=None)
        max_rows = 0
        for name, sheet_df in all_sheets.items():
            if len(sheet_df) > max_rows:
                max_rows = len(sheet_df)
                df = sheet_df
    except:
        pass
    
    if df is None:
        methods = [(pd.read_csv, {}), (pd.read_csv, {'encoding': 'utf-8'}), 
                   (pd.read_csv, {'encoding': 'gbk'}), (pd.read_csv, {'on_bad_lines': 'skip'})]
        for reader, kwargs in methods:
            file.seek(0)
            try:
                temp_df = reader(file, **kwargs)
                if not temp_df.empty: 
                    df = temp_df
                    break
            except: continue

    if df is not None and not df.empty:
        df.columns = df.columns.astype(str).str.strip()
        cols_to_drop = [c for c in df.columns if 'Unnamed' in c or c == '']
        if cols_to_drop: df.drop(columns=cols_to_drop, inplace=True)
            
    return df

@st.cache_data(show_spinner=False) 
def load_and_merge_files(files):
    """读取合并文件 (缓存加速)"""
    all_dfs = []
    for file in files:
        file.seek(0)
        df = super_reader(file)
        if df is not None and not df.empty:
            try:
                if 'Amount' in df.columns and 'LauncherNum' in df.columns:
                    df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce').fillna(0)
                    df['Times'] = (df['Amount'] + 10000) / 10000
                    all_dfs.append(df)
            except:
                continue     
    if all_dfs:
        return pd.concat(all_dfs, ignore_index=True)
    return pd.DataFrame()

# ==========================================
# 3. 主界面逻辑
# ==========================================
st.header("2. 上传数据文件")
uploaded_files = st.file_uploader(
    "请上传 Excel 或 CSV 文件", 
    type=['xlsx', 'xls', 'csv'],
    accept_multiple_files=True
)

if uploaded_files:
    # 读取过程 (带缓存)
    with st.spinner("正在读取或从缓存加载数据..."):
        master_df = load_and_merge_files(uploaded_files)

    if not master_df.empty:
        # --- 统计面板 ---
        st.markdown("### 📈 数据全貌统计")
        c1, c2, c3 = st.columns(3)
        c1.metric("📦 总数据行数", f"{len(master_df):,} 行")
        c2.metric("✖️ Times 范围", f"{master_df['Times'].min():.2f} ~ {master_df['Times'].max():.2f}")
        c3.metric("🚀 LauncherNum 范围", f"{master_df['LauncherNum'].min()} ~ {master_df['LauncherNum'].max()}")
        st.divider()

        # --- 批量处理逻辑 ---
        st.markdown(f"### 🚀 批量拆分处理 (当前共 {len(st.session_state.filter_rules)} 个任务)")
        
        if st.button("👉 开始批量拆分并打包下载", type="primary"):
            
            results_buffer = io.BytesIO() # 用于存放 ZIP 文件的内存
            processed_logs = [] # 用于记录处理结果日志
            total_files_generated = 0

            # 创建 ZIP 文件
            with zipfile.ZipFile(results_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                
                progress_bar = st.progress(0)
                
                # 遍历所有规则
                for i, rule in enumerate(st.session_state.filter_rules):
                    idx = i + 1
                    t_min, t_max = rule['min_t'], rule['max_t']
                    l_min, l_max = rule['min_l'], rule['max_l']
                    
                    # 1. 筛选
                    filtered_df = master_df[
                        (master_df['Times'] >= t_min) & 
                        (master_df['Times'] <= t_max) & 
                        (master_df['LauncherNum'] >= l_min) & 
                        (master_df['LauncherNum'] <= l_max)
                    ].copy()
                    
                    file_name = f"File{idx}_Times_{t_min}-{t_max}_L_{l_min}-{l_max}.csv"
                    
                    if not filtered_df.empty:
                        # 2. 生成 MD5
                        filtered_df['Row_MD5'] = filtered_df.apply(
                            lambda row: hashlib.md5("".join(row.astype(str).values).encode('utf-8')).hexdigest(), axis=1
                        )

                        # 3. 生成 Batch_ID (基于当前规则的 Min/Max)
                        avg_val = (t_min + t_max) / 2
                        prefix_str = str(int(round(avg_val * 100))).zfill(6)
                        filtered_df['Batch_ID'] = [f"{prefix_str}{str(k+1).zfill(6)}" for k in range(len(filtered_df))]

                        # 4. 列重排
                        cols = list(filtered_df.columns)
                        priority = ['Batch_ID', 'Row_MD5']
                        others = [c for c in cols if c not in priority]
                        if 'Times' in others and 'Amount' in others:
                            others.remove('Times')
                            others.insert(others.index('Amount') + 1, 'Times')
                        
                        final_df = filtered_df[priority + others]
                        
                        # 5. 写入 ZIP
                        csv_data = final_df.to_csv(index=False).encode('utf-8-sig')
                        zf.writestr(file_name, csv_data)
                        
                        processed_logs.append({"文件": file_name, "状态": "✅ 成功", "行数": len(final_df)})
                        total_files_generated += 1
                    else:
                        processed_logs.append({"文件": file_name, "状态": "⚠️ 跳过 (无数据)", "行数": 0})
                    
                    progress_bar.progress((i + 1) / len(st.session_state.filter_rules))

            # 结果展示
            if total_files_generated > 0:
                st.success(f"🎉 处理完成！共生成 {total_files_generated} 个文件。")
                
                # 展示日志表格
                st.table(pd.DataFrame(processed_logs))
                
                # 提供 ZIP 下载
                st.download_button(
                    label="📦 点击下载所有文件 (ZIP压缩包)",
                    data=results_buffer.getvalue(),
                    file_name=f"Batch_Processed_{BUILD_DATE}.zip",
                    mime="application/zip"
                )
            else:
                st.error("所有筛选条件的筛选结果均为空，未生成任何文件。")
                st.table(pd.DataFrame(processed_logs))

    else:
        st.error("未能读取到有效数据。")
else:
    st.info("👈 请上传文件。")