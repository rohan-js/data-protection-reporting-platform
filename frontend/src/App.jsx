import React, { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Download, FileText, RefreshCw, ShieldAlert, UserRoundCheck } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api, fetchDashboard } from './api/client.js';

const severityClass = {
  CRITICAL: 'critical',
  HIGH: 'high',
  MEDIUM: 'medium',
  LOW: 'low',
};

function App() {
  const [view, setView] = useState('dashboard');
  const [dashboard, setDashboard] = useState(null);
  const [events, setEvents] = useState([]);
  const [anomalies, setAnomalies] = useState([]);
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  async function loadAll() {
    setLoading(true);
    setMessage('');
    try {
      const [dash, eventRows, anomalyRows, reportRows] = await Promise.all([
        fetchDashboard(),
        api.get('/events?limit=200'),
        api.get('/anomalies?limit=200'),
        api.get('/reports'),
      ]);
      setDashboard(dash);
      setEvents(eventRows.data);
      setAnomalies(anomalyRows.data);
      setReports(reportRows.data);
    } catch (error) {
      setMessage(error.response?.data?.detail || error.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
  }, []);

  async function ingest() {
    setLoading(true);
    setMessage('Ingestion started');
    try {
      const response = await api.post('/ingest');
      setMessage(`Ingested ${response.data.events} events, ${response.data.credentials} credentials, ${response.data.findings} findings`);
      await loadAll();
    } catch (error) {
      setMessage(error.response?.data?.detail || error.message);
    } finally {
      setLoading(false);
    }
  }

  async function generateReport(type) {
    setLoading(true);
    try {
      const response = await api.post('/reports/generate', { report_type: type });
      setMessage(`${type} report generated`);
      setReports((current) => [response.data, ...current]);
    } catch (error) {
      setMessage(error.response?.data?.detail || error.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="shell">
      <aside className="nav">
        <div className="brand">
          <ShieldAlert size={28} />
          <span>Data Protection</span>
        </div>
        {['dashboard', 'events', 'anomalies', 'identities', 'findings', 'reports'].map((item) => (
          <button key={item} className={view === item ? 'active' : ''} onClick={() => setView(item)}>
            {item}
          </button>
        ))}
      </aside>
      <main>
        <header className="topbar">
          <div>
            <h1>Cloud Identity Reporting</h1>
            <p>AWS CloudTrail, IAM credential report, and external Access Analyzer findings</p>
          </div>
          <div className="actions">
            <button onClick={loadAll} disabled={loading} title="Refresh dashboard">
              <RefreshCw size={16} /> Refresh
            </button>
            <button onClick={ingest} disabled={loading} title="Run AWS ingestion">
              <Download size={16} /> Ingest
            </button>
          </div>
        </header>
        {message && <div className="notice">{message}</div>}
        {view === 'dashboard' && <Dashboard data={dashboard} anomalies={anomalies} />}
        {view === 'events' && <Events rows={events} />}
        {view === 'anomalies' && <Anomalies rows={anomalies} />}
        {view === 'identities' && <Identities rows={dashboard?.identities || []} />}
        {view === 'findings' && <Findings rows={dashboard?.findings || []} />}
        {view === 'reports' && <Reports rows={reports} onGenerate={generateReport} />}
      </main>
    </div>
  );
}

function Dashboard({ data, anomalies }) {
  const chartData = useMemo(() => {
    const byHour = data?.events?.by_hour || {};
    return Object.entries(byHour).slice(-24).map(([hour, count]) => ({ hour: hour.slice(11), count }));
  }, [data]);

  return (
    <section className="stack">
      <div className="kpis">
        <Kpi icon={<FileText />} label="Total Events" value={data?.events?.total || 0} />
        <Kpi icon={<AlertTriangle />} label="Open Anomalies" value={data?.anomalies?.total_open || 0} />
        <Kpi icon={<UserRoundCheck />} label="High-Risk Identities" value={(data?.identities || []).filter((item) => item.risk_score >= 70).length} />
        <Kpi icon={<ShieldAlert />} label="Active Findings" value={(data?.findings || []).filter((item) => item.status === 'ACTIVE').length} />
      </div>
      <div className="panel">
        <h2>Activity by Hour</h2>
        <div className="chart">
          <ResponsiveContainer>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="hour" />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Bar dataKey="count" fill="#2f6f73" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
      <Anomalies rows={anomalies.slice(0, 10)} compact />
    </section>
  );
}

function Kpi({ icon, label, value }) {
  return (
    <div className="kpi">
      <div className="kpiIcon">{icon}</div>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
      </div>
    </div>
  );
}

function Events({ rows }) {
  return (
    <Table
      title="CloudTrail Events"
      rows={rows}
      columns={[
        ['event_time', 'Time'],
        ['event_name', 'Event'],
        ['subject', 'Identity'],
        ['source_ip', 'Source IP'],
        ['error_code', 'Error'],
      ]}
    />
  );
}

function Anomalies({ rows, compact = false }) {
  return (
    <div className="panel">
      <h2>{compact ? 'Recent Anomalies' : 'Anomaly Feed'}</h2>
      <div className="feed">
        {rows.length === 0 && <div className="empty">No anomalies stored yet.</div>}
        {rows.map((item) => (
          <article key={`${item.id}-${item.anomaly_type}`} className={`anomaly ${severityClass[item.severity] || 'low'}`}>
            <div>
              <span className="badge">{item.severity}</span>
              <strong>{item.anomaly_type}</strong>
            </div>
            <p>{item.description}</p>
            <small>{item.subject}</small>
          </article>
        ))}
      </div>
    </div>
  );
}

function Identities({ rows }) {
  return (
    <Table
      title="IAM Risk Rankings"
      rows={rows}
      columns={[
        ['name', 'Identity'],
        ['type', 'Type'],
        ['risk_score', 'Risk'],
        ['mfa_enabled', 'MFA'],
        ['access_key_age_days', 'Key Age'],
        ['last_activity', 'Last Activity'],
      ]}
    />
  );
}

function Findings({ rows }) {
  return (
    <Table
      title="Access Analyzer Findings"
      rows={rows}
      columns={[
        ['status', 'Status'],
        ['severity', 'Severity'],
        ['resource_type', 'Type'],
        ['resource_arn', 'Resource'],
        ['updated_at', 'Updated'],
      ]}
    />
  );
}

function Reports({ rows, onGenerate }) {
  return (
    <div className="panel">
      <div className="panelHeader">
        <h2>Reports</h2>
        <div className="actions">
          <button onClick={() => onGenerate('PDF')}>PDF</button>
          <button onClick={() => onGenerate('CSV')}>CSV</button>
        </div>
      </div>
      <Table
        rows={rows}
        columns={[
          ['generated_at', 'Generated'],
          ['report_type', 'Type'],
          ['id', 'Report ID'],
        ]}
        renderAction={(row) => (
          <a href={`/api/reports/download/${row.id}`} className="download">
            Download
          </a>
        )}
      />
    </div>
  );
}

function Table({ title, rows, columns, renderAction }) {
  return (
    <div className="panel">
      {title && <h2>{title}</h2>}
      <div className="tableWrap">
        <table>
          <thead>
            <tr>
              {columns.map(([, label]) => (
                <th key={label}>{label}</th>
              ))}
              {renderAction && <th>Action</th>}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan={columns.length + (renderAction ? 1 : 0)}>No data stored yet.</td>
              </tr>
            )}
            {rows.map((row, index) => (
              <tr key={row.id || index}>
                {columns.map(([field]) => (
                  <td key={field}>{formatValue(row[field])}</td>
                ))}
                {renderAction && <td>{renderAction(row)}</td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function formatValue(value) {
  if (value === null || value === undefined || value === '') return '-';
  if (value === 1) return 'yes';
  if (value === 0) return 'no';
  return String(value);
}

export default App;
