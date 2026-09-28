import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import re

# ==========================================
# 1. KONFIGURASI HALAMAN DASHBOARD
# ==========================================
st.set_page_config(page_title="ESP Well Dashboard", layout="wide")

st.title("⚡ ESP Production & Downhole Monitoring Dashboard")
st.markdown("Dashboard otomatis mendeteksi sheet berlabel **'Monitoring'** dari file Excel lapangan Anda.")

# ==========================================
# 2. SIDEBAR UPLOAD EXCEL MULTI-SHEET
# ==========================================
st.sidebar.header("📁 Unggah Laporan Lapangan")
uploaded_file = st.sidebar.file_uploader("Upload File Excel (.xlsx)", type=["xlsx"])

all_wells_data = {}

if uploaded_file is not None:
    try:
        excel_file = pd.ExcelFile(uploaded_file)
        sheet_names = excel_file.sheet_names
        monitoring_sheets = [s for s in sheet_names if 'monitoring' in s.lower()]
        
        if not monitoring_sheets:
            st.sidebar.error("Tidak ditemukan sheet dengan nama 'Monitoring' di file ini!")
        else:
            for sheet in monitoring_sheets:
                df_raw_full = pd.read_excel(uploaded_file, sheet_name=sheet, header=None)
                
                header_row_idx = None
                for idx, row in df_raw_full.iterrows():
                    row_str = [str(x).strip().lower() for x in row.values if pd.notnull(x)]
                    if 'day' in row_str or 'hari' in row_str or 'date' in row_str:
                        header_row_idx = idx
                        break
                
                if header_row_idx is None:
                    continue
                
                df_table = pd.read_excel(uploaded_file, sheet_name=sheet, skiprows=header_row_idx)
                df_table.columns = df_table.columns.str.strip().str.replace('\n', ' ').str.replace('  ', ' ')
                
                day_col_candidates = [c for c in df_table.columns if 'day' in c.lower() or 'date' in c.lower() or 'tgl' in c.lower() or 'time' in c.lower()]
                if not day_col_candidates:
                    continue
                target_day_col = day_col_candidates
                
                # Deteksi Bulan & Tahun Cadangan
                detected_month = 9
                detected_year = 2026
                for idx, row in df_raw_full.iloc[:header_row_idx].iterrows():
                    row_cells = [str(x).strip() for x in row.values if pd.notnull(x)]
                    for cell_text in row_cells:
                        match = re.search(r'([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})', cell_text)
                        if match:
                            try:
                                temp_date = pd.to_datetime(match.group(0), errors='coerce')
                                if pd.notnull(temp_date):
                                    detected_month = temp_date.month
                                    detected_year = temp_date.year
                            except:
                                pass
                
                df_clean = pd.DataFrame()
                
                def find_and_parse_flexible(keywords, default_val=np.nan):
                    for c in df_table.columns:
                        clean_col_name = c.lower().replace(' ', '').replace('\n', '')
                        if any(k.lower().replace(' ', '') in clean_col_name for k in keywords):
                            return pd.to_numeric(df_table[c], errors='coerce')
                    return pd.Series(default_val, index=df_table.index)
                
                # Ekstraksi Parameter
                df_clean['Oil_Rate_BOPD'] = find_and_parse_flexible(['oilbopd', 'bopd', 'oil', 'bop'])
                df_clean['Water_Rate_BWPD'] = find_and_parse_flexible(['waterbwpd', 'bwpd', 'water', 'bwp'])
                df_clean['Water_Cut_Percent'] = find_and_parse_flexible(['watercut', 'wc%', 'wc']).fillna(0)
                df_clean['Gas_Rate_MSCFD'] = find_and_parse_flexible(['agfmcfd', 'mcfd', 'gas', 'agf', 'gascf']).fillna(0)
                
                df_clean['PI_PSI'] = find_and_parse_flexible(['pintake', 'pip', 'intake', 'pintakepsi', 'p.intake'])
                df_clean['PD_PSI'] = find_and_parse_flexible(['pdischarge', 'pdp', 'discharge', 'pdischargepsi', 'p.discharge'])
                df_clean['Frequency_Hz'] = find_and_parse_flexible(['freqhz', 'hz', 'freq', 'vsd'], default_val=40).ffill().bfill().fillna(40)
                
                df_clean['Raw_Day'] = df_table[target_day_col]
                
                # Pembersihan data teks pengganggu
                df_clean = df_clean.dropna(subset=['Oil_Rate_BOPD', 'Water_Rate_BWPD'], how='all')
                
                df_clean['PI_PSI'] = df_clean['PI_PSI'].ffill().bfill().fillna(0)
                df_clean['PD_PSI'] = df_clean['PD_PSI'].ffill().bfill().fillna(0)
                df_clean['Oil_Rate_BOPD'] = df_clean['Oil_Rate_BOPD'].fillna(0)
                df_clean['Water_Rate_BWPD'] = df_clean['Water_Rate_BWPD'].fillna(0)
                
                df_clean['Valid_Check'] = df_clean['Oil_Rate_BOPD'] + df_clean['Water_Rate_BWPD'] + df_clean['PI_PSI']
                df_clean = df_clean[df_clean['Valid_Check'] > 0]
                
                if df_clean.empty:
                    continue
                
                def parse_date_smart(val):
                    val_str = str(val).strip()
                    if val_str.isdigit() and 1 <= int(val_str) <= 31:
                        return pd.to_datetime(f"{detected_year}-{detected_month:02d}-{int(val_str):02d}", errors='coerce')
                    parsed = pd.to_datetime(val, errors='coerce')
                    if pd.notnull(parsed):
                        return parsed
                    return pd.NaT

                df_clean['Date'] = df_clean['Raw_Day'].apply(parse_date_smart)
                df_clean['Date'] = df_clean['Date'].ffill().bfill()
                
                # Deteksi Nama Sumur
                well_name_derived = sheet.replace('Monitoring', '').replace('monitoring', '').strip()
                for idx, row in df_raw_full.iloc[:header_row_idx].iterrows():
                    row_cells = [str(x).strip() for x in row.values if pd.notnull(x)]
                    for cell_text in row_cells:
                        if 'well name' in cell_text.lower() or 'sumur' in cell_text.lower():
                            well_name_derived = row_cells[-1].replace(':', '').strip()
                
                df_clean['Well_Name'] = well_name_derived
                df_clean['Motor_Temp_C'] = 95.0
                df_clean['Vibration_G'] = 1.2
                
                all_wells_data[well_name_derived] = df_clean.sort_values('Date')
                
            if all_wells_data:
                st.sidebar.success(f"Berhasil memuat {len(all_wells_data)} Sumur Monitoring!")
            else:
                st.sidebar.error("Gagal mengekstrak data dari sheet monitoring.")
                
    except Exception as e:
        st.sidebar.error(f"Eror pembacaan file: {e}")

# ==========================================
# 3. INTERFAS / TAMPILAN UTAMA DASHBOARD
# ==========================================
if all_wells_data:
    selected_well = st.sidebar.selectbox("Pilih Sumur ESP:", list(all_wells_data.keys()))
    df_well = all_wells_data[selected_well]
    latest_data = df_well.iloc[-1]
    
    st.subheader(f"📊 Status Terakhir Sumur: {selected_well} ({latest_data['Date'].strftime('%d-%b-%Y')})")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Oil Rate", f"{latest_data['Oil_Rate_BOPD']:.1f} BOPD")
    col2.metric("Water Rate", f"{latest_data['Water_Rate_BWPD']:.1f} BWPD")
    col3.metric("Water Cut", f"{latest_data['Water_Cut_Percent']:.1f} %")
    col4.metric("Gas Rate", f"{latest_data['Gas_Rate_MSCFD']:.1f} MCFD")
    
    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Pump Intake (PI)", f"{latest_data['PI_PSI']:.1f} PSI")
    col6.metric("Pump Discharge (PD)", f"{latest_data['PD_PSI']:.1f} PSI")
    col7.metric("VSD Frequency", f"{latest_data['Frequency_Hz']:.1f} Hz")
    col8.metric("Total Data Points", f"{len(df_well)} Hari")
    
    st.markdown("---")
    
    # Grid Layout untuk Menjajarkan Grafik Produksi dengan Skematik Animasi Pompa Sumur ESP
    col_graph, col_anim = st.columns([2, 1])
    
    with col_graph:
        # ==========================================
        # 4. GRAFIK TREN PRODUKSI
        # ==========================================
        st.subheader("📈 Grafik Tren Produksi Sumur")
        selected_prod = st.multiselect("Pilih Parameter Produksi:", options=["Oil Rate (BOPD)", "Water Rate (BWPD)", "Gas Rate (MCFD)"], default=["Oil Rate (BOPD)", "Water Rate (BWPD)", "Gas Rate (MCFD)"])
        fig_prod = go.Figure()
        if "Oil Rate (BOPD)" in selected_prod: fig_prod.add_trace(go.Scatter(x=df_well['Date'], y=df_well['Oil_Rate_BOPD'], mode='lines+markers', name='Oil Rate (BOPD)', line=dict(color='green', width=2.5)))
        if "Water Rate (BWPD)" in selected_prod: fig_prod.add_trace(go.Scatter(x=df_well['Date'], y=df_well['Water_Rate_BWPD'], mode='lines+markers', name='Water Rate (BWPD)', line=dict(color='blue', width=2)))
        if "Gas Rate (MCFD)" in selected_prod: fig_prod.add_trace(go.Scatter(x=df_well['Date'], y=df_well['Gas_Rate_MSCFD'], mode='lines+markers', name='Gas Rate (MCFD)', yaxis="y2", line=dict(color='red', width=2, dash='dash')))
            
        fig_prod.layout.xaxis.title = "Tanggal"
        fig_prod.layout.yaxis.title = "Liquid Rate (BOPD / BWPD)"
        fig_prod.layout.yaxis.autorange = True
        fig_prod.layout.yaxis2.title = "Gas Rate (MCFD)"
        fig_prod.layout.yaxis2.overlaying = "y"
        fig_prod.layout.yaxis2.side = "right"
        fig_prod.layout.yaxis2.autorange = True
        fig_prod.layout.hovermode = "x unified"
