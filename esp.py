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

# ==========================================
# 2. SIDEBAR UPLOAD EXCEL LAPANGAN
# ==========================================
st.sidebar.header("📁 Unggah Laporan Lapangan")
uploaded_file = st.sidebar.file_uploader("Upload File Excel Sumur", type=["xlsx"])

# Inisialisasi variabel penampung data
metadata = {}
df_well = pd.DataFrame()
selected_well = "No Data"

if uploaded_file is not None:
    try:
        # A. MEMBACA METADATA & HISTORY (15 Baris Pertama)
        df_meta = pd.read_excel(uploaded_file, nrows=15, header=None)
        
        for idx, row in df_meta.iterrows():
            key = str(row[0]).strip() if pd.notnull(row[0]) else ""
            val = str(row[1]).replace(':', '').strip() if pd.notnull(row[1]) else ""
            if key and val:
                metadata[key] = val
        
        # Ambil nama sumur dari metadata
        selected_well = metadata.get("Well Name", "Unknown Well")
        
        # B. MEMBACA TABEL DATA UTAMA & DETEKSI HEADER OTOMATIS
        # ==========================================
        # Membaca seluruh sheet tanpa memotong baris terlebih dahulu
        df_raw_full = pd.read_excel(uploaded_file, header=None)
        
        # Mencari di baris mana kata 'Day' berada secara otomatis
        header_row_idx = 14  # Default baseline baris 15 (indeks 14)
        for idx, row in df_raw_full.iterrows():
            row_str = [str(x).strip().lower() for x in row.values]
            if 'day' in row_str:
                header_row_idx = idx
                break
        
        # Membaca ulang data mulai dari baris header yang ditemukan
        df_raw = pd.read_excel(uploaded_file, skiprows=header_row_idx)
        
        # Membersihkan nama kolom dari spasi di awal/akhir dan karakter enter (\n)
        df_raw.columns = df_raw.columns.str.strip().str.replace('\n', ' ')
        
        # Menghapus baris kosong di bawah tabel
        df_raw = df_raw.dropna(subset=[df_raw.columns[0]])
        
        # ==========================================
        # C. PEMETAAN (MAPPING) KOLOM SECARA TELITI
        # ==========================================
        df_clean = pd.DataFrame()
        
        # Cari kolom tanggal (mendeteksi variasi kata 'Day' atau 'Date')
        day_col = [c for c in df_raw.columns if 'day' in c.lower() or 'date' in c.lower()][0]
        df_clean['Date'] = pd.to_datetime(df_raw[day_col], errors='coerce')
        df_clean['Well_Name'] = selected_well
        
        # Cari dan petakan kolom parameter produksi (mencari substring kata kunci)
        bopd_col = [c for c in df_raw.columns if 'bopd' in c.lower()][0]
        bwpd_col = [c for c in df_raw.columns if 'bwpd' in c.lower()][0]
        wc_col = [c for c in df_raw.columns if 'wc' in c.lower() or 'water cut' in c.lower()][0]
        gas_col = [c for c in df_raw.columns if 'agf' in c.lower() or 'mcfd' in c.lower() or 'gas' in c.lower()][0]
        
        df_clean['Oil_Rate_BOPD'] = pd.to_numeric(df_raw[bopd_col], errors='coerce').fillna(0)
        df_clean['Water_Rate_BWPD'] = pd.to_numeric(df_raw[bwpd_col], errors='coerce').fillna(0)
        df_clean['Water_Cut_Percent'] = pd.to_numeric(df_raw[wc_col], errors='coerce').fillna(0)
        df_clean['Gas_Rate_MSCFD'] = pd.to_numeric(df_raw[gas_col], errors='coerce').fillna(0)
        
        # Cari dan petakan kolom parameter downhole tekanan
        pi_col = [c for c in df_raw.columns if 'intake' in c.lower() or 'pip' in c.lower() or 'p intake' in c.lower()][0]
        pd_col = [c for c in df_raw.columns if 'discharge' in c.lower() or 'p discharge' in c.lower()][0]
        freq_col = [c for c in df_raw.columns if 'freq' in c.lower() or 'hz' in c.lower()][0]
        
        df_clean['PI_PSI'] = pd.to_numeric(df_raw[pi_col], errors='coerce').fillna(0)
        df_clean['PD_PSI'] = pd.to_numeric(df_raw[pd_col], errors='coerce').fillna(0)
        df_clean['Frequency_Hz'] = pd.to_numeric(df_raw[freq_col], errors='coerce').fillna(40)
        
        # Nilai acuan default untuk parameter pendukung
        df_clean['Motor_Temp_C'] = 95.0
        df_clean['Vibration_G'] = 1.2
        
        df_well = df_clean.sort_values('Date')
        st.sidebar.success(f"Berhasil memuat data Sumur: {selected_well}")
        
    except Exception as e:
        st.sidebar.error(f"Gagal membaca format file: {e}")

# ==========================================
# 3. TAMPILAN INFORMASI & HISTORY SUMUR (HEADER)
# ==========================================
if not df_well.empty:
    latest_data = df_well.iloc[-1]
    
    # Tampilkan Riwayat Commissioning / Start Up dari Atas Excel
    st.subheader(f"📋 Resume & Riwayat Sumur: {selected_well}")
    
    meta_col1, meta_col2 = st.columns(2)
    with meta_col1:
        st.markdown(f"**Pump Type:** {metadata.get('Pump Type', '-')}")
        st.markdown(f"**Pump Intake Depth:** {metadata.get('Pump Intake', '-')}")
        st.markdown(f"**Status Kendali Pompa:** {metadata.get('Pump Status', '-')}")
    with meta_col2:
        st.markdown(f"**Initial Commissioning:** {metadata.get('Date of Commissioning/start up', '-')}")
        st.markdown(f"**Last Well Service (4th):** :orange[{metadata.get('Date of Commissioning/start up after 4th well service', '-')}]")
        
    st.markdown("---")
    
    # ==========================================
    # 4. TAMPILAN KPI METRICS TERKINI
    # ==========================================
    st.subheader(f"📊 Status Data Terakhir ({latest_data['Date'].strftime('%d-%b-%Y')})")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Oil Rate", f"{latest_data['Oil_Rate_BOPD']} BOPD")
    col2.metric("Water Rate", f"{latest_data['Water_Rate_BWPD']} BWPD")
    col3.metric("Water Cut", f"{latest_data['Water_Cut_Percent']} %")
    col4.metric("Gas Rate", f"{latest_data['Gas_Rate_MSCFD']} MCFD")
    
    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Pump Intake (PI)", f"{latest_data['PI_PSI']} PSI")
    col6.metric("Pump Discharge (PD)", f"{latest_data['PD_PSI']} PSI")
    col7.metric("VSD Frequency", f"{latest_data['Frequency_Hz']} Hz")
    col8.metric("Operating Hours", f"{df_raw.iloc[-1].get('Hour\nProd.', 24)} Jam")
    
    st.markdown("---")
    
    # ==========================================
    # 5. GRAFIK TREN PRODUKSI
    # ==========================================
    st.subheader("📈 Grafik Tren Produksi Sumur")
    
    fig_prod = go.Figure()
    fig_prod.add_trace(go.Scatter(x=df_well['Date'], y=df_well['Oil_Rate_BOPD'], mode='lines+markers', name='Oil Rate (BOPD)', line=dict(color='green', width=2)))
    fig_prod.add_trace(go.Scatter(x=df_well['Date'], y=df_well['Water_Rate_BWPD'], mode='lines', name='Water Rate (BWPD)', line=dict(color='blue', width=2)))
    
    fig_prod.update_layout(xaxis_title='Tanggal', yaxis_title='Rate (BFPD / BOPD)', hovermode='x unified')
    st.plotly_chart(fig_prod, use_container_width=True)
    
    # ==========================================
    # 6. GRAFIK DOWNHOLE PARAMETER (INTEGRASI PI & PD)
    # ==========================================
    st.subheader("⚙️ Grafik Tekanan Pompa (PI & PD)")
    
    # Filter parameter downhole pilihan user
    selected_params = st.multiselect(
        "Pilih Downhole Parameter:",
        options=["Pump Intake Pressure (PI)", "Pump Discharge Pressure (PD)", "VSD Frequency"],
        default=["Pump Intake Pressure (PI)", "Pump Discharge Pressure (PD)"]
    )
    
    fig_downhole = go.Figure()
    if "Pump Intake Pressure (PI)" in selected_params:
        fig_downhole.add_trace(go.Scatter(x=df_well['Date'], y=df_well['PI_PSI'], name='Intake Press (PSI)', line=dict(color='purple')))
    if "Pump Discharge Pressure (PD)" in selected_params:
        fig_downhole.add_trace(go.Scatter(x=df_well['Date'], y=df_well['PD_PSI'], name='Discharge Press (PSI)', line=dict(color='teal')))
    if "VSD Frequency" in selected_params:
        fig_downhole.add_trace(go.Scatter(x=df_well['Date'], y=df_well['Frequency_Hz'], name='Freq (Hz)', line=dict(color='darkblue'), yaxis="y2"))
        fig_downhole.update_layout(yaxis2=dict(title="Frequency (Hz)", overlaying="y", side="right"))
        
    fig_downhole.update_layout(xaxis_title='Tanggal', yaxis_title='Pressure (PSI)', hovermode='x unified')
    st.plotly_chart(fig_downhole, use_container_width=True)

else:
    st.info("Silakan unggah berkas excel laporan harian sumur ESP melalui sidebar untuk melihat visualisasi data.")
