import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
const client = axios.create({ baseURL: API_URL, timeout: 600000 });

/**
 * Optimal lap by microsectors for a full session CSV.
 * Runs in the background after the session analysis; pass an AbortSignal to cancel.
 */
export const analyzeOptimalLap = async (sessionFile, lang = 'en', { microsectorM = 25, signal } = {}) => {
  const formData = new FormData();
  formData.append('session_file', sessionFile);
  formData.append('microsector_m', String(microsectorM));
  try {
    const response = await client.post('/optimal-lap', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      params: { lang },
      signal,
    });
    return response.data;
  } catch (error) {
    if (axios.isCancel(error)) throw error;
    const detail = error.response?.data?.detail;
    throw new Error(
      typeof detail === 'string' ? detail : (error.message || 'Error'),
      { cause: error },
    );
  }
};

export const isCancelled = (error) => axios.isCancel(error);
