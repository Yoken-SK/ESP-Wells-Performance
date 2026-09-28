import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# ==========================================
# 1. KONFIGURASI HALAMAN DASHBOARD
# ==========================================
st.set_page_config(
    page_title="ESP Well Monitoring Dashboard",
    page_icon="⚡",
    layout="wide"
)

st.title("⚡ ESP Production & Downhole Monitoring Dashboard")
st.markdown("Dashboard interaktif untuk monitoring performa produksi dan parameter downhole sumur ESP.")

# ==========================================
# 2. GENERATE DUMMY DATA (Data Cadangan jika belum upload)
# ==========================================
@st.cache_data
def generate_default_data():
    wells = ['Well-ESP-01', 'Well-ESP-02', 'Well-ESP-03', 'Well-ESP-04']
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    date_range = pd.date_range(start=start_date, end=end_date, freq='D')
    
    all_data = []
    np.random.seed(42)
    
    for well in wells:
        base_oil = np.random.randint(200, 600)
        base_water = np.random.randint(500, 1500)
        
        for date in date_range:
            oil_rate = base_oil + np.random.normal(0, 15)
            water_rate = base_water + np.random.normal(0, 40)
            liquid_rate = oil_rate + water_rate
            water_cut = (water_rate / liquid_rate) * 100
            gas_rate = oil_rate * np.random.uniform(150, 250) / 1000
            
            # Downhole Parameter + PI & PD
            motor_temp = np.random.uniform(90, 110) + (oil_rate * 0.02)
            pi_press = np.random.uniform(600, 900) - (liquid_rate * 0.1)  # Pump Intake
            pd_press = pi_press + np.random.uniform(1200, 1500)          # Pump Discharge
            vibration = np.random.uniform(0.5, 2.5)
            frequency = 50.0
            
            all_data.append({
                "Date": date.strftime('%Y-%m-%d'),
                "Well_Name": well,
                "Oil_Rate_BOPD": round(oil_rate, 1),
                "Water_Rate_BWPD": round(water_rate, 1),
                "Water_Cut_Percent": round(water_cut, 1),
                "Gas_Rate_MSCFD": round(gas_rate, 1),
                "Motor_Temp_C": round(motor_temp, 1),
                "PI_PSI": round(pi_press, 1),
                "PD_PSI": round(pd_press, 1),
                "Vibration_G": round(vibration, 2),
                "Frequency_Hz": frequency
            })
            
    return pd.DataFrame(all_data)

# ==========================================
# 3. SIDEBAR UPLOAD EXCEL & FILTER
# ==========================================
st.sidebar.header("📁 Unggah Data Sumur")
uploaded_file = st.sidebar.file_uploader("Upload File Excel (.xlsx)", type=["xlsx"])

# Memuat data utama (Dari Excel atau Default Data)
if uploaded_file is not None:
    try:
        df_all = pd.read_excel(uploaded_file)
        st.sidebar.success("Berhasil memuat file Excel!")
    except Exception as e:
        st.sidebar.error(f"Gagal membaca file: {e}")
        df_all = generate_default_data()
else:
    df_all = generate_default_data()
    st.sidebar.info("Menggunakan contoh data simulasi sumur bawaan.")

# Standardisasi nama kolom tanggal & Filter Sumur
if 'Date' in df_all.columns:
    df_all['Date'] = pd.to_datetime(df_all['Date'])

st.sidebar.markdown("---")
st.sidebar.header("Filter & Seleksi Sumur")
selected_well = st.sidebar.selectbox("Pilih Sumur ESP:", df_all['Well_Name'].unique())

# Filter data berdasarkan sumur
df_well = df_all[df_all['Well_Name'] == selected_well].sort_values('Date')
latest_data = df_well.iloc[-1]

# ==========================================
# 4. TAMPILAN KPI METRICS
# ==========================================
st.subheader(f"📊 Status Terakhir: {selected_well}")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Oil Rate", f"{latest_data['Oil_Rate_BOPD']} BOPD")
col2.metric("Water Rate", f"{latest_data['Water_Rate_BWPD']} BWPD")
col3.metric("Water Cut", f"{latest_data['Water_Cut_Percent']} %")
col4.metric("Gas Rate", f"{latest_data['Gas_Rate_MSCFD']} MSCFD")

col5, col6, col7, col8 = st.columns(4)
col5.metric("Motor Temp", f"{latest_data['Motor_Temp_C']} °C")
col6.metric("Pump Intake (PI)", f"{latest_data['PI_PSI']} PSI")
col7.metric("Pump Discharge (PD)", f"{latest_data['PD_PSI']} PSI")
col8.metric("Vibration / Freq", f"{latest_data['Vibration_G']} G / {latest_data['Frequency_Hz']} Hz")

st.markdown("---")

# ==========================================
# 5. GRAFIK TREN PRODUKSI
# ==========================================
st.subheader("📈 Grafik Tren Produksi")

fig_prod = go.Figure()
fig_prod.add_trace(go.Scatter(x=df_well['Date'], y=df_well['Oil_Rate_BOPD'], mode='lines+markers', name='Oil Rate (BOPD)', line=dict(color='green', width=2)))
fig_prod.add_trace(go.Scatter(x=df_well['Date'], y=df_well['Water_Rate_BWPD'], mode='lines', name='Water Rate (BWPD)', line=dict(color='blue', width=2)))
fig_prod.add_trace(go.Scatter(x=df_well['Date'], y=df_well['Gas_Rate_MSCFD'], mode='lines', name='Gas Rate (MSCFD)', line=dict(color='red', dash='dash')))

fig_prod.update_layout(xaxis_title='Tanggal', yaxis_title='Production Rate', hovermode='x unified', legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
st.plotly_chart(fig_prod, use_container_width=True)

# ==========================================
# 6. GRAFIK DOWNHOLE PARAMETER (FITUR SELEKSI INTEGRASI)
# ==========================================
st.subheader("⚙️ Grafik Tren Downhole Parameter")

# Definisikan daftar parameter beserta konfigurasinya
param_options = {
    "Motor Temperature (°C)": {"col": "Motor_Temp_C", "color": "orange", "axis": "y1"},
    "Pump Intake Pressure (PI - PSI)": {"col": "PI_PSI", "color": "purple", "axis": "y1"},
    "Pump Discharge Pressure (PD - PSI)": {"col": "PD_PSI", "color": "teal", "axis": "y2"},
    "Vibration (G)": {"col": "Vibration_G", "color": "red", "axis": "y2"},
    "Operating Frequency (Hz)": {"col": "Frequency_Hz", "color": "darkblue", "axis": "y1"}
}

# Berikan kontrol kepada pengguna untuk memilih parameter apa saja yang mau ditampilkan
selected_params = st.multiselect(
    "Pilih Downhole Parameter yang ingin ditampilkan pada grafik:",
    options=list(param_options.keys()),
    default=list(param_options.keys()) # Standar awal: Tampilkan semua
)

if not selected_params:
    st.warning("Silakan pilih minimal satu parameter pada kotak pilihan di atas untuk menampilkan grafik.")
else:
    fig_downhole = go.Figure()
    use_secondary_axis = False
    
    # Masukkan tiap parameter yang dicentang pengguna ke dalam grafik plot
    for param in selected_params:
        cfg = param_options[param]
        is_secondary = (cfg["axis"] == "y2")
        
        fig_downhole.add_trace(go.Scatter(
            x=df_well['Date'],
            y=df_well[cfg["col"]],
            name=param,
            yaxis="y2" if is_secondary else "y",
            mode='lines+markers' if cfg["col"] in ["Vibration_G", "Frequency_Hz"] else 'lines',
            line=dict(color=cfg["color"])
        ))
        if is_secondary:
            use_secondary_axis = True

    # Konfigurasi tata letak grafik sumur axis tunggal atau ganda
    layout_kwargs = {
        "xaxis": dict(title="Tanggal"),
        "yaxis": dict(title="Primary Parameters (Temp / PI / Freq)"),
        "hovermode": "x unified",
        "legend": dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    }
    
    if use_secondary_axis:
        layout_kwargs["yaxis2"] = dict(
            title="Secondary Parameters (PD / Vibration)",
            overlaying="y",
            side="right"
        )
        
    fig_downhole.update_layout(**layout_kwargs)
    st.plotly_chart(fig_downhole, use_container_width=True)

# ==========================================
# 7. TABEL DATA SUMUR
# ==========================================
with st.expander("🔍 Lihat Detail Tabel Data Keseluruhan"):
    st.dataframe(df_well, use_container_width=True)
