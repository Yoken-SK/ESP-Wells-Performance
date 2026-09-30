import re
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ==========================================
# 1. KONFIGURASI HALAMAN DASHBOARD & RESPONSIVE CSS
# ==========================================
st.set_page_config(
    page_title="ESP Well Dashboard",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Custom CSS untuk Tablet Optimization & Compact Spacing
st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 1rem !important;
        padding-left: 0.8rem !important;
        padding-right: 0.8rem !important;
    }
    
    /* Mengurangi jarak antarkartu metric di Tablet/Mobile */
    [data-testid="stMetric"] {
        padding: 4px 8px !important;
        margin-bottom: -10px !important;
    }
    
    [data-testid="stMetricValue"] {
        font-size: clamp(1.1rem, 2.2vw, 1.4rem) !important;
        font-weight: 700;
        line-height: 1.1 !important;
    }
    
    [data-testid="stMetricLabel"] {
        font-size: clamp(0.75rem, 1.3vw, 0.85rem) !important;
        color: #4A5568;
        margin-bottom: 2px !important;
    }

    /* Mengurangi spacing horizontal antar kolom di Streamlit */
    [data-testid="column"] {
        padding: 0px 4px !important;
    }

    .stPlotlyChart {
        width: 100% !important;
    }

    h1 { font-size: clamp(1.3rem, 3.5vw, 2.0rem) !important; }
    h2 { font-size: clamp(1.1rem, 2.8vw, 1.6rem) !important; }
    h3 { font-size: clamp(0.95rem, 2.2vw, 1.2rem) !important; }
    
    hr {
        margin-top: 0.5rem !important;
        margin-bottom: 0.8rem !important;
    }
    </style>
""",
    unsafe_allow_html=True,
)

st.title("⚡ ESP Production & Downhole Monitoring Dashboard")

# ==========================================
# 2. SIDEBAR UPLOAD FILE & INPUT KEDALAMAN
# ==========================================
st.sidebar.header("📁 Unggah Laporan Lapangan")
uploaded_file = st.sidebar.file_uploader(
    "1. Upload File Excel Produksi Utama (.xlsx)", type=["xlsx"]
)

st.sidebar.markdown("---")
st.sidebar.header("📊 Unggah Data Downhole Khusus (Opsional)")
uploaded_dh_file = st.sidebar.file_uploader(
    "2. Upload Data Downhole / Sensor (.csv, .xlsx)",
    type=["csv", "xlsx"],
    key="dh_uploader",
)

if "well_depth_params" not in st.session_state:
  st.session_state["well_depth_params"] = {}

# Session state untuk tracking key perbaikan zoom
if "reset_sch_key" not in st.session_state:
  st.session_state["reset_sch_key"] = 0
if "reset_prod_key" not in st.session_state:
  st.session_state["reset_prod_key"] = 0
if "reset_dh_key" not in st.session_state:
  st.session_state["reset_dh_key"] = 0

DEFAULT_DEPTH_CONFIGS = {
    "GE-4": {
        "casing": 6000.0,
        "psd": 4500.0,
        "perf_top": 5000.0,
        "perf_bot": 5200.0,
    },
    "GE-6": {
        "casing": 7200.0,
        "psd": 5800.0,
        "perf_top": 6100.0,
        "perf_bot": 6350.0,
    },
}

all_wells_data = {}

# ==========================================
# 3. PARSING DATA EXCEL UNTUK SETIAP SUMUR
# ==========================================
if uploaded_file is not None:
  try:
    excel_file = pd.ExcelFile(uploaded_file)
    sheet_names = excel_file.sheet_names
    monitoring_sheets = [s for s in sheet_names if "monitoring" in s.lower()]

    if not monitoring_sheets:
      st.sidebar.error(
          "Tidak ditemukan sheet dengan nama 'Monitoring' di file ini!"
      )
    else:
      for sheet in monitoring_sheets:
        df_raw_full = pd.read_excel(
            uploaded_file, sheet_name=sheet, header=None
        )

        header_row_idx = None
        for idx, row in df_raw_full.iterrows():
          row_str = [
              str(x).strip().lower() for x in row.values if pd.notnull(x)
          ]
          if "day" in row_str or "hari" in row_str or "date" in row_str:
            header_row_idx = idx
            break

        if header_row_idx is None:
          continue

        df_table = pd.read_excel(
            uploaded_file, sheet_name=sheet, skiprows=header_row_idx
        )
        df_table.columns = (
            df_table.columns.astype(str)
            .str.strip()
            .str.replace("\n", " ")
            .str.replace(r"\s+", " ", regex=True)
        )

        day_col_candidates = [
            c
            for c in df_table.columns
            if "day" in c.lower()
            or "date" in c.lower()
            or "tgl" in c.lower()
            or "time" in c.lower()
        ]
        if not day_col_candidates:
          continue
        target_day_col = day_col_candidates[0]

        detected_month = 9
        detected_year = 2026
        for idx, row in df_raw_full.iloc[:header_row_idx].iterrows():
          row_cells = [str(x).strip() for x in row.values if pd.notnull(x)]
          for cell_text in row_cells:
            match = re.search(r"([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})", cell_text)
            if match:
              try:
                temp_date = pd.to_datetime(match.group(0), errors="coerce")
                if pd.notnull(temp_date):
                  detected_month = temp_date.month
                  detected_year = temp_date.year
              except Exception:
                pass

        df_clean = pd.DataFrame()

        def find_and_parse_flexible(keywords, default_val=np.nan):
          for c in df_table.columns:
            clean_col_name = c.lower().replace(" ", "").replace("\n", "")
            if any(
                k.lower().replace(" ", "") in clean_col_name for k in keywords
            ):
              return pd.to_numeric(df_table[c], errors="coerce")
          return pd.Series(default_val, index=df_table.index)

        df_clean["Oil_Rate_BOPD"] = find_and_parse_flexible(
            ["oilbopd", "bopd", "oil", "bop"]
        )
        df_clean["Water_Rate_BWPD"] = find_and_parse_flexible(
            ["waterbwpd", "bwpd", "water", "bwp"]
        )
        df_clean["Water_Cut_Percent"] = find_and_parse_flexible(
            ["watercut", "wc%", "wc"]
        ).fillna(0)
        df_clean["Gas_Rate_MSCFD"] = find_and_parse_flexible(
            ["agfmcfd", "mcfd", "gas", "agf", "gascf"]
        ).fillna(0)

        df_clean["PI_PSI"] = find_and_parse_flexible(
            ["pintake", "pip", "intake", "pintakepsi", "p.intake"]
        )
        df_clean["PD_PSI"] = find_and_parse_flexible(
            ["pdischarge", "pdp", "discharge", "pdischargepsi", "p.discharge"]
        )

        df_clean["Motor_Temp_C"] = find_and_parse_flexible(
            ["motortemp", "mtemp", "temp", "motortempc", "tmotor"],
            default_val=np.nan,
        )
        df_clean["Vibration_G"] = find_and_parse_flexible(
            ["vibration", "vib", "vibrationg", "vibrasig", "vibg"],
            default_val=np.nan,
        )

        freq_series = find_and_parse_flexible(
            ["freqhz", "hz", "freq", "vsd"], default_val=40
        )
        df_clean["Frequency_Hz"] = freq_series.ffill().bfill().fillna(40)

        df_clean["Raw_Day"] = df_table[target_day_col]

        df_clean = df_clean.dropna(
            subset=["Oil_Rate_BOPD", "Water_Rate_BWPD"], how="all"
        )

        df_clean["PI_PSI"] = df_clean["PI_PSI"].ffill().bfill().fillna(0)
        df_clean["PD_PSI"] = df_clean["PD_PSI"].ffill().bfill().fillna(0)
        df_clean["Motor_Temp_C"] = df_clean["Motor_Temp_C"].ffill().bfill()
        df_clean["Vibration_G"] = df_clean["Vibration_G"].ffill().bfill()
        df_clean["Oil_Rate_BOPD"] = df_clean["Oil_Rate_BOPD"].fillna(0)
        df_clean["Water_Rate_BWPD"] = df_clean["Water_Rate_BWPD"].fillna(0)

        df_clean["Valid_Check"] = (
            df_clean["Oil_Rate_BOPD"]
            + df_clean["Water_Rate_BWPD"]
            + df_clean["PI_PSI"]
        )
        df_clean = df_clean[df_clean["Valid_Check"] > 0]

        if df_clean.empty:
          continue

        def parse_date_smart(val):
          val_str = str(val).strip()
          if val_str.isdigit() and 1 <= int(val_str) <= 31:
            return pd.to_datetime(
                f"{detected_year}-{detected_month:02d}-{int(val_str):02d}",
                errors="coerce",
            )
          parsed = pd.to_datetime(val, errors="coerce")
          if pd.notnull(parsed):
            return parsed
          return pd.NaT

        df_clean["Date"] = df_clean["Raw_Day"].apply(parse_date_smart)
        df_clean["Date"] = df_clean["Date"].ffill().bfill()

        well_name_derived = (
            sheet.replace("Monitoring", "").replace("monitoring", "").strip()
        )
        for idx, row in df_raw_full.iloc[:header_row_idx].iterrows():
          row_cells = [str(x).strip() for x in row.values if pd.notnull(x)]
          for cell_text in row_cells:
            if (
                "well name" in cell_text.lower()
                or "sumur" in cell_text.lower()
            ):
              well_name_derived = row_cells[-1].replace(":", "").strip()

        df_clean["Well_Name"] = well_name_derived
        all_wells_data[well_name_derived] = df_clean.sort_values("Date")

        if well_name_derived not in st.session_state["well_depth_params"]:
          if well_name_derived in DEFAULT_DEPTH_CONFIGS:
            st.session_state["well_depth_params"][well_name_derived] = (
                DEFAULT_DEPTH_CONFIGS[well_name_derived].copy()
            )
          else:
            st.session_state["well_depth_params"][well_name_derived] = {
                "casing": 6500.0,
                "psd": 4800.0,
                "perf_top": 5300.0,
                "perf_bot": 5500.0,
            }

      if all_wells_data:
        st.sidebar.success(
            f"Berhasil memuat {len(all_wells_data)} Sumur Monitoring!"
        )

  except Exception as e:
    st.sidebar.error(f"Eror pembacaan file: {e}")

# Integration Data Sensor Downhole Terpisah
if uploaded_dh_file is not None and all_wells_data:
  try:
    if uploaded_dh_file.name.endswith(".csv"):
      df_dh_upload = pd.read_csv(uploaded_dh_file)
    else:
      df_dh_upload = pd.read_excel(uploaded_dh_file)

    df_dh_upload.columns = df_dh_upload.columns.str.strip().str.lower()

    date_col = next(
        (
            c
            for c in df_dh_upload.columns
            if "date" in c or "tgl" in c or "time" in c or "tanggal" in c
        ),
        None,
    )
    temp_col = next(
        (
            c
            for c in df_dh_upload.columns
            if "temp" in c or "suhu" in c or "tmotor" in c
        ),
        None,
    )
    vib_col = next(
        (
            c
            for c in df_dh_upload.columns
            if "vib" in c or "vibration" in c or "getaran" in c
        ),
        None,
    )

    if date_col:
      df_dh_upload["Date_Parsed"] = pd.to_datetime(
          df_dh_upload[date_col], errors="coerce"
      )

      for well_k in all_wells_data.keys():
        df_target = all_wells_data[well_k]
        if temp_col:
          df_dh_upload[temp_col] = pd.to_numeric(
              df_dh_upload[temp_col], errors="coerce"
          )
          temp_map = df_dh_upload.dropna(
              subset=["Date_Parsed", temp_col]
          ).set_index("Date_Parsed")[temp_col]
          df_target["Motor_Temp_C"] = (
              df_target["Date"].map(temp_map).fillna(df_target["Motor_Temp_C"])
          )

        if vib_col:
          df_dh_upload[vib_col] = pd.to_numeric(
              df_dh_upload[vib_col], errors="coerce"
          )
          vib_map = df_dh_upload.dropna(
              subset=["Date_Parsed", vib_col]
          ).set_index("Date_Parsed")[vib_col]
          df_target["Vibration_G"] = (
              df_target["Date"].map(vib_map).fillna(df_target["Vibration_G"])
          )

        all_wells_data[well_k] = df_target

      st.sidebar.success("✅ Data Sensor Downhole terpisah berhasil terhubung!")

  except Exception as ex:
    st.sidebar.warning(f"Gagal membaca data sensor terpisah: {ex}")


# ==========================================
# 4. FUNGSI MEMBUAT SKEMATIK ESP
# ==========================================
def create_esp_schematic_dynamic(
    temp_val, vib_val, pi_val, pd_val, casing_d, psd_d, perf_top, perf_bot
):
  fig = go.Figure()
  max_d = max(casing_d, perf_bot + 200)

  # Casing Outer
  fig.add_shape(
      type="rect",
      x0=-0.8,
      y0=0,
      x1=-0.7,
      y1=max_d,
      fillcolor="#4A5568",
      line=dict(color="#2D3748"),
  )
  fig.add_shape(
      type="rect",
      x0=0.7,
      y0=0,
      x1=0.8,
      y1=max_d,
      fillcolor="#4A5568",
      line=dict(color="#2D3748"),
  )

  # Fluida Annulus
  fig.add_shape(
      type="rect",
      x0=-0.7,
      y0=0,
      x1=0.7,
      y1=max_d,
      fillcolor="rgba(226, 232, 240, 0.3)",
      line=dict(width=0),
  )

  # Zona Perforasi
  fig.add_shape(
      type="rect",
      x0=-0.9,
      y0=perf_top,
      x1=-0.7,
      y1=perf_bot,
      fillcolor="#E53E3E",
      line=dict(color="#9B2C2C"),
  )
  fig.add_shape(
      type="rect",
      x0=0.7,
      y0=perf_top,
      x1=0.9,
      y1=perf_bot,
      fillcolor="#E53E3E",
      line=dict(color="#9B2C2C"),
  )

  for y_p in np.linspace(perf_top + 30, perf_bot - 30, 2):
    fig.add_annotation(
        x=-0.7,
        y=y_p,
        ax=-1.0,
        ay=y_p,
        showarrow=True,
        arrowhead=2,
        arrowcolor="#E53E3E",
    )
    fig.add_annotation(
        x=0.7,
        y=y_p,
        ax=1.0,
        ay=y_p,
        showarrow=True,
        arrowhead=2,
        arrowcolor="#E53E3E",
    )

  # Tubing
  fig.add_shape(
      type="rect",
      x0=-0.15,
      y0=0,
      x1=0.15,
      y1=psd_d,
      fillcolor="#718096",
      line=dict(color="#2D3748"),
  )

  # ESP Rangkaian
  pump_h, intake_h, prot_h, motor_h, gauge_h = 300, 150, 150, 400, 100

  p_top = psd_d
  p_bot = p_top + pump_h
  fig.add_shape(
      type="rect",
      x0=-0.3,
      y0=p_top,
      x1=0.3,
      y1=p_bot,
      fillcolor="#3182CE",
      line=dict(color="#1A365D", width=1.5),
  )
  fig.add_annotation(
      x=0,
      y=(p_top + p_bot) / 2,
      text="PUMP",
      showarrow=False,
      font=dict(color="white", size=8, family="Arial Black"),
  )

  i_top = p_bot
  i_bot = i_top + intake_h
  fig.add_shape(
      type="rect",
      x0=-0.28,
      y0=i_top,
      x1=0.28,
      y1=i_bot,
      fillcolor="#DD6B20",
      line=dict(color="#7B341E", width=1.5),
  )
  fig.add_annotation(
      x=0,
      y=(i_top + i_bot) / 2,
      text="INK",
      showarrow=False,
      font=dict(color="white", size=7),
  )

  pr_top = i_bot
  pr_bot = pr_top + prot_h
  fig.add_shape(
      type="rect",
      x0=-0.25,
      y0=pr_top,
      x1=0.25,
      y1=pr_bot,
      fillcolor="#D69E2E",
      line=dict(color="#744210", width=1.5),
  )

  m_top = pr_bot
  m_bot = m_top + motor_h

  temp_num = temp_val if pd.notnull(temp_val) else 0
  motor_color = (
      "#E53E3E"
      if temp_num > 115
      else ("#DD6B20" if temp_num > 105 else "#38A169")
  )
  fig.add_shape(
      type="rect",
      x0=-0.28,
      y0=m_top,
      x1=0.28,
      y1=m_bot,
      fillcolor=motor_color,
      line=dict(color="#1A202C", width=1.5),
  )
  fig.add_annotation(
      x=0,
      y=(m_top + m_bot) / 2,
      text="MTR",
      showarrow=False,
      font=dict(color="white", size=8, family="Arial Black"),
  )

  g_top = m_bot
  g_bot = g_top + gauge_h
  fig.add_shape(
      type="rect",
      x0=-0.2,
      y0=g_top,
      x1=0.2,
      y1=g_bot,
      fillcolor="#805AD5",
      line=dict(color="#44337A", width=1.5),
  )

  fig.add_trace(
      go.Scatter(
          x=[0.35, 0.35, 0.3],
          y=[0, m_top, m_top],
          mode="lines",
          line=dict(color="#E53E3E", width=2),
          showlegend=False,
          hoverinfo="none",
      )
  )

  fig.add_annotation(
      x=-0.3,
      y=p_top,
      ax=-1.1,
      ay=p_top,
      text=f"PSD:{psd_d:.0f}'",
      showarrow=True,
      arrowhead=1,
      arrowcolor="#2B6CB0",
      font=dict(size=9, color="#2B6CB0"),
  )

  temp_text = f"{temp_val:.0f}°C" if pd.notnull(temp_val) else "N/A"
  fig.add_annotation(
      x=-0.28,
      y=(m_top + m_bot) / 2,
      ax=-1.1,
      ay=(m_top + m_bot) / 2,
      text=temp_text,
      showarrow=True,
      arrowhead=1,
      arrowcolor=motor_color,
      font=dict(size=9, color=motor_color),
  )

  fig.update_layout(
      title=dict(
          text="🎨 ESP Schematic", x=0.5, xanchor="center", font=dict(size=12)
      ),
      xaxis=dict(
          range=[-1.4, 1.4],
          showgrid=False,
          zeroline=False,
          showticklabels=False,
      ),
      yaxis=dict(range=[max_d + 100, -100], showgrid=True, title="Depth (ft)"),
      height=360,
      margin=dict(l=5, r=5, t=30, b=10),
      showlegend=False,
      paper_bgcolor="rgba(0,0,0,0)",
      plot_bgcolor="rgba(0,0,0,0)",
      autosize=True,
      # Konfigurasi dragmode bawaan pan / zoom
      dragmode="pan",
  )

  return fig


# Configurations Plotly Config (Menampilkan Tombol Zoom, Reset View, dll.)
PLOTLY_CONFIG = {
    "displayModeBar": True,
    "displaylogo": False,
    "scrollZoom": True,
    "modeBarButtonsToAdd": ["drawline", "drawopenpath", "eraseshape"],
    "modeBarButtonsToRemove": [],
    "toImageButtonOptions": {
        "format": "png",
        "filename": "esp_dashboard_export",
    },
}

# ==========================================
# 5. TAMPILAN DASHBOARD & LOGIKA RESPONSIVE LAYOUT
# ==========================================
if all_wells_data:
  selected_well = st.sidebar.selectbox(
      "Pilih Sumur ESP:", list(all_wells_data.keys())
  )

  current_depths = st.session_state["well_depth_params"].get(
      selected_well,
      {"casing": 6000.0, "psd": 4500.0, "perf_top": 5000.0, "perf_bot": 5200.0},
  )

  st.sidebar.markdown("---")
  st.sidebar.header(f"⚙️ Input Kedalaman Sumur ({selected_well})")

  casing_depth_input = st.sidebar.number_input(
      "Casing / Total Depth (ft)",
      value=float(current_depths["casing"]),
      step=100.0,
      key=f"casing_{selected_well}",
  )
  pump_depth_input = st.sidebar.number_input(
      "Pump Setting Depth / PSD (ft)",
      value=float(current_depths["psd"]),
      step=50.0,
      key=f"psd_{selected_well}",
  )
  perf_top_input = st.sidebar.number_input(
      "Top Perforation Depth (ft)",
      value=float(current_depths["perf_top"]),
      step=50.0,
      key=f"perftop_{selected_well}",
  )
  perf_bot_input = st.sidebar.number_input(
      "Bottom Perforation Depth (ft)",
      value=float(current_depths["perf_bot"]),
      step=50.0,
      key=f"perfbot_{selected_well}",
  )

  st.session_state["well_depth_params"][selected_well] = {
      "casing": casing_depth_input,
      "psd": pump_depth_input,
      "perf_top": perf_top_input,
      "perf_bot": perf_bot_input,
  }

  df_well = all_wells_data[selected_well]
  latest_data = df_well.iloc[-1]

  st.subheader(
      f"📊 Status Terakhir: {selected_well}"
      f" ({latest_data['Date'].strftime('%d-%b-%Y')})"
  )

  c_left_schematic, c_right_metrics = st.columns([1, 2.2])

  temp_val = latest_data["Motor_Temp_C"]
  vib_val = latest_data["Vibration_G"]
  pi_val = latest_data["PI_PSI"]
  pd_val = latest_data["PD_PSI"]
  wc_val = latest_data["Water_Cut_Percent"]

  with c_left_schematic:
    fig_sch = create_esp_schematic_dynamic(
        temp_val,
        vib_val,
        pi_val,
        pd_val,
        casing_depth_input,
        pump_depth_input,
        perf_top_input,
        perf_bot_input,
    )

    st.plotly_chart(
        fig_sch,
        use_container_width=True,
        config=PLOTLY_CONFIG,
        key=f"sch_plot_{st.session_state['reset_sch_key']}",
    )

    # Tombol Reset View khusus Skematik
    if st.button("🔄 Reset Zoom Skematik", key="btn_reset_sch"):
      st.session_state["reset_sch_key"] += 1
      st.rerun()

  with c_right_metrics:
    st.markdown("### 📈 Ringkasan Parameter")

    # Metrics 4 Kolom di Rapat dalam Layar Tablet
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    m_col1.metric("Oil Rate", f"{latest_data['Oil_Rate_BOPD']:.1f}", "BOPD")
    m_col2.metric("Water Rate", f"{latest_data['Water_Rate_BWPD']:.1f}", "BWPD")
    m_col3.metric("Water Cut", f"{latest_data['Water_Cut_Percent']:.1f}", "%")
    m_col4.metric("Gas Rate", f"{latest_data['Gas_Rate_MSCFD']:.1f}", "MCFD")

    st.markdown("<hr style='margin: 4px 0px;'>", unsafe_allow_html=True)

    m_col5, m_col6, m_col7, m_col8 = st.columns(4)
    m_col5.metric("Pump Intake", f"{latest_data['PI_PSI']:.1f}", "PSI")
    m_col6.metric("Discharge", f"{latest_data['PD_PSI']:.1f}", "PSI")
    m_col7.metric("Frequency", f"{latest_data['Frequency_Hz']:.1f}", "Hz")
    temp_disp = f"{temp_val:.1f}" if pd.notnull(temp_val) else "-"
    m_col8.metric("Motor Temp", temp_disp, "°C")

    st.markdown("<hr style='margin: 4px 0px;'>", unsafe_allow_html=True)

    issues, warnings = [], []
    if pd.notnull(temp_val):
      if temp_val > 115:
        issues.append(
            f"🔥 **Overheating**: Temperatur motor tinggi ({temp_val:.1f} °C)."
        )
      elif temp_val > 105:
        warnings.append(
            f"⚠️ **Warning Temp**: Temperatur mendekati limit"
            f" ({temp_val:.1f} °C)."
        )

    if pd.notnull(vib_val):
      if vib_val > 2.5:
        issues.append(
            f"🚨 **High Vibration**: Vibrasi berlebih ({vib_val:.2f} G)."
        )
      elif vib_val > 1.8:
        warnings.append(
            f"⚠️ **Warning Vibrasi**: Vibrasi tinggi ({vib_val:.2f} G)."
        )

    if pi_val < 200 and pi_val > 0:
      warnings.append(
          f"⚠️ **Low Intake Pressure**: PI rendah ({pi_val:.1f} PSI)."
      )

    if wc_val > 90:
      warnings.append(
          f"💧 **High Water Cut**: Air sangat tinggi ({wc_val:.1f}%)."
      )

    if not issues and not warnings:
      st.success("✅ **Performa Normal**: Tidak terdeteksi anomali pada sumur.")
    else:
      for iss in issues:
        st.error(iss)
      for warn in warnings:
        st.warning(warn)

  st.markdown("---")

  # Layout Grafik Bawah
  col_graph, col_anim = st.columns([1, 1])

  with col_graph:
    c_title1, c_btn1 = st.columns([2.5, 1])
    with c_title1:
      st.subheader("📈 Tren Produksi")
    with c_btn1:
      if st.button("🔄 Reset Zoom", key="btn_reset_prod"):
        st.session_state["reset_prod_key"] += 1
        st.rerun()

    selected_prod = st.multiselect(
        "Pilih Parameter Produksi:",
        options=["Oil Rate (BOPD)", "Water Rate (BWPD)", "Gas Rate (MCFD)"],
        default=["Oil Rate (BOPD)", "Water Rate (BWPD)", "Gas Rate (MCFD)"],
        key=f"prod_select_{selected_well}",
    )

    fig_prod = go.Figure()
    if "Oil Rate (BOPD)" in selected_prod:
      fig_prod.add_trace(
          go.Scatter(
              x=df_well["Date"],
              y=df_well["Oil_Rate_BOPD"],
              mode="lines+markers",
              name="Oil Rate",
              line=dict(color="green", width=2),
          )
      )
    if "Water Rate (BWPD)" in selected_prod:
      fig_prod.add_trace(
          go.Scatter(
              x=df_well["Date"],
              y=df_well["Water_Rate_BWPD"],
              mode="lines+markers",
              name="Water Rate",
              line=dict(color="blue", width=2),
          )
      )
    if "Gas Rate (MCFD)" in selected_prod:
      fig_prod.add_trace(
          go.Scatter(
              x=df_well["Date"],
              y=df_well["Gas_Rate_MSCFD"],
              mode="lines+markers",
              name="Gas Rate",
              yaxis="y2",
              line=dict(color="red", width=2, dash="dash"),
          )
      )

    fig_prod.update_layout(
        title=f"Produksi - {selected_well}",
        xaxis=dict(title="Tanggal"),
        yaxis=dict(title="Liquid/Oil/Water (STB/D)"),
        yaxis2=dict(
            title="Gas (MCFD)", overlaying="y", side="right", showgrid=False
        ),
        legend=dict(
            orientation="h", yanchor="top", y=-0.22, xanchor="center", x=0.5
        ),
        margin=dict(l=15, r=15, t=35, b=55),
        autosize=True,
    )
    st.plotly_chart(
        fig_prod,
        use_container_width=True,
        config=PLOTLY_CONFIG,
        key=f"prod_plot_{st.session_state['reset_prod_key']}",
    )

  with col_anim:
    c_title2, c_btn2 = st.columns([2.5, 1])
    with c_title2:
      st.subheader("📉 Downhole Monitoring")
    with c_btn2:
      if st.button("🔄 Reset Zoom", key="btn_reset_dh"):
        st.session_state["reset_dh_key"] += 1
        st.rerun()

    selected_dh = st.multiselect(
        "Pilih Parameter Downhole:",
        options=[
            "Pump Intake (PI)",
            "Pump Discharge (PD)",
            "Motor Temp (°C)",
            "Vibration (G)",
        ],
        default=[
            "Pump Intake (PI)",
            "Pump Discharge (PD)",
            "Motor Temp (°C)",
            "Vibration (G)",
        ],
        key=f"dh_select_{selected_well}",
    )

    fig_dh = go.Figure()
    if "Pump Intake (PI)" in selected_dh:
      fig_dh.add_trace(
          go.Scatter(
              x=df_well["Date"],
              y=df_well["PI_PSI"],
              mode="lines+markers",
              name="PI (PSI)",
              line=dict(color="darkorange", width=2),
          )
      )
    if "Pump Discharge (PD)" in selected_dh:
      fig_dh.add_trace(
          go.Scatter(
              x=df_well["Date"],
              y=df_well["PD_PSI"],
              mode="lines+markers",
              name="PD (PSI)",
              line=dict(color="purple", width=2),
          )
      )
    if "Motor Temp (°C)" in selected_dh:
      fig_dh.add_trace(
          go.Scatter(
              x=df_well["Date"],
              y=df_well["Motor_Temp_C"],
              mode="lines+markers",
              name="Temp (°C)",
              yaxis="y2",
              line=dict(color="crimson", width=2, dash="dash"),
          )
      )
    if "Vibration (G)" in selected_dh:
      fig_dh.add_trace(
          go.Scatter(
              x=df_well["Date"],
              y=df_well["Vibration_G"],
              mode="lines+markers",
              name="Vib (G)",
              yaxis="y2",
              line=dict(color="teal", width=2, dash="dot"),
          )
      )

    fig_dh.update_layout(
        title=f"Downhole Health - {selected_well}",
        xaxis=dict(title="Tanggal"),
        yaxis=dict(title="Tekanan (PSI)"),
        yaxis2=dict(
            title="Temp/Vib", overlaying="y", side="right", showgrid=False
        ),
        legend=dict(
            orientation="h", yanchor="top", y=-0.22, xanchor="center", x=0.5
        ),
        margin=dict(l=15, r=15, t=35, b=55),
        autosize=True,
    )
    st.plotly_chart(
        fig_dh,
        use_container_width=True,
        config=PLOTLY_CONFIG,
        key=f"dh_plot_{st.session_state['reset_dh_key']}",
    )
