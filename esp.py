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
# 2. GENERATE DUMMY DATA (Simulasi Data Sumur)
# ==========================================
@st.cache_data
def generate_esp_data():
    wells = ['Well-ESP-01', 'Well-ESP-02', 'Well-ESP-03', 'Well-ESP-04']
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    date_range = pd.date_range(start=start_date, end=end_date, freq='D')
    
    all_data = []
    
    np.random.seed(42) # Mengunci random state agar data konsisten
    
    for well in wells:
        # Basis parameter agar tiap sumur berbeda karakteristik
        base_oil = np.random.randint(200, 600)
        base_water = np.random.randint(500, 1500)
        
        for date in date_range:
            oil_rate = base_oil + np.random.normal(0, 15)
            water_rate = base_water + np.random.normal(0, 40)
            liquid_rate = oil_rate + water_rate
            water_cut = (water_rate / liquid_rate) * 100
            gas_rate = oil_rate * np.random.uniform(150, 250) / 1000 # Gas dalam Mscf/d
            
            # Downhole Parameter
            motor_temp = np.random.uniform(90, 110) + (oil_rate * 0.02) # °C
            intake_press = np.random.uniform(500, 800) - (liquid_rate * 0.1) # Psi
            vibration = np.random.uniform(0.5, 2.5) # Gs
            frequency = np.random.choice([45, 50, 55, 60]) # Hz
            
            all_data.append({
                "Date": date,
                "Well_Name": well,
                "Oil_Rate_BOPD": round(oil_rate, 1),
                "Water_Rate_BWPD": round(water_rate, 1),
                "Water_Cut_Percent": round(water_cut, 1),
                "Gas_Rate_MSCFD": round(gas_rate, 1),
                "Motor_Temp_C": round(motor_temp, 1),
                "Intake_Pressure_PSI": round(intake_press, 1),
                "Vibration_G": round(vibration, 2),
                "Frequency_Hz": frequency
            })
            
    return pd.DataFrame(all_data)

df_all = generate_esp_data()

# ==========================================
# 3. SIDEBAR / FILTER SUMUR
# ==========================================
st.sidebar.header("Filter & Seleksi Sumur")
selected_well = st.sidebar.selectbox("Pilih Sumur ESP:", df_all['Well_Name'].unique())

# Filter data berdasarkan sumur yang dipilih
df_well = df_all[df_all['Well_Name'] == selected_well].sort_values('Date')
latest_data = df_well.iloc[-1] # Data hari terakhir untuk KPI Card

# ==========================================
# 4. TAMPILAN KPI METRICS (RATE & PARAMETER TERKINI)
# ==========================================
st.subheader(f"📊 Status Terakhir: {selected_well}")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Oil Rate", f"{latest_data['Oil_Rate_BOPD']} BOPD")
col2.metric("Water Rate", f"{latest_data['Water_Rate_BWPD']} BWPD")
col3.metric("Water Cut", f"{latest_data['Water_Cut_Percent']} %")
col4.metric("Gas Rate", f"{latest_data['Gas_Rate_MSCFD']} MSCFD")

col5, col6, col7, col8 = st.columns(4)
col5.metric("Motor Temp", f"{latest_data['Motor_Temp_C']} °C", delta_color="inverse")
col6.metric("Intake Pressure", f"{latest_data['Intake_Pressure_PSI']} PSI")
col7.metric("Vibration", f"{latest_data['Vibration_G']} G", delta_color="inverse")
col8.metric("Operating Freq", f"{latest_data['Frequency_Hz']} Hz")

st.markdown("---")

# ==========================================
# 5. GRAFIK PRODUKSI (HISTORIKAL)
# ==========================================
st.subheader("📈 Grafik Tren Produksi (30 Hari Terakhir)")

fig_prod = go.Figure()
# Line untuk Oil Rate
fig_prod.add_trace(go.Scatter(x=df_well['Date'], y=df_well['Oil_Rate_BOPD'],
                    mode='lines+markers', name='Oil Rate (BOPD)', line=dict(color='green', width=2)))
# Line untuk Water Rate
fig_prod.add_trace(go.Scatter(x=df_well['Date'], y=df_well['Water_Rate_BWPD'],
                    mode='lines', name='Water Rate (BWPD)', line=dict(color='blue', width=2)))
# Line untuk Gas Rate (Sumbu Y Kedua / Kanan jika diperlukan, di sini disatukan dulu)
fig_prod.add_trace(go.Scatter(x=df_well['Date'], y=df_well['Gas_Rate_MSCFD'],
                    mode='lines', name='Gas Rate (MSCFD)', line=dict(color='red', dash='dash')))

fig_prod.update_layout(
    xaxis_title='Tanggal',
    yaxis_title='Production Rate',
    hovermode='x unified',
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)
st.plotly_chart(fig_prod, use_container_width=True)

# ==========================================
# 6. GRAFIK DOWNHOLE PARAMETER
# ==========================================
st.subheader("⚙️ Grafik Tren Downhole Parameter")

tab1, tab2, tab3 = st.tabs(["Temperature & Pressure", "Vibration", "Frequency"])

with tab1:
    fig_tp = go.Figure()
    # Sumbu Kiri: Temperatur
    fig_tp.add_trace(go.Scatter(x=df_well['Date'], y=df_well['Motor_Temp_C'],
                        name='Motor Temp (°C)', line=dict(color='orange')))
    # Sumbu Kanan: Tekanan
    fig_tp.add_trace(go.Scatter(x=df_well['Date'], y=df_well['Intake_Pressure_PSI'],
                        name='Intake Press (PSI)', yaxis='y2', line=dict(color='purple')))
    
    # Layout untuk Dual Axis (Sumbu Y Ganda)
    fig_tp.update_layout(
        yaxis=dict(title='Motor Temperature (°C)', titlefont=dict(color='orange'), tickfont=dict(color='orange')),
        yaxis2=dict(title='Intake Pressure (PSI)', titlefont=dict(color='purple'), tickfont=dict(color='purple'),
                    overlaying='y', side='right'),
        hovermode='x unified'
    )
    st.plotly_chart(fig_tp, use_container_width=True)

with tab2:
    fig_vib = px.line(df_well, x='Date', y='Vibration_G', title='Downhole Vibration Trend',
                      labels={'Vibration_G': 'Vibration (G)'}, color_discrete_sequence=['red'])
    # Tambahkan garis batas aman vibrasi (misal aman jika di bawah 1.5 G)
    fig_vib.add_hline(y=2.0, line_dash="dash", line_color="orange", annotation_text="Warning Limit (2.0 G)")
    st.plotly_chart(fig_vib, use_container_width=True)

with tab3:
    fig_freq = px.stepline(df_well, x='Date', y='Frequency_Hz', title='VSD Frequency History',
                          labels={'Frequency_Hz': 'Frequency (Hz)'}, color_discrete_sequence=['darkblue'])
    st.plotly_chart(fig_freq, use_container_width=True)

# ==========================================
# 7. TABEL DATA SUMUR
# ==========================================
with st.expander("🔍 Lihat Detail Tabel Data"):
    st.dataframe(df_well.style.highlight_max(axis=0, color='#e6f2ff'), use_container_width=True)
