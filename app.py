import streamlit as st
import pandas as pd
import io

# 设置页面配置
st.set_page_config(page_title="表格筛选小工具", layout="wide")
st.title("📊 表格数据筛选与合并工具 (全能扫描版)")

# --- 侧边栏：设置筛选条件 ---
st.sidebar.header("1. 设置筛选条件")
min_amount = st.sidebar.number_input("Amount 最小值", value=0)
max_amount = st.sidebar.number_input("Amount 最大值", value=10000)
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
    全能读取函数：扫描所有Sheet，尝试所有格式，只返回有数据的那个
    """
    logs = []
    file.seek(0)
    
    # --- 策略 1: Excel 全表扫描 (最可能的情况) ---
    try:
        # sheet_name=None 表示读取所有工作表
        all_sheets = pd.read_excel(file, sheet_name=None)
        
        best_df = pd.DataFrame()
        best_sheet_name = ""
        max_rows = 0
        
        # 遍历所有 Sheet，找行数最多的那个
        for name, sheet_df in all_sheets.items():
            if len(sheet_df) > max_rows:
                max_rows = len(sheet_df)
                best_df = sheet_df
                best_sheet_name = name
        
        if not best_df.empty:
            return best_df, f"Excel (工作表: {best_sheet_name})"
        else:
            logs.append("Excel读取成功但所有工作表皆为空")
            
    except Exception as e:
        logs.append(f"Excel读取失败: {str(e)}")
    
    # --- 策略 2: CSV 标准读取 ---
    file.seek(0)
    try:
        df = pd.read_csv(file)
        if not df.empty: return df, "CSV-标准"
    except Exception as e:
        logs.append(f"CSV标准失败: {str(e)}")
        
    # --- 策略 3: CSV GBK读取 (中文乱码专用) ---
    file.seek(0)
    try:
        df = pd.read_csv(file, encoding='gbk')
        if not df.empty: return df, "CSV-GBK"
    except Exception as e:
        logs.append(f"CSV-GBK失败: {str(e)}")

    # --- 策略 4: CSV 强行读取 ---
    file.seek(0)
    try:
        df = pd.read_csv(file, on_bad_lines='skip') # pandas新版用 on_bad_lines
        if not df.empty: return df, "CSV-强行"
    except:
        # 兼容旧版 pandas
        try:
            file.seek(0)
            df = pd.read_csv(file, error_bad_lines=False)
            if not df.empty: return df, "CSV-强行(旧版)"
        except Exception as e:
            logs.append(f"CSV强行失败: {str(e)}")
            
    return None, " | ".join(logs)

if uploaded_files:
    if st.button("开始筛选并合并"):
        all_filtered_data = []
        total_original_rows = 0
        success_count = 0
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, file in enumerate(uploaded_files):
            status_text.text(f"正在深度分析: {file.name} ...")
            
            # --- 调用全能读取 ---
            df, read_info = super_reader(file)
            
            if df is None or df.empty:
                st.error(f"❌ 文件 {file.name} 无法读取有效数据。日志: {read_info}")
                continue
            
            # --- 清洗列名 ---
            # 强制全部转为字符并去空格
            df.columns = df.columns.astype(str).str.strip()
            
            # --- 检查关键列 ---
            if 'Amount' not in df.columns or 'LauncherNum' not in df.columns:
                st.warning(f"⚠️ 跳过 {file.name} ({read_info}): 找不到 Amount 或 LauncherNum 列。现有列: {list(df.columns)}")
                continue
            
            total_original_rows += len(df)
            
            # --- 筛选 ---
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
                st.error(f"筛选 {file.name} 出错: {e}")

            progress_bar.progress((i + 1) / len(uploaded_files))
            
        status_text.text("处理完成！")
        
        # --- 结果展示 ---
        if all_filtered_data:
            final_df = pd.concat(all_filtered_data, ignore_index=True)
            st.success(f"✅ 成功！从 {success_count} 个文件中提取了数据。")
            
            # 统计
            c1, c2, c3 = st.columns(3)
            c1.metric("原始总行数", total_original_rows)
            c2.metric("筛选后行数", len(final_df))
            c3.metric("筛选率", f"{len(final_df)/total_original_rows:.1%}" if total_original_rows else "0%")
            
            st.dataframe(final_df.head(100))
            
            st.download_button(
                "📥 下载最终结果 (CSV)",
                final_df.to_csv(index=False).encode('utf-8-sig'),
                "filtered_result.csv",
                "text/csv"
            )
        else:
            if success_count > 0:
                st.warning("⚠️ 读取了数据，但根据您的筛选条件（Amount/LauncherNum范围），没有保留下任何一行。")
            else:
                st.error("⚠️ 没有成功读取任何数据，请检查文件内容是否真的为空。")