import streamlit as st
import pandas as pd
import tempfile
import requests
from io import BytesIO
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl import Workbook

def show():
    st.title("📊 Reportes de Gastos por Obra y Empresa")
    
    # Configuraciones
    GOOGLE_SHEET_ID = "1-QhFEYbNl_rlkLjvEuhj3TfyaOPNrKdU2AVC4KPDfP0"
    export_url = f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/export?format=xlsx"

    def cargar_datos():
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            try:
                response = requests.get(export_url)
                response.raise_for_status()
                tmp_file.write(response.content)
                uploaded_file = tmp_file.name
            except Exception as e:
                st.error(f"Error al descargar el archivo: {e}")
                return None

        try:
            sheets = pd.read_excel(uploaded_file, sheet_name=None)
        except Exception as e:
            st.error(f"Error al cargar el archivo: {e}")
            return None
        
        df = pd.concat([df.assign(Obra=sheet) for sheet, df in sheets.items()], ignore_index=True, sort=False)
        
        # LIMPIEZA AUTOMÁTICA: Detectar y remover filas de totales
        monto_col = next((c for c in df.columns if "monto" in c.lower() or "importe" in c.lower()), None)
        
        if monto_col:
            # Limpiar datos: convertir "nan" strings a NaN reales
            for col in df.columns:
                if col != monto_col:  # No tocar la columna de monto
                    df[col] = df[col].replace(['nan', 'NaN', 'NAN', ''], pd.NA)
            
            # Identificar filas que probablemente sean totales
            cols_datos = [col for col in df.columns if col not in ['Obra', monto_col]]
            
            if cols_datos:
                # Mask para filas donde todos los campos de datos están vacíos pero hay monto
                mask_totales = df[cols_datos].isna().all(axis=1) & df[monto_col].notna()
                filas_totales = df[mask_totales]
                
                if not filas_totales.empty:
                    print(f"🔍 DETECTADAS {len(filas_totales)} FILAS DE TOTALES - REMOVIENDO AUTOMÁTICAMENTE")
                    print("Filas removidas:")
                    for idx, row in filas_totales.iterrows():
                        obra = row['Obra'] if 'Obra' in row and pd.notna(row['Obra']) else 'N/A'
                        monto = row[monto_col] if pd.notna(row[monto_col]) else 0
                        print(f"  - Fila {idx}: Obra: {obra}, Monto: ${monto:,.2f}")
                    
                    # Remover las filas de totales automáticamente
                    df = df[~mask_totales].reset_index(drop=True)
                    print(f"✅ Dataset limpio: {len(df)} filas restantes")
                else:
                    print("ℹ️  No se detectaron filas de totales obvias")
                    
            # DETECCIÓN ADICIONAL: Buscar filas con montos sospechosamente altos
            if len(df) > 0 and monto_col in df.columns:
                # Calcular estadísticas del monto
                montos_validos = df[monto_col].dropna()
                if len(montos_validos) > 1:
                    percentil_95 = montos_validos.quantile(0.95)
                    promedio = montos_validos.mean()
                    
                    # Buscar montos que sean mucho más altos que el resto (posibles totales)
                    threshold = max(percentil_95 * 3, promedio * 10)  # 3 veces el percentil 95 o 10 veces el promedio
                    
                    mask_montos_altos = df[monto_col] > threshold
                    filas_montos_altos = df[mask_montos_altos]
                    
                    if not filas_montos_altos.empty:
                        print(f"⚠️  DETECTADOS {len(filas_montos_altos)} MONTOS SOSPECHOSAMENTE ALTOS:")
                        
                        # Lista de indicadores de filas de totales
                        indicadores_total = ['total', 'suma', 'subtotal', 'gran total', 'total general', 'resumen']
                        
                        filas_a_remover = []
                        
                        for idx, row in filas_montos_altos.iterrows():
                            monto = row[monto_col]
                            print(f"  - Fila {idx}: ${monto:,.2f} (Threshold: ${threshold:,.2f})")
                            
                            # Verificar si es una fila de total
                            es_total = False
                            for col in df.columns:
                                if col != monto_col and pd.notna(row[col]):
                                    valor_str = str(row[col]).lower().strip()
                                    if any(indicador in valor_str for indicador in indicadores_total):
                                        es_total = True
                                        print(f"    🎯 FILA DE TOTAL DETECTADA: '{col}' = '{row[col]}'")
                                        break
                            
                            if es_total:
                                filas_a_remover.append(idx)
                            else:
                                print(f"    ℹ️  Monto alto pero no parece fila de total")
                                print(f"    Datos: {dict(row)}")
                        
                        # Remover las filas de totales detectadas
                        if filas_a_remover:
                            print(f"🗑️  REMOVIENDO {len(filas_a_remover)} FILAS DE TOTALES AUTOMÁTICAMENTE")
                            df = df.drop(index=filas_a_remover).reset_index(drop=True)
                            print(f"✅ Dataset limpio: {len(df)} filas restantes")
                        else:
                            print("ℹ️  No se removieron filas (montos altos pero no parecen totales)")
        
        return df

    def convert_df_to_excel(df):
        """Convierte un DataFrame a formato Excel con formato profesional"""
        output = BytesIO()
        
        # Crear workbook y worksheet
        wb = Workbook()
        ws = wb.active
        ws.title = "Datos_Filtrados"
        
        # Escribir los datos
        for r in dataframe_to_rows(df, index=False, header=True):
            ws.append(r)
        
        # Agregar fila de total
        monto_col_name = next((c for c in df.columns if "monto" in c.lower() or "importe" in c.lower()), None)
        if monto_col_name:
            # Reemplazar NaN por 0 antes de sumar
            total_monto = df[monto_col_name].fillna(0).sum()
            
            # Crear fila de total
            total_row = [''] * len(df.columns)
            
            # Poner "TOTAL:" siempre en la primera columna
            total_row[0] = 'TOTAL:'
            
            # Buscar la posición de la columna de monto y poner el valor del total
            monto_col_index = df.columns.get_loc(monto_col_name)
            total_row[monto_col_index] = total_monto if pd.notnull(total_monto) else 0
            
            # Agregar la fila de total
            ws.append(total_row)
        
        # Aplicar estilos (código de estilos existente)
        # ... (mantener todo el código de estilos del archivo original)
        
        # Guardar en BytesIO
        wb.save(output)
        processed_data = output.getvalue()
        return processed_data

    # Estado de la aplicación
    if "df_reportes" not in st.session_state:
        with st.spinner("Cargando datos desde Google Sheets..."):
            st.session_state.df_reportes = cargar_datos()

    # Botón recargar
    col1, col2, col3 = st.columns([1, 1, 1])
    with col3:
        if st.button("🔄 Recargar datos", key="reload_reportes"):
            with st.spinner("Recargando datos..."):
                st.session_state.df_reportes = cargar_datos()
            st.success("Datos actualizados correctamente")
            st.rerun()

    df = st.session_state.df_reportes

    if df is not None:
        # Procesar datos
        fecha_col = next((c for c in df.columns if "fecha" in c.lower()), None)
        if fecha_col:
            df[fecha_col] = pd.to_datetime(df[fecha_col], dayfirst=True, errors='coerce')
        else:
            st.warning("No se encontró columna de fecha. Usa una hoja con columna 'Fecha'.")
        
        empresa_col = next((c for c in df.columns if "empresa" in c.lower()), None)
        if not empresa_col:
            st.warning("No se encontró columna de empresa. Usa una hoja con columna 'Empresa'.")
        
        # Filtros en columnas
        st.markdown("### 🔍 Filtros de Búsqueda")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if fecha_col:
                meses = df[fecha_col].dropna().dt.month.unique()
                meses = sorted(meses)
                opciones_meses = ["Todos los meses"] + [str(m) for m in meses]
                mes_seleccionado = st.selectbox("📅 Seleccionar mes", opciones_meses)
            else:
                mes_seleccionado = None
        
        with col2:
            obras = df['Obra'].dropna().unique()
            obra_seleccionada = st.selectbox("🏗️ Seleccionar obra", sorted(obras))
        
        with col3:
            if empresa_col:
                empresas = df[empresa_col].dropna().unique().tolist()
                empresas = ["Ambas empresas"] + sorted(empresas)
                empresa_seleccionada = st.selectbox("🏢 Seleccionar empresa", empresas, index=0)
            else:
                empresa_seleccionada = None
        
        # Aplicar filtros
        dt_filtrado = df.copy()
        
        if obra_seleccionada:
            dt_filtrado = dt_filtrado[dt_filtrado['Obra'] == obra_seleccionada]
        
        if empresa_col and empresa_seleccionada != "Ambas empresas":
            dt_filtrado = dt_filtrado[dt_filtrado[empresa_col] == empresa_seleccionada]
        
        if fecha_col and mes_seleccionado != "Todos los meses" and mes_seleccionado is not None:
            dt_filtrado = dt_filtrado[dt_filtrado[fecha_col].dt.month == int(mes_seleccionado)]

        # Mostrar resultados
        st.markdown("---")
        st.subheader(f"📋 {empresa_seleccionada} - {obra_seleccionada} - Mes {mes_seleccionado}")
        
        if dt_filtrado.empty:
            st.warning("⚠️ No se encontraron datos para los filtros seleccionados.")
        else:
            # Metrics
            monto_col = next((c for c in df.columns if "monto" in c.lower() or "importe" in c.lower()), None)
            if monto_col and not dt_filtrado.empty:
                total = dt_filtrado[monto_col].sum()
                cantidad_gastos = len(dt_filtrado)
                promedio = total / cantidad_gastos if cantidad_gastos > 0 else 0
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("💰 Total Gastos", f"$ {total:,.2f}")
                with col2:
                    st.metric("📊 Cantidad", cantidad_gastos)
                with col3:
                    st.metric("📈 Promedio", f"$ {promedio:,.2f}")
                with col4:
                    # Botón de descarga
                    excel_data = convert_df_to_excel(dt_filtrado)
                    filename = f"gastos_{empresa_seleccionada}_{obra_seleccionada}_mes_{mes_seleccionado}.xlsx"
                    st.download_button(
                        label="📥 Descargar Excel",
                        data=excel_data,
                        file_name=filename,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            
            # Mostrar tabla
            st.markdown("### 📋 Detalle de Gastos")
            df_display = dt_filtrado.copy()
            
            # Formatear montos
            if monto_col and monto_col in df_display.columns:
                df_display[monto_col] = df_display[monto_col].apply(lambda x: f"$ {x:,.2f}" if pd.notnull(x) else "")
            
            # Formatear fechas
            if fecha_col:
                df_display[fecha_col] = pd.to_datetime(df_display[fecha_col], errors='coerce').dt.strftime("%d/%m/%Y")

            df_display = df_display.astype(str)
            st.dataframe(df_display, use_container_width=True, hide_index=True)
    
    else:
        st.error("❌ No se pudo cargar el archivo automáticamente.")
        st.info("💡 Verifica la conexión a Google Sheets y la configuración del ID.")