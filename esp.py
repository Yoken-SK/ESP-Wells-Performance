import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# ==========================================
# 1. KONFIGURASI HALAMAN DASHBOARD
# ==========================================
st.set_page_config(
    page_title="ESP Well Monitoring Dashboard",
    page_icon="⚡",
    layout="wide"
)

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
        
        # Filter: Hanya ambil sheet yang mengandung kata 'monitoring'
        monitoring_sheets = [s for s in sheet_names if 'monitoring' in s.lower()]
        
        if not monitoring_sheets:
            st.sidebar.error("Tidak ditemukan sheet dengan nama 'Monitoring' di file ini!")
        else:
            for sheet in monitoring_sheets:
                # Muat seluruh isi sheet sebagai matriks mentah tanpa header
                df_raw_full = pd.read_excel(uploaded_file, sheet_name=sheet, header=None)
                
                # --- DETEKSI KELOMPOK TABEL SECARA DINAMIS ---
                header_row_idx = None
                for idx, row in df_raw_full.iterrows():
                    row_str = [str(x).strip().lower() for x in row.values if pd.notnull(x)]
                    if 'day' in row_str:
                        header_row_idx = idx
                        break
                
                if header_row_idx is None:
                    continue
                
                # Membaca ulang sheet khusus dari baris tabel data utama ke bawah
                df_table = pd.read_excel(uploaded_file, sheet_name=sheet, skiprows=header_row_idx)
                
                # SANGAT PENTING: Bersihkan nama kolom dari spasi berlebih dan enter (\n)
                df_table.columns = df_table.columns.str.strip().str.replace('\n', ' ').str.replace('  ', ' ')
                
                # Cari kolom utama tanggal
                day_col_candidates = [c for c in df_table.columns if 'day' in c.lower() or 'date' in c.lower()]
                if not day_col_candidates:
                    continue
                target_day_col = day_col_candidates[0]
                
                # Buang baris kosong atau grafik/kurva pompa di bagian bawah tabel
                df_table = df_table.dropna(subset=[target_day_col])
                df_table = df_table[pd.to_datetime(df_table[target_day_col], errors='coerce').notnull()]
                
                if df_table.empty:
                    continue
                
                # --- EKSTRAKSI NAMA SUMUR ---
                well_name_derived = sheet.split(' ')[0].strip()
                for idx, row in df_raw_full.iloc[:header_row_idx].iterrows():
                    row_cells = [str(x).strip() for x in row.values if pd.notnull(x)]
                    for cell_text in row_cells:
                        if 'well name' in cell_text.lower():
                            well_name_derived = row_cells[-1].replace(':', '').strip()
                
                # --- PEMETAAN (MAPPING) KOLOM STRIP KETAT ---
                df_clean = pd.DataFrame()
                df_clean['Date'] = pd.to_datetime(df_table[target_day_col])
                df_clean['Well_Name'] = well_name_derived
                
                # Fungsi pencarian kolom cerdas yang diperbaiki agar mengambil kolom spesifik tunggal
                def find_and_parse_strict(keywords, default_val=0):
                    for c in df_table.columns:
                        # Membersihkan nama kolom untuk pencocokan kata kunci yang pas
                        clean_col_name = c.lower().replace(' ', '')
                        if any(k.replace(' ', '') in clean_col_name for k in keywords):
                            return pd.to_numeric(df_table[c], errors='coerce').fillna(default_val)
                    return pd.Series(default_val, index=df_table.index)
                
                # Ekstraksi Parameter Laju Produksi (Disesuaikan dengan singkatan nama kolom Excel Lapangan)
                df_clean['Oil_Rate_BOPD'] = find_and_parse_strict(['oilbopd', 'bopd'])
                df_clean['Water_Rate_BWPD'] = find_and_parse_strict(['waterbwpd', 'bwpd'])
                df_clean['Water_Cut_Percent'] = find_and_parse_strict(['watercut', 'wc%'])
                df_clean['Gas_Rate_MSCFD'] = find_and_parse_strict(['agfmcfd', 'mcfd', 'gas'])
                
                # Ekstraksi Parameter Tekanan Pompa Downhole & Freq
                df_clean['PI_PSI'] = find_and_parse_strict(['pintake', 'pip'])
                df_clean['PD_PSI'] = find_and_parse_strict(['pdischarge', 'pdp'])
                df_clean['Frequency_Hz'] = find_and_parse_strict(['freqhz', 'hz'], default_val=40)
                
                # Parameter Baseline Tambahan
                df_clean['Motor_Temp_C'] = 95.0
                df_clean['Vibration_G'] = 1.2
                
                all_wells_data[well_name_derived] = df_clean.sort_values('Date')
                
            if all_wells_data:
                st.sidebar.success(f"Berhasil memuat {len(all_wells_data)} Sumur Monitoring!")
            else:
                st.sidebar.error("Gagal mengekstrak data terstruktur dari sheet monitoring.")
                
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
    
    # Grid Utama - KPI Parameter
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Oil Rate", f"{latest_data['Oil_Rate_BOPD']:.1f} BOPD")
    col2.metric("Water Rate", f"{latest_data['Water_Rate_BWPD']:.1f} BWPD")
    col3.metric("Water Cut", f"{latest_data['Water_Cut_Percent']:.1f} %")
    col4.metric("Gas Rate", f"{latest_data['Gas_Rate_MSCFD']:.1f} MCFD")
    
    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Pump Intake (PI)", f"{latest_data['PI_PSI']:.1f} PSI")
    col6.metric("Pump Discharge (PD)", f"{latest_data['PD_PSI']:.1f} PSI")
    col7.metric("VSD Frequency", f"{latest_data['Frequency_Hz']:.1f} Hz")
    col8.metric("Motor Temp (Baseline)", f"{latest_data['Motor_Temp_C']:.1f} °C")
    
    st.markdown("---")
    
    # ==========================================
    # 4. GRAFIK TREN PRODUKSI (DENGAN MULTISELECT OIL, WATER, GAS)
    # ==========================================
    st.subheader("📈 Grafik Tren Produksi Sumur")
    
    # FITUR BARU: Pilihan fleksibel untuk menampilkan Oil, Water, atau Gas
    selected_prod_params = st.multiselect(
        "Pilih Parameter Produksi yang Ingin Ditampilkan pada Grafik:",
        options=["Oil Rate (BOPD)", "Water Rate (BWPD)", "Gas Rate (MCFD)"],
        default=["Oil Rate (BOPD)", "Water Rate (BWPD)"]
    )
    
    if not selected_prod_params:
        st.warning("Silakan pilih minimal satu parameter produksi untuk menampilkan grafik.")
    else:
        fig_prod = go.Figure()
        for prod_param in selected_prod_params:
            if prod_param == "Oil Rate (BOPD)":
                fig_prod.add_trace(go.Scatter(x=df_well['Date'], y=df_well['Oil_Rate_BOPD'], mode='lines+markers', name='Oil Rate (BOPD)', line=dict(color='green', width=2)))
            elif prod_param == "Water Rate (BWPD)":
                fig_prod.add_trace(go.Scatter(x=df_well['Date'], y=df_well['Water_Rate_BWPD'], mode='lines+markers', name='Water Rate (BWPD)', line=dict(color='blue', width=2)))
            elif prod_param == "Gas Rate (MCFD)":
                # Gas menggunakan sumbu kanan (y2) jika angkanya jauh berbeda agar skala tetap ideal
                fig_prod.add_trace(go.Scatter(x=df_well['Date'], y=df_well['Gas_Rate_MSCFD'], mode='lines+markers', name='Gas Rate (MCFD)', line=dict(color='red', dash='dash'), yaxis="y2"))
                fig_prod.update_layout(yaxis2=dict(title="Gas Rate (MCFD)", overlaying="y", side="right"))
                
        fig_prod.update_layout(xaxis_title='Tanggal', yaxis_title='Production Rate (BOPD / BWPD)', hovermode='x unified')
        st.plotly_chart(fig_prod, use_container_width=True)
    
    # ==========================================
    # 5. GRAFIK DOWNHOLE DENGAN FITUR MULTISELECT
    # ==========================================
    st.subheader("⚙️ Visualisasi Tren Downhole & ESP Parameter")
    
    selected_params = st.multiselect(
        "Pilih Parameter Downhole yang Ingin Ditampilkan:",
        options=["Pump Intake Pressure (PI)", "Pump Discharge Pressure (PD)", "VSD Frequency"],
        default=["Pump Intake Pressure (PI)", "Pump Discharge Pressure (PD)"]
    )
    
    if not selected_params:
        st.warning("Silakan centang opsi parameter di atas untuk memuat bagan grafik.")
    else:
        fig_downhole = go.Figure()
        for param in selected_params:
            if param == "Pump Intake Pressure (PI)":
                fig_downhole.add_trace(go.Scatter(x=df_well['Date'], y=df_well['PI_PSI'], mode='lines+markers', name='Intake Press (PSI)', line=dict(color='purple')))
            elif param == "Pump Discharge Pressure (PD)":
