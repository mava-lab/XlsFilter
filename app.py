import streamlit as st
import pandas as pd
import io

# 设置页面配置
st.set_page_config(page_title="表格筛选小工具", layout="wide")
st.title("📊 表格数据筛选与合并工具 (自动加值版)")

# --- 侧边栏：设置筛选条件 ---
st.sidebar.header("1. 设置筛选条件")
# 提示用户这里是针对处理后的值进行筛选
st.sidebar.info("💡 注意：筛选是基于【Amount + 10000】后的数值进行的")
min_amount = st.sidebar.number_input("Amount (处理后) 最小值", value=10000) # 默认值调大一点比较合理
max_amount = st.sidebar.number_input("Amount (处理后) 最大值", value=50000)
min_launcher = st.sidebar.number_input("LauncherNum 最小值", value=0)
max_launcher = st.sidebar.number_input("LauncherNum 最大值", value=100)

# --- 主界面：上传与处理 ---
st.header("2. 上传数据文件")
uploaded_files = st.file_uploader(
    "请上传 Excel 或 CSV 文件", 
    type=['csv', 'xlsx', 'xls'], 
    accept_multiple_files=True
)

def super_reader(file):
    """
    全能读取函数：扫描所有Sheet，尝试所有格式
    """
    logs = []
    file.seek(0)
    
    # 策略 1: Excel 全表扫描
    try:
        all_sheets = pd.read_excel(file, sheet_name=None)
        best_df = pd.DataFrame()
        best_sheet_name = ""
        max_rows = 0
        for name, sheet_df in all_sheets.items():
            if len(sheet_df) > max_rows:
                max_rows = len(sheet_df)
                best_df = sheet_df
                best_sheet_name = name
        if not best_df.empty:
            return best_df, f"Excel (Sheet: {best_sheet_name})"
    except Exception as e:
        logs.append(f"Excel失败: {str(e)}")
    
    # 策略 2/3/4: CSV 各种尝试
    methods = [
        (pd.read_csv, {}),
        (pd.read_csv, {'encoding': 'gbk'}),
        (pd.read_csv, {'on_bad_lines': 'skip'}),
    ]
    
    for reader, kwargs in methods:
        file.seek(0)
        try:
            df = reader(file, **kwargs)
            if not df.empty: return df, "CSV"
        except:
            continue
            
    return None, "无法识别格式"

if uploaded_files:
    if st.button("开始筛选并合并"):
        all_filtered_data = []
        total_original_rows = 0
        success_count = 0
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, file in enumerate(uploaded_files):
            status_text.text(f"正在处理: {file.name} ...")
            
            # 1. 读取
            df, read_info = super_reader(file)
            
            if df is None or df.empty:
                st.error(f"❌ 跳过 {file.name}: 读取失败")
                continue
            
            # 2. 清洗列名
            df.columns = df.columns.astype(str).str.strip()
            
            if 'Amount' not in df.columns or 'LauncherNum' not in df.columns:
                st.warning(f"⚠️ 跳过 {file.name}: 缺少必要列")
                continue
            
            # -------------------------------------------------------
            # 【关键修改】: 在筛选前，先把 Amount 加上 10000
            # -------------------------------------------------------
            try:
                # 确保是数字类型，防止报错
                df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce').fillna(0)
                # 执行加法
                df['Amount'] = df['Amount'] + 10000
            except Exception as e:
                st.error(f"❌ 文件 {file.name} 的 Amount 列无法进行数学运算: {e}")
                continue
            # -------------------------------------------------------
            
            total_original_rows += len(df)
            
            # 3. 筛选 (此时 df['Amount'] 已经是加过的值了)
            try:
                filtered_df = df[
                    (df['Amount'] >= min_amount) & 
                    (df['Amount'] <= max_amount) & 
                    (df['LauncherNum'] >= min_launcher) & 
                    (df['LauncherNum'] <= max_launcher)
                ]
                
                if not filtered_df.empty:
                    all_filtered_data.append(filtered_df)
                success_count += 1
                
            except Exception as e:
                st.error(f"筛选出错: {e}")

            progress_bar.progress((i + 1) / len(uploaded_files))
            
        status_text.text("处理完成！")
        
        # 4. 结果展示
        if all_filtered_data:
            final_df = pd.concat(all_filtered_data, ignore_index=True)
            st.success(f"✅ 成功！从 {success_count} 个文件中提取数据 (Amount 已全部 +10000)")
            
            c1, c2 = st.columns(2)
            c1.metric("原始总行数", total_original_rows)
            c2.metric("筛选后行数", len(final_df))
            
            st.dataframe(final_df.head(100))
            
            st.download_button(
                "📥 下载结果 (CSV)",
                final_df.to_csv(index=False).encode('utf-8-sig'),
                "filtered_result.csv",
                "text/csv"
            )
        else:
            st.warning("⚠️ 没有数据满足筛选条件。")