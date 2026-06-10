import axios from 'axios';

// Configurar el cliente base de axios
// Si el frontend está en el mismo host que el backend, esto usará el puerto correcto
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

const apiClient = axios.create({
  baseURL: API_URL,
  timeout: 60000, // 60 segundos (el análisis puede tomar unos segundos)
});

/**
 * Sube dos archivos de telemetría (lap A y lap B) para ser comparados.
 * 
 * @param {File} lapA - Archivo CSV de la vuelta de referencia.
 * @param {File} lapB - Archivo CSV de la vuelta a comparar.
 * @returns {Promise<Object>} Resultado del análisis de telemetría.
 */
export const compareLaps = async (lapA, lapB) => {
  try {
    const formData = new FormData();
    formData.append('lap_a', lapA);
    formData.append('lap_b', lapB);

    const response = await apiClient.post('/compare-laps', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });

    return response.data;
  } catch (error) {
    console.error('Error al comparar las vueltas:', error);
    
    // Mejorar el manejo de errores
    if (error.response) {
      // El servidor respondió con un código de estado fuera del rango 2xx
      throw new Error(error.response.data.detail || `Error del servidor: ${error.response.status}`);
    } else if (error.request) {
      // La petición fue hecha pero no hubo respuesta
      throw new Error('No se pudo conectar con el servidor. Verifica que la API esté corriendo.');
    } else {
      // Algo pasó al configurar la petición
      throw new Error(`Error en la solicitud: ${error.message}`);
    }
  }
};

/**
 * Sube un archivo de telemetría de una sesión completa.
 * 
 * @param {File} sessionFile - Archivo CSV de la sesión.
 * @returns {Promise<Object>} Resultado del análisis de la sesión.
 */
export const analyzeSession = async (sessionFile) => {
  try {
    const formData = new FormData();
    formData.append('session_file', sessionFile);

    const response = await apiClient.post('/analyze-session', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });

    return response.data;
  } catch (error) {
    console.error('Error al analizar la sesión:', error);
    
    if (error.response) {
      throw new Error(error.response.data.detail || `Error del servidor: ${error.response.status}`);
    } else if (error.request) {
      throw new Error('No se pudo conectar con el servidor. Verifica que la API esté corriendo.');
    } else {
      throw new Error(`Error en la solicitud: ${error.message}`);
    }
  }
};
