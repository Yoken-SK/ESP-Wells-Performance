import streamlit as st
import pandas as pd
import numpy as np
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
                df_raw_full = pd.read_excel(uploaded_file, sheet_name=sheet, header=None)
                
                # --- DETEKSI KELOMPOK TABEL SECARA DINAMIS ---
                header_row_idx = None
                for idx, row in df_raw_full.iterrows():
                    row_str = [str(x).strip().lower() for x in row.values if pd.notnull(x)]
                    if 'day' in row_str or 'hari' in row_str:
                        header_row_idx = idx
                        break
                
                if header_row_idx is None:
                    continue
                
                # Membaca tabel data utama
                df_table = pd.read_excel(uploaded_file, sheet_name=sheet, skiprows=header_row_idx)
                df_table.columns = df_table.columns.str.strip().str.replace('\n', ' ').str.replace('  ', ' ')
                
                # Cari kolom tanggal
                day_col_candidates = [c for c in df_table.columns if 'day' in c.lower() or 'date' in c.lower() or 'tgl' in c.lower()]
                if not day_col_candidates:
                    continue
                target_day_col = day_col_candidates
                
                # Bersihkan baris non-tanggal
                df_table['Clean_Date'] = pd.to_datetime(df_table[target_day_col], errors='coerce')
                df_table = df_table.dropna(subset=['Clean_Date'])
                
                if df_table.empty:
                    continue
                
                # --- EKSTRAKSI NAMA SUMUR ---
                well_name_derived = sheet.replace('Monitoring', '').replace('monitoring', '').strip()
                for idx, row in df_raw_full.iloc[:header_row_idx].iterrows():
                    row_cells = [str(x).strip() for x in row.values if pd.notnull(x)]
                    for cell_text in row_cells:
                        if 'well name' in cell_text.lower() or 'sumur' in cell_text.lower():
                            well_name_derived = row_cells[-1].replace(':', '').strip()
                
                # --- PEMETAAN (MAPPING) KOLOM ---
                df_clean = pd.DataFrame()
                df_clean['Date'] = df_table['Clean_Date']
                df_clean['Well_Name'] = well_name_derived
                
                def find_and_parse_flexible(keywords, default_val=np.nan):
                    for c in df_table.columns:
                        clean_col_name = c.lower().replace(' ', '').replace('\n', '')
                        if any(k.lower().replace(' ', '') in clean_col_name for k in keywords):
                            return pd.to_numeric(df_table[c], errors='coerce')
                    return pd.Series(default_val, index=df_table.index)
                
                # Ekstraksi Parameter Laju Produksi
                df_clean['Oil_Rate_BOPD'] = find_and_parse_flexible(['oilbopd', 'bopd', 'oil', 'bop']).fillna(0)
                df_clean['Water_Rate_BWPD'] = find_and_parse_flexible(['waterbwpd', 'bwpd', 'water', 'bwp']).fillna(0)
                df_clean['Water_Cut_Percent'] = find_and_parse_flexible(['watercut', 'wc%', 'wc']).fillna(0)
                df_clean['Gas_Rate_MSCFD'] = find_and_parse_flexible(['agfmcfd', 'mcfd', 'gas', 'agf', 'gascf']).fillna(0)
                
                # Ekstraksi Parameter Tekanan Pompa Downhole & Freq
                df_clean['PI_PSI'] = find_and_parse_flexible(['pintake', 'pip', 'intake', 'pintakepsi', 'p.intake']).ffill().bfill().fillna(0)
                df_clean['PD_PSI'] = find_and_parse_flexible(['pdischarge', 'pdp', 'discharge', 'pdischargepsi', 'p.discharge']).ffill().bfill().fillna(0)
                df_clean['Frequency_Hz'] = find_and_parse_flexible(['freqhz', 'hz', 'freq', 'vsd'], default_val=40).ffill().bfill().fillna(40)
                
                # Parameter Tambahan
                df_clean['Motor_Temp_C'] = 95.0
                df_clean['Vibration_G'] = 1.2
                
                if not df_clean.empty:
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
    st.columns(4)[2].metric("Water Cut", f"{latest_data['Water_Cut_Percent']:.1f} %")
    st.columns(4)[3].metric("Gas Rate", f"{latest_data['Gas_Rate_MSCFD']:.1f} MCFD")
    
    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Pump Intake (PI)", f"{latest_data['PI_PSI']:.1f} PSI")
    col6.metric("Pump Discharge (PD)", f"{latest_data['PD_PSI']:.1f} PSI")
    st.columns(4)[2].metric("VSD Frequency", f"{latest_data['Frequency_Hz']:.1f} Hz")
    st.columns(4)[3].metric("Total Data Points", f"{len(df_well)} Hari")
    
    st.markdown("---")
    
    # ==========================================
    # 4. GRAFIK TREN PRODUKSI (STRUKTUR DATA FLAT ANTI-ERROR)
    # ==========================================
    st.subheader("📈 Grafik Tren Produksi Sumur")
    
    prod_config = {
        "Oil Rate (BOPD)": {"col": "Oil_Rate_BOPD", "color": "green", "y": "y", "dash": "solid"},
        "Water Rate (BWPD)": {"col": "Water_Rate_BWPD", "color": "blue", "y": "y", "dash": "solid"},
        "Gas Rate (MCFD)": {"col": "Gas_Rate_MSCFD", "color": "red", "y": "y2", "dash": "dash"}
    }
    
    selected_prod = st.multiselect(
        "Pilih Parameter Produksi yang Ingin Ditampilkan pada Grafik:",
        options=list(prod_config.keys()),
        default=["Oil Rate (BOPD)", "Water Rate (BWPD)"]
    )
    
    fig_prod = go.Figure()
    
    # Loop rata tanpa percabangan if-else untuk sumbu Y ganda
    for k in selected_prod:
        cfg = prod_config[k]
        fig_prod.add_trace(go.Scatter(x=df_well['Date'], y=df_well[cfg["col"]], mode='lines+markers', name=k, yaxis=cfg["y"], line=dict(color=cfg["color"], width=2, dash=cfg["dash"])))
        
    fig_prod.update_layout(
        xaxis=dict(title="Tanggal"),
        yaxis=dict(title="Liquid Rate (BOPD / BWPD)", autorange=True),
        yaxis2=dict(title="Gas Rate (MCFD)", overlaying="y", side="right", autorange=True),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig_prod, use_container_width=True)
    
    st.markdown("---")
    
    # ==========================================
    # 5. GRAFIK DOWNHOLE PARAMETER (STRUKTUR DATA FLAT ANTI-ERROR)
    # ==========================================
    st.subheader("⚙️ Visualisasi Tren Downhole & ESP Parameter")
    
    dh_config = {
        "Pump Intake Pressure (PI)": {"col": "PI_PSI", "color": "purple", "y": "y"},
        "Pump Discharge Pressure (PD)": {"col": "PD_PSI", "color": "teal", "y": "y"},
        "VSD Frequency": {"col": "Frequency_Hz", "color": "darkblue", "y": "y2"}
    }
    
    selected_dh = st.multiselect(
        "Pilih Parameter Downhole yang Ingin Ditampilkan:",
        options=list(dh_config.keys()),
        default=["Pump Intake Pressure (PI)", "Pump Discharge Pressure (PD)"]
    )
    
    fig_downhole = go.Figure()
    
    # Loop rata tanpa percabangan if-else untuk sumbu Y ganda
    for k in selected_dh:
        cfg = dh_config[k]
        fig_downhole.add_trace(go.Scatter(x=df_well['Date'], y=df_well[cfg["col"]], mode='lines+markers', name=k, yaxis=cfg["y"], line=dict(color=cfg["color"], width=2)))
        
    fig_downhole.update_layout(
        xaxis=dict(title="Tanggal"),
        yaxis=dict(title="Pressure (PSI)", autorange=True),
        yaxis2=dict(title="Frequency (Hz)", overlaying="y", side="right", autorange=True),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig_downhole, use_container_width=True)
    
    # ==========================================
