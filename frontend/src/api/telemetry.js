const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

import axios from 'axios';

const apiClient = axios.create({
  baseURL: API_URL,
  timeout: 90000,
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

/**
 * Pipeline avanzado: geometría + Time Delta acumulado + sectorización.
 * Llama al endpoint POST /api/telemetry/compare
 */
export const compareAdvanced = async (lapFast, lapSlow, resolutionM = 5) => {
  const formData = new FormData();
  formData.append('lap_fast', lapFast);
  formData.append('lap_slow', lapSlow);
  formData.append('resolution_m', String(resolutionM));

  try {
    const response = await apiClient.post('/telemetry/compare', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  } catch (error) {
    throw new Error(extractErrorMessage(error), { cause: error });
  }
};

export const analyzeTelemetry = async (lapFast, lapSlow, resolutionM = 5) => {
  const formData = new FormData();
  formData.append('lap_fast', lapFast);
  formData.append('lap_slow', lapSlow);
  formData.append('resolution_m', String(resolutionM));

  try {
    const response = await apiClient.post('/telemetry/analyze', formData, {
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

export const analyzeStint = async (lapFiles) => {
  const formData = new FormData();
  lapFiles.forEach(f => formData.append('laps', f));
  try {
    const response = await apiClient.post('/stint/analyze', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000,
    });
    return response.data;
  } catch (error) {
    throw new Error(extractErrorMessage(error), { cause: error });
  }
};
