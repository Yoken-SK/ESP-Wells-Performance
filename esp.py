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
        
        # B. MEMBACA TABEL DATA UTAMA (Mulai dari baris ke-16 / indeks 15)
        # Menyesuaikan dengan baris bertingkat (multi-header)
        df_raw = pd.read_excel(uploaded_file, skiprows=14)
        
        # Membersihkan kolom kosong atau baris penutup jika ada
        df_raw = df_raw.dropna(subset=['Day'])
        
        # C. PEMETAAN (MAPPING) KOLOM SESUAI FORMAT GAMBAR LAPANGAN
        df_clean = pd.DataFrame()
        df_clean['Date'] = pd.to_datetime(df_raw['Day'], errors='coerce')
        df_clean['Well_Name'] = selected_well
        
        # Parameter Produksi
        # Mengatasi kolom 'error'/'#VALUE!' dengan mengubah ke numerik (jika error jadi NaN)
        df_clean['Oil_Rate_BOPD'] = pd.to_numeric(df_raw['BOPD'], errors='coerce').fillna(0)
        df_clean['Water_Rate_BWPD'] = pd.to_numeric(df_raw['BWPD'], errors='coerce').fillna(0)
        df_clean['Water_Cut_Percent'] = pd.to_numeric(df_raw['WC\n%'], errors='coerce').fillna(0)
        df_clean['Gas_Rate_MSCFD'] = pd.to_numeric(df_raw['AGF\nMCFD'], errors='coerce').fillna(0)
        
        # Parameter Downhole & ESP
        df_clean['PI_PSI'] = pd.to_numeric(df_raw['P intake\npsi'], errors='coerce').fillna(0)
        df_clean['PD_PSI'] = pd.to_numeric(df_raw['P discharge\npsi'], errors='coerce').fillna(0)
        df_clean['Frequency_Hz'] = pd.to_numeric(df_raw['Freq\nHz'], errors='coerce').fillna(40)
        
        # Kolom opsional tambahan (Bisa diaktifkan jika data terisi)
        df_clean['Motor_Temp_C'] = 90.0 # Nilai asumsi baseline karena di gambar kolom temp terpotong/kosong
        df_clean['Vibration_G'] = 1.0   # Nilai asumsi baseline
        
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
