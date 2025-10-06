import streamlit as st
from modules import gastos_reportes, gastos_pendientes

# Configuración de la página
st.set_page_config(
    page_title="Admin Panel - Gastos",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configuración de navegación
def main():
    # Título principal
    st.markdown("""
    <div style='text-align: center; margin-bottom: 2rem;'>
        <h1 style='color: #1f4e79; margin: 0;'>💼 Panel Administrativo</h1>
        <p style='color: #666; font-size: 1.1em; margin: 0.5rem 0;'>Sistema de Gestión de Gastos</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Definir las páginas
    pages = {
        "📊 Reportes de Gastos": gastos_reportes,
        "⏳ Gastos Pendientes": gastos_pendientes,
    }
    
    # Crear navegación en sidebar
    st.sidebar.markdown("### 🧭 Navegación")
    
    # Selector de página
    selected_page = st.sidebar.radio(
        "Seleccionar sección:",
        options=list(pages.keys()),
        index=0,
        key="navigation"
    )
    
    # Información adicional en sidebar
    st.sidebar.markdown("---")
    st.sidebar.markdown("### ℹ️ Información")
    st.sidebar.info(
        "**¿Cómo usar el panel?**\n\n"
        "1. **Reportes de Gastos**: \n"
        "   - Filtra por mes, obra y empresa\n"
        "   - Descarga reportes en Excel\n"
        "    - Ve totales por categoría\n\n"
        "2. **Gastos Pendientes**:\n"
        "   - Revisa gastos esperando aprobación\n"
        "   - Aprueba o rechaza gastos\n"
        "   - Ve detalles completos \n"
    )
    
    # Ejecutar la página seleccionada
    try:
        pages[selected_page].show()
    except Exception as e:
        st.error(f"Error al cargar la página: {str(e)}")
        st.info("Por favor, contacta al administrador del sistema.")

if __name__ == "__main__":
    main()