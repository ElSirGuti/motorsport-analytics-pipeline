const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

import axios from 'axios';

const apiClient = axios.create({
  baseURL: API_URL,
  timeout: 60000,
});

function extractErrorMessage(error) {
  if (error.response) {
    return error.response.data?.detail || `Error del servidor: ${error.response.status}`;
  }
  if (error.request) {
    return 'No se pudo conectar con el servidor. Verifica que la API esté corriendo.';
  }
  return error.message || 'Error desconocido';
}

export const compareLaps = async (lapA, lapB) => {
  const formData = new FormData();
  formData.append('lap_a', lapA);
  formData.append('lap_b', lapB);

  try {
    const response = await apiClient.post('/compare-laps', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  } catch (error) {
    throw new Error(extractErrorMessage(error), { cause: error });
  }
};

export const analyzeSession = async (sessionFile) => {
  const formData = new FormData();
  formData.append('session_file', sessionFile);

  try {
    const response = await apiClient.post('/analyze-session', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  } catch (error) {
    throw new Error(extractErrorMessage(error), { cause: error });
  }
};
