import streamlit as st
import pandas as pd
import io

# 设置页面配置
st.set_page_config(page_title="表格筛选小工具", layout="wide")
st.title("📊 表格数据筛选与合并工具 (统计增强版)")

# --- 侧边栏：设置筛选条件 ---
st.sidebar.header("1. 设置筛选条件")

st.sidebar.subheader("Times (倍数) 范围")
st.sidebar.info("计算公式: Times = (Amount + 10000) / 10000")
min_times = st.sidebar.number_input("Times 最小值", value=0.0, step=0.1, format="%.2f")
max_times = st.sidebar.number_input("Times 最大值", value=1000.0, step=0.1, format="%.2f")

st.sidebar.subheader("LauncherNum (发射数) 范围")
min_launcher = st.sidebar.number_input("LauncherNum 最小值", value=0)
max_launcher = st.sidebar.number_input("LauncherNum 最大值", value=100)

# --- 主界面 ---
st.header("2. 上传数据文件")
uploaded_files = st.file_uploader(
    "请上传 Excel 或 CSV 文件", 
    type=['csv', 'xlsx', 'xls'], 
    accept_multiple_files=True
)

def super_reader(file):
    """全能读取函数"""
    logs = []
    file.seek(0)
    
    # 策略 1: Excel 全表扫描
    try:
        all_sheets = pd.read_excel(file, sheet_name=None)
        best_df = pd.DataFrame()
        max_rows = 0
        for name, sheet_df in all_sheets.items():
            if len(sheet_df) > max_rows:
                max_rows = len(sheet_df)
                best_df = sheet_df
        if not best_df.empty:
            return best_df
    except:
        pass
    
    # 策略 2: CSV
    methods = [
        (pd.read_csv, {}),
        (pd.read_csv, {'encoding': 'gbk'}),
        (pd.read_csv, {'on_bad_lines': 'skip'}),
    ]
    for reader, kwargs in methods:
        file.seek(0)
        try:
            df = reader(file, **kwargs)
            if not df.empty: return df
        except:
            continue
    return None

# --- 核心逻辑: 上传即读取 ---
if uploaded_files:
    all_data_frames = []
    total_files = len(uploaded_files)
    
    # 使用 Spinner 提示用户正在预处理
    with st.spinner(f"正在分析 {total_files} 个文件，请稍候..."):
        for file in uploaded_files:
            df = super_reader(file)
            
            if df is not None and not df.empty:
                # 1. 清洗列名
                df.columns = df.columns.astype(str).str.strip()
                
                # 2. 检查列并计算 Times
                if 'Amount' in df.columns and 'LauncherNum' in df.columns:
                    try:
                        df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce').fillna(0)
                        df['Times'] = (df['Amount'] + 10000) / 10000
                        # 仅保留需要的数据以节省内存（可选，这里先全部保留）
                        all_data_frames.append(df)
                    except:
                        pass

    if all_data_frames:
        # 合并所有数据用于统计
        master_df = pd.concat(all_data_frames, ignore_index=True)
        
        # ==========================================
        # 【新增模块】: 统计信息 (Statistics)
        # ==========================================
        st.markdown("### 📈 数据全貌统计")
        st.info("这里展示的是**所有上传文件**合并后的原始数据统计，供您参考以设置筛选条件。")
        
        stat_col1, stat_col2, stat_col3 = st.columns(3)
        
        # 总行数
        stat_col1.metric("📦 总数据行数", f"{len(master_df):,} 行")
        
        # Times 范围
        t_min = master_df['Times'].min()
        t_max = master_df['Times'].max()
        stat_col2.metric("✖️ Times (倍数) 范围", f"{t_min:.2f} ~ {t_max:.2f}")
        
        # LauncherNum 范围
        l_min = master_df['LauncherNum'].min()
        l_max = master_df['LauncherNum'].max()
        stat_col3.metric("🚀 LauncherNum (发射) 范围", f"{l_min} ~ {l_max}")
        
        st.divider() # 分割线
        
        # ==========================================
        # 【原有模块】: 文件清单
        # ==========================================
        with st.expander(f"📄 已加载文件清单 ({len(uploaded_files)} 个)"):
             for f in uploaded_files:
                 st.text(f"- {f.name}")
        
        # ==========================================
        # 【原有模块】: 筛选按钮与结果
        # ==========================================
        st.markdown("### 🔍 数据筛选")
        if st.button("👉 按左侧条件开始筛选并导出", type="primary"):
            
            # 直接在 master_df 上筛选，速度极快
            filtered_df = master_df[
                (master_df['Times'] >= min_times) & 
                (master_df['Times'] <= max_times) & 
                (master_df['LauncherNum'] >= min_launcher) & 
                (master_df['LauncherNum'] <= max_launcher)
            ]
            
            # 调整列顺序
            cols = list(filtered_df.columns)
            if 'Times' in cols and 'Amount' in cols:
                cols.remove('Times')
                amount_idx = cols.index('Amount')
                cols.insert(amount_idx + 1, 'Times')
                filtered_df = filtered_df[cols]

            # 展示结果
            if not filtered_df.empty:
                st.success(f"✅ 筛选完成！共提取 {len(filtered_df)} 行。")
                
                # 结果统计小栏目
                res_c1, res_c2 = st.columns(2)
                res_c1.metric("筛选后行数", len(filtered_df))
                res_c1.metric("保留比例", f"{len(filtered_df)/len(master_df):.1%}")
                
                # 高度设为 600
                st.dataframe(filtered_df, height=600)
                
                st.download_button(
                    "📥 下载结果 (CSV)",
                    filtered_df.to_csv(index=False).encode('utf-8-sig'),
                    "filtered_result.csv",
                    "text/csv"
                )
            else:
                st.warning("⚠️ 根据当前的筛选条件，结果为空。请参考上方的统计范围调整数值。")
                
    else:
        st.error("❌ 未能从上传的文件中读取到有效数据，请检查文件格式或列名。")