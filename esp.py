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
st.markdown("Dashboard cerdas yang dikustomisasi khusus untuk membaca format multi-sheet laporan lapangan.")

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
                
                # Membaca ulang sheet dari baris tabel data utama ke bawah
                df_table = pd.read_excel(uploaded_file, sheet_name=sheet, skiprows=header_row_idx)
                
                # Bersihkan nama kolom dari spasi berlebih dan enter (\n)
                df_table.columns = df_table.columns.str.strip().str.replace('\n', ' ').str.replace('  ', ' ')
                
                # Cari kolom utama tanggal
                day_col_candidates = [c for c in df_table.columns if 'day' in c.lower() or 'date' in c.lower()]
                if not day_col_candidates:
                    continue
                target_day_col = day_col_candidates[0]
                
                # Bersihkan baris non-tanggal (seperti sub-header unit atau teks kurva di bawah)
                df_table['Clean_Date'] = pd.to_datetime(df_table[target_day_col], errors='coerce')
                df_table = df_table.dropna(subset=['Clean_Date'])
                
                if df_table.empty:
                    continue
                
                # --- EKSTRAKSI NAMA SUMUR ---
                well_name_derived = sheet.split(' ')[0].strip()
                for idx, row in df_raw_full.iloc[:header_row_idx].iterrows():
                    row_cells = [str(x).strip() for x in row.values if pd.notnull(x)]
                    for cell_text in row_cells:
                        if 'well name' in cell_text.lower():
                            well_name_derived = row_cells[-1].replace(':', '').strip()
                
                # --- PEMETAAN KOLOM STRIP KETAT & CLEANING AGRESIP ---
                df_clean = pd.DataFrame()
                df_clean['Date'] = df_table['Clean_Date']
                df_clean['Well_Name'] = well_name_derived
                
                def find_and_parse_strict(keywords, default_val=np.nan):
                    for c in df_table.columns:
                        clean_col_name = c.lower().replace(' ', '')
                        if any(k.replace(' ', '') in clean_col_name for k in keywords):
                            # Konversi paksa string teks bermasalah menjadi NaN agar bisa dibersihkan
                            series_converted = pd.to_numeric(df_table[c], errors='coerce')
                            # Jika kolom kosong akibat baris unit, isi dengan nilai default aman
                            return series_converted
                    return pd.Series(default_val, index=df_table.index)
                
                # Ekstraksi Parameter Laju Produksi 
                df_clean['Oil_Rate_BOPD'] = find_and_parse_strict(['oilbopd', 'bopd', 'oil']).fillna(0)
                df_clean['Water_Rate_BWPD'] = find_and_parse_strict(['waterbwpd', 'bwpd', 'water']).fillna(0)
                df_clean['Water_Cut_Percent'] = find_and_parse_strict(['watercut', 'wc%']).fillna(0)
                df_clean['Gas_Rate_MSCFD'] = find_and_parse_strict(['agfmcfd', 'mcfd', 'gas', 'agf']).fillna(0)
                
                # Ekstraksi Parameter Tekanan Pompa Downhole & Freq
                df_clean['PI_PSI'] = find_and_parse_strict(['pintake', 'pip', 'intake', 'pintakepsi']).fillna(method='ffill').fillna(0)
                df_clean['PD_PSI'] = find_and_parse_strict(['pdischarge', 'pdp', 'discharge', 'pdischargepsi']).fillna(method='ffill').fillna(0)
                df_clean['Frequency_Hz'] = find_and_parse_strict(['freqhz', 'hz', 'freq'], default_val=40).fillna(40)
                
                # Hilangkan baris data yang bernilai 0 murni di kolom kritikal untuk menjaga akurasi skala grafik
                df_clean = df_clean[df_clean['Oil_Rate_BOPD'] > 0] if not df_clean.empty else df_clean
                
                if not df_clean.empty:
                    all_wells_data[well_name_derived] = df_clean.sort_values('Date')
                
            if all_wells_data:
                st.sidebar.success(f"Berhasil memuat {len(all_wells_data)} Sumur Monitoring!")
            else:
                st.sidebar.error("Gagal memproses baris angka. Cek apakah kolom berisi data teks unit.")
                
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
    col8.metric("Total Data Points", f"{len(df_well)} Hari")
    
    st.markdown("---")
    
    # ==========================================
    # 4. GRAFIK TREN PRODUKSI (MULTISELECT)
    # ==========================================
    st.subheader("📈 Grafik Tren Produksi Sumur")
    
    prod_options = {
        "Oil Rate (BOPD)": {"col": "Oil_Rate_BOPD", "color": "green", "axis": "y1", "dash": "solid"},
        "Water Rate (BWPD)": {"col": "Water_Rate_BWPD", "color": "blue", "axis": "y1", "dash": "solid"},
        "Gas Rate (MCFD)": {"col": "Gas_Rate_MSCFD", "color": "red", "axis": "y2", "dash": "dash"}
    }
    
    selected_prod_params = st.multiselect(
        "Pilih Parameter Produksi yang Ingin Ditampilkan pada Grafik:",
        options=list(prod_options.keys()),
        default=["Oil Rate (BOPD)", "Water Rate (BWPD)"]
    )
    
    if not selected_prod_params:
        st.warning("Silakan pilih minimal satu parameter produksi untuk menampilkan grafik.")
    else:
        fig_prod = go.Figure()
        use_prod_y2 = False
        
        for param in selected_prod_params:
            cfg = prod_options[param]
            is_y2 = (cfg["axis"] == "y2")
            fig_prod.add_trace(go.Scatter(
                x=df_well['Date'], 
                y=df_well[cfg["col"]], 
                mode='lines+markers', 
                name=param, 
                yaxis="y2" if is_y2 else "y",
                line=dict(color=cfg["color"], width=2, dash=cfg["dash"])
            ))
            if is_y2:
                use_prod_y2 = True
                
        prod_layout = {
            "xaxis": dict(title="Tanggal"),
            "yaxis": dict(title="Liquid Rate (BOPD / BWPD)", autorange=True),
            "hovermode": "x unified"
        }
        if use_prod_y2:
            prod_layout["yaxis2"] = dict(title="Gas Rate (MCFD)", overlaying="y", side="right", autorange=True)
            
        fig_prod.update_layout(**prod_layout)
        st.plotly_chart(fig_prod, use_container_width=True)
    
    # ==========================================
    # 5. GRAFIK DOWNHOLE DENGAN FITUR MULTISELECT
    # ==========================================
    st.subheader("⚙️ Visualisasi Tren Downhole & ESP Parameter")
    
    downhole_options = {
        "Pump Intake Pressure (PI)": {"col": "PI_PSI", "color": "purple", "axis": "y1"},
        "Pump Discharge Pressure (PD)": {"col": "PD_PSI", "color": "teal", "axis": "y1"},
        "VSD Frequency": {"col": "Frequency_Hz", "color": "darkblue", "axis": "y2"}
    }
    
    selected_params = st.multiselect(
        "Pilih Parameter Downhole yang Ingin Ditampilkan:",
        options=list(downhole_options.keys()),
