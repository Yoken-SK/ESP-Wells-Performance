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

# Kamus besar untuk menampung data matang dari semua sumur/sheet yang valid
all_wells_data = {}

if uploaded_file is not None:
    try:
        # Membaca seluruh nama sheet yang ada di dalam berkas Excel
        excel_file = pd.ExcelFile(uploaded_file)
        sheet_names = excel_file.sheet_names
        
        # Filter: Hanya ambil sheet yang mengandung kata 'monitoring' (tidak sensitif huruf besar/kecil)
        monitoring_sheets = [s for s in sheet_names if 'monitoring' in s.lower()]
        
        if not monitoring_sheets:
            st.sidebar.error("Tidak ditemukan sheet dengan nama 'Monitoring' di file ini!")
        else:
            # Memproses setiap sheet monitoring yang lolos filter
            for sheet in monitoring_sheets:
                # Muat seluruh isi sheet sebagai matriks mentah tanpa header terlebih dahulu
                df_raw_full = pd.read_excel(uploaded_file, sheet_name=sheet, header=None)
                
                # --- DETEKSI KELOMPOK TABEL SECARA DINAMIS ---
                # Mencari letak baris yang berisi kata kunci kolom tanggal 'day'
                header_row_idx = None
                for idx, row in df_raw_full.iterrows():
                    row_str = [str(x).strip().lower() for x in row.values if pd.notnull(x)]
                    if 'day' in row_str:
                        header_row_idx = idx
                        break
                
                # Jika baris tabel penunjuk tidak ditemukan, lewati sheet ini
                if header_row_idx is None:
                    continue
                
                # Membaca ulang sheet khusus dari baris tabel data utama ke bawah
                df_table = pd.read_excel(uploaded_file, sheet_name=sheet, skiprows=header_row_idx)
                
                # Bersihkan nama kolom dari spasi berlebih dan karakter enter (\n) akibat merged cells
                df_table.columns = df_table.columns.str.strip().str.replace('\n', ' ').str.replace('  ', ' ')
                
                # Cari kolom utama tanggal untuk validasi baris aktif
                day_col_candidates = [c for c in df_table.columns if 'day' in c.lower() or 'date' in c.lower()]
                if not day_col_candidates:
                    continue
                target_day_col = day_col_candidates[0]
                
                # Buang baris kosong atau grafik/kurva pompa di bagian bawah tabel
                df_table = df_table.dropna(subset=[target_day_col])
                # Pastikan kolom tanggal benar-benar berisi format tanggal/angka, bukan teks sisa penjelasan grafik
                df_table = df_table[pd.to_datetime(df_table[target_day_col], errors='coerce').notnull()]
                
                if df_table.empty:
                    continue
                
                # --- EKSTRAKSI NAMA SUMUR (WELL NAME) ---
                # Mengambil nama sumur langsung dari teks sebelum kata 'Monitoring' pada nama sheet
                well_name_derived = sheet.split(' ')[0].strip()
                
                # Mencoba validasi silang dari teks baris metadata atas (jika polanya cocok)
                for idx, row in df_raw_full.iloc[:header_row_idx].iterrows():
                    row_cells = [str(x).strip() for x in row.values if pd.notnull(x)]
                    for cell_text in row_cells:
                        if 'well name' in cell_text.lower():
                            # Ambil teks setelah tanda titik dua atau sel di sebelahnya
                            well_name_derived = row_cells[-1].replace(':', '').strip()
                
                # --- PEMETAAN (MAPPING) KOLOM FLEXIBEL SUBSTRING ---
                df_clean = pd.DataFrame()
                df_clean['Date'] = pd.to_datetime(df_table[target_day_col])
                df_clean['Well_Name'] = well_name_derived
                
                # Fungsi pencarian kolom cerdas untuk mengantisipasi ketidakkonsistenan penulisan
                def find_and_parse(keywords, default_val=0):
                    matched_cols = [c for c in df_table.columns if any(k in c.lower() for k in keywords)]
                    if matched_cols:
                        return pd.to_numeric(df_table[matched_cols[0]], errors='coerce').fillna(default_val)
                    return pd.Series(default_val, index=df_table.index)
                
                # Ekstraksi Parameter Laju Produksi
                df_clean['Oil_Rate_BOPD'] = find_and_parse(['bopd', 'oil bopd'])
                df_clean['Water_Rate_BWPD'] = find_and_parse(['bwpd', 'water bwpd'])
                df_clean['Water_Cut_Percent'] = find_and_parse(['wc', 'water cut'])
                df_clean['Gas_Rate_MSCFD'] = find_and_parse(['mcfd', 'agf', 'gas'])
                
                # Ekstraksi Parameter Tekanan Pompa Downhole & Freq
                df_clean['PI_PSI'] = find_and_parse(['p intake', 'intake', 'pip'])
                df_clean['PD_PSI'] = find_and_parse(['p discharge', 'discharge', 'pdp'])
                df_clean['Frequency_Hz'] = find_and_parse(['freq', 'hz'], default_val=40)
                
                # Parameter Baseline Tambahan
                df_clean['Motor_Temp_C'] = 95.0
                df_clean['Vibration_G'] = 1.2
                
                # Simpan dataframe matang ke dalam objek kamus sumur
                all_wells_data[well_name_derived] = df_clean.sort_values('Date')
                
            if all_wells_data:
                st.sidebar.success(f"Berhasil memuat {len(all_wells_data)} Sumur Monitoring!")
            else:
                st.sidebar.error("Gagal mengekstrak data terstruktur dari sheet monitoring.")
                
    except Exception as e:
        st.sidebar.error(f"Eror pembacaan file: {e}")

# ==========================================
# 3. INTERFAS/TAMPILAN UTAMA DASHBOARD
# ==========================================
if all_wells_data:
    # Dropdown interaktif untuk memilih sumur yang terdeteksi aktif dari file
    selected_well = st.sidebar.selectbox("Pilih Sumur ESP:", list(all_wells_data.keys()))
    df_well = all_wells_data[selected_well]
    latest_data = df_well.iloc[-1]
    
    st.subheader(f"📊 Status Terakhir Sumur: {selected_well} ({latest_data['Date'].strftime('%d-%b-%Y')})")
    
    # Grid Utama - KPI Parameter Produksi
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Oil Rate", f"{latest_data['Oil_Rate_BOPD']:.1f} BOPD")
    col2.metric("Water Rate", f"{latest_data['Water_Rate_BWPD']:.1f} BWPD")
    col3.metric("Water Cut", f"{latest_data['Water_Cut_Percent']:.1f} %")
    col4.metric("Gas Rate", f"{latest_data['Gas_Rate_MSCFD']:.1f} MCFD")
    
    # Grid Kedua - KPI Parameter Downhole ESP
    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Pump Intake (PI)", f"{latest_data['PI_PSI']:.1f} PSI")
    col6.metric("Pump Discharge (PD)", f"{latest_data['PD_PSI']:.1f} PSI")
    col7.metric("VSD Frequency", f"{latest_data['Frequency_Hz']:.1f} Hz")
    col8.metric("Motor Temp (Baseline)", f"{latest_data['Motor_Temp_C']:.1f} °C")
    
    st.markdown("---")
    
    # ==========================================
    # 4. GRAFIK TREN PRODUKSI
    # ==========================================
    st.subheader("📈 Grafik Tren Produksi Sumur")
    fig_prod = go.Figure()
    fig_prod.add_trace(go.Scatter(x=df_well['Date'], y=df_well['Oil_Rate_BOPD'], mode='lines+markers', name='Oil Rate (BOPD)', line=dict(color='green', width=2)))
    fig_prod.add_trace(go.Scatter(x=df_well['Date'], y=df_well['Water_Rate_BWPD'], mode='lines', name='Water Rate (BWPD)', line=dict(color='blue', width=2)))
    fig_prod.update_layout(xaxis_title='Tanggal', yaxis_title='Production Fluid Rate', hovermode='x unified')
    st.plotly_chart(fig_prod, use_container_width=True)
    
    # ==========================================
    # 5. GRAFIK DOWNHOLE DENGAN FITUR MULTISELECT
    # ==========================================
    # ==========================================
    # 5. GRAFIK DOWNHOLE DENGAN FITUR MULTISELECT
    # ==========================================
    st.subheader("⚙️ Visualisasi Tren Downhole & ESP Parameter")
    
    # Kotak pilihan untuk menampilkan satu, sebagian, atau semua parameter sekaligus
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
                fig_downhole.add_trace(go.Scatter(x=df_well['Date'], y=df_well['PD_PSI'], mode='lines+markers', name='Discharge Press (PSI)', line=dict(color='teal')))
            elif param == "VSD Frequency":
                fig_downhole.add_trace(go.Scatter(x=df_well['Date'], y=df_well['Frequency_Hz'], mode='lines', name='Frequency (Hz)', line=dict(color='darkblue'), yaxis="y2"))
                fig_downhole.update_layout(yaxis2=dict(title="Frequency (Hz)", overlaying="y", side="right"))
                
        fig_downhole.update_layout(xaxis_title='Tanggal', yaxis_title='Pressure (PSI)', hovermode='x unified')
        st.plotly_chart(fig_downhole, use_container_width=True)
