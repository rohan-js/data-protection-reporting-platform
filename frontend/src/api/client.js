import axios from 'axios';

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 30000,
});

export async function fetchDashboard() {
  const [events, anomalies, identities, findings] = await Promise.all([
    api.get('/events/summary'),
    api.get('/anomalies/summary'),
    api.get('/identities/risk'),
    api.get('/findings'),
  ]);
  return {
    events: events.data,
    anomalies: anomalies.data,
    identities: identities.data,
    findings: findings.data,
  };
}

