import React, { useEffect, useMemo, useState } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Float, Stars } from '@react-three/drei';
import * as THREE from 'three';

import {
  Activity,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  ClipboardCheck,
  FileScan,
  HeartPulse,
  LayoutDashboard,
  Menu,
  MessageCircle,
  Pill,
  Plus,
  Search,
  Settings,
  ShieldCheck,
  Stethoscope,
  Users,
  X,
  Loader2,
  Save,
  RefreshCw,
  LockKeyhole
} from 'lucide-react';

import {
  ResponsiveContainer,
  Tooltip,
  PieChart,
  Pie,
  Cell
} from 'recharts';

// ============================================================
// API CONNECTION
// ============================================================

const api = async (path, options = {}) => {
  const res = await fetch('/api' + path, {
    headers: {
      'Content-Type': 'application/json'
    },
    ...options
  });

  const body = await res.json().catch(() => ({}));

  if (!res.ok) {
    throw new Error(
      typeof body.detail === 'string'
        ? body.detail
        : 'Request failed'
    );
  }

  return body;
};

// ============================================================
// NAVIGATION
// ============================================================

const nav = [
  ['Dashboard', LayoutDashboard],
  ['New Assessment', Plus],
  ['Medication Review', Pill],
  ['AI Copilot', MessageCircle],
  ['Patient Records', Users],
  ['Analytics', Activity],
  ['Safety Center', ShieldCheck],
  ['Settings', Settings]
];

// ============================================================
// DEFAULT FORM
// ============================================================

const empty = {
  drug: 'Vancomycin',
  age: 58,
  weight: 75,
  sex: 'Male',
  creatinine: 2.4,
  dialysis: 'No',
  flow: 0,
  allergy: '',
  medications: '',
  infection: 'complicated',
  indication: 'Standard',
  infusion: 'Short_Infusion',
  label: ''
};

// ============================================================
// 3D KIDNEY MODEL
// ============================================================

function Kidney({ side = 1 }) {
  const geo = useMemo(() => {
    const g = new THREE.SphereGeometry(1, 52, 40);
    const p = g.attributes.position;

    for (let i = 0; i < p.count; i++) {
      const x = p.getX(i);
      const y = p.getY(i);
      const z = p.getZ(i);

      const dent =
        Math.exp(
          -((x + side * 0.73) ** 2) * 5 - y * y * 3
        ) * 0.35;

      p.setXYZ(
        i,
        (x + side * dent) * 0.73,
        y * 1.13,
        z * 0.63
      );
    }

    g.computeVertexNormals();

    return g;
  }, [side]);

  useEffect(() => {
    return () => geo.dispose();
  }, [geo]);

  return (
    <group
      position={[side * 1.05, 0.15, 0]}
      rotation={[0, side * 0.14, side * 0.18]}
    >
      <mesh geometry={geo}>
        <meshPhysicalMaterial
          color={side > 0 ? '#ee5e9b' : '#e95b9c'}
          roughness={0.23}
          metalness={0.15}
          transmission={0.24}
          thickness={1}
          transparent
          opacity={0.89}
          clearcoat={1}
          emissive="#64114e"
          emissiveIntensity={0.28}
        />
      </mesh>

      <mesh geometry={geo} scale={1.015}>
        <meshBasicMaterial
          color="#71eaff"
          wireframe
          transparent
          opacity={0.11}
        />
      </mesh>

      <mesh
        position={[-side * 0.32, 0.02, 0.43]}
        scale={[0.27, 0.58, 0.16]}
      >
        <sphereGeometry args={[1, 24, 16]} />
        <meshBasicMaterial
          color="#fcb0ce"
          transparent
          opacity={0.19}
        />
      </mesh>
    </group>
  );
}

// ============================================================
// FIX: USEFRAME INSIDE CANVAS
// ============================================================

function KidneyAnimation({ children }) {
  const groupRef = React.useRef(null);

  useFrame(({ clock }) => {
    if (groupRef.current) {
      groupRef.current.rotation.y =
        Math.sin(clock.elapsedTime * 0.35) * 0.22;
    }
  });

  return (
    <group ref={groupRef}>
      {children}
    </group>
  );
}

// ============================================================
// 3D SCENE
// ============================================================

function KidneyScene() {
  return (
    <Canvas
      camera={{
        position: [0, 0, 6.5],
        fov: 37
      }}
      gl={{
        alpha: true,
        antialias: true
      }}
    >
      <ambientLight intensity={1.35} />

      <pointLight
        position={[2, 4, 5]}
        color="#5cf6ff"
        intensity={80}
      />

      <pointLight
        position={[-4, -1, 3]}
        color="#f658c6"
        intensity={45}
      />

      <Stars
        radius={70}
        depth={15}
        count={240}
        factor={2}
        saturation={0}
        fade
        speed={0.4}
      />

      <KidneyAnimation>
        <Float
          speed={1.4}
          rotationIntensity={0.08}
          floatIntensity={0.25}
        >
          <Kidney side={-1} />
          <Kidney side={1} />

          <mesh position={[0, 0.55, 0]}>
            <cylinderGeometry args={[0.10, 0.10, 2.2, 20]} />
            <meshStandardMaterial
              color="#ff6796"
              emissive="#be1e5e"
              emissiveIntensity={0.4}
            />
          </mesh>

          <mesh position={[0.22, 0.55, 0.06]}>
            <cylinderGeometry args={[0.07, 0.07, 2.2, 20]} />
            <meshStandardMaterial
              color="#42c9ff"
              emissive="#1681bd"
              emissiveIntensity={0.6}
            />
          </mesh>

          <mesh
            position={[0, -0.63, 0.12]}
            rotation={[0, 0, Math.PI / 2]}
          >
            <torusGeometry args={[1.9, 0.015, 8, 100]} />
            <meshBasicMaterial
              color="#1cd5f4"
              transparent
              opacity={0.65}
            />
          </mesh>
        </Float>
      </KidneyAnimation>

      <OrbitControls
        enablePan={false}
        enableZoom={false}
        autoRotate
        autoRotateSpeed={0.45}
        minPolarAngle={Math.PI / 2.5}
        maxPolarAngle={Math.PI / 1.7}
      />
    </Canvas>
  );
}

// ============================================================
// STATUS UTILITIES
// ============================================================

const statusClass = (status = '') => {
  const value = String(status || '').toUpperCase();

  if (/BLOCK|ALERT|STOP/.test(value)) {
    return 'danger';
  }

  if (
    /REVIEW|MORE|UNAVAILABLE|UNSUPPORTED|BOUNDS/.test(value)
  ) {
    return 'warning';
  }

  return 'good';
};

// ============================================================
// CLINICAL RESULT DISPLAY
// ============================================================

function ClinicalResult({ result }) {
  if (!result) {
    return (
      <div className="placeholder">
        <Stethoscope size={35} />
        <p>No clinical result available.</p>
      </div>
    );
  }

  const hasRegimen = Boolean(result.drug);

  const monitoring = result.monitoring_plan || {};

  const therapyAlerts = Array.isArray(result.therapy_assessment)
    ? result.therapy_assessment
    : [];

  const commonMonitoring = Array.isArray(monitoring.common)
    ? monitoring.common
    : [];

  const drugMonitoring = Array.isArray(monitoring.drug_specific)
    ? monitoring.drug_specific
    : [];

  const reassessmentTriggers = Array.isArray(
    monitoring.reassessment_triggers
  )
    ? monitoring.reassessment_triggers
    : [];

  const rowStyle = {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: 15,
    padding: '11px 0',
    borderBottom: '1px solid rgba(255,255,255,0.08)'
  };

  const valueStyle = {
    color: '#e9faff',
    fontWeight: 600,
    textAlign: 'right',
    overflowWrap: 'anywhere'
  };

  const sectionStyle = {
    marginTop: 22,
    marginBottom: 12,
    color: '#39e6e6'
  };

  const alertStyle = {
    padding: 14,
    marginTop: 12,
    borderRadius: 12,
    background: 'rgba(255,184,107,0.08)',
    border: '1px solid rgba(255,184,107,0.25)'
  };

  const displayValue = (value, fallback = 'Not available') => {
    if (value === null || value === undefined || value === '') {
      return fallback;
    }

    return String(value);
  };

  return (
    <div
      className="result-message"
      style={{ lineHeight: 1.7 }}
    >
      {result.message && (
        <p>{result.message}</p>
      )}

      {hasRegimen && (
        <>
          <h3 style={sectionStyle}>
            💊 Selected Antibiotic Regimen
          </h3>

          <div style={rowStyle}>
            <span>Antibiotic</span>
            <span style={valueStyle}>
              {displayValue(result.drug)}
            </span>
          </div>

          <div style={rowStyle}>
            <span>Selected Dose</span>
            <span style={valueStyle}>
              {result.dose_mg != null
                ? `${result.dose_mg} mg`
                : result.dose != null
                  ? `${result.dose} ${result.dose_unit || 'mg'}`
                  : 'Not available'}
            </span>
          </div>

          <div style={rowStyle}>
            <span>Administration Route</span>
            <span style={valueStyle}>
              {displayValue(result.route)}
            </span>
          </div>

          <div style={rowStyle}>
            <span>Frequency</span>
            <span style={valueStyle}>
              {displayValue(result.frequency)}
            </span>
          </div>

          <div style={rowStyle}>
            <span>Dose Type</span>
            <span style={valueStyle}>
              {displayValue(result.dose_type)}
            </span>
          </div>

          <h3 style={sectionStyle}>
            🫘 Renal Assessment
          </h3>

          <div style={rowStyle}>
            <span>Creatinine Clearance Band</span>
            <span style={valueStyle}>
              {displayValue(result.crcl_band)}
            </span>
          </div>

          <div style={rowStyle}>
            <span>Weight Band</span>
            <span style={valueStyle}>
              {displayValue(result.weight_band)}
            </span>
          </div>

          <div style={rowStyle}>
            <span>Clinical Rule ID</span>
            <span style={valueStyle}>
              {displayValue(result.rule_id)}
            </span>
          </div>

          {result.note && (
            <div style={rowStyle}>
              <span>Rule Note</span>
              <span style={valueStyle}>
                {result.note}
              </span>
            </div>
          )}
        </>
      )}

      <h3
        style={{
          ...sectionStyle,
          color: '#ffb86b'
        }}
      >
        ⚠️ Clinical Safety
      </h3>

      <div
        style={{
          padding: 14,
          borderRadius: 12,
          background: 'rgba(255,184,107,0.08)',
          border: '1px solid rgba(255,184,107,0.25)'
        }}
      >
        <strong>
          Clinical Review:{' '}
          {result.clinical_review_required === true
            ? 'Required'
            : 'Verify with clinical protocol'}
        </strong>

        <p style={{ marginTop: 8 }}>
          The displayed regimen is a rule-engine output,
          not an approved prescription.
        </p>
      </div>

      {therapyAlerts.length > 0 && (
        <>
          <h3 style={sectionStyle}>
            Clinical Therapy Alerts
          </h3>

          {therapyAlerts.map((item, index) => (
            <div key={index} style={alertStyle}>
              <strong style={{ color: '#ffb86b' }}>
                {displayValue(item.category, 'Clinical Alert')}
              </strong>

              {item.severity && (
                <p>
                  <strong>Severity:</strong>{' '}
                  {item.severity}
                </p>
              )}

              {item.rule_id && (
                <p>
                  <strong>Rule:</strong>{' '}
                  {item.rule_id}
                </p>
              )}

              {item.trigger && (
                <p>
                  <strong>Trigger:</strong>{' '}
                  {item.trigger}
                </p>
              )}

              {item.rule && (
                <p>
                  <strong>Assessment:</strong>{' '}
                  {item.rule}
                </p>
              )}
            </div>
          ))}
        </>
      )}

      {(commonMonitoring.length > 0 ||
        drugMonitoring.length > 0) && (
        <>
          <h3 style={sectionStyle}>
            📈 Monitoring Plan
          </h3>

          {commonMonitoring.length > 0 && (
            <>
              <h4 style={{ marginTop: 14 }}>
                General Monitoring
              </h4>

              {commonMonitoring.map((item, index) => (
                <div key={index} style={alertStyle}>
                  <strong style={{ color: '#39e6e6' }}>
                    {displayValue(item.parameter)}
                  </strong>

                  <p>{displayValue(item.detail)}</p>
                </div>
              ))}
            </>
          )}

          {drugMonitoring.length > 0 && (
            <>
              <h4 style={{ marginTop: 18 }}>
                Drug-Specific Monitoring
              </h4>

              {drugMonitoring.map((item, index) => (
                <div key={index} style={alertStyle}>
                  <strong style={{ color: '#39e6e6' }}>
                    {displayValue(item.parameter)}
                  </strong>

                  <p>{displayValue(item.detail)}</p>
                </div>
              ))}
            </>
          )}
        </>
      )}

      {reassessmentTriggers.length > 0 && (
        <>
          <h3 style={sectionStyle}>
            🔄 Reassessment Triggers
          </h3>

          {reassessmentTriggers.map((item, index) => (
            <div key={index} style={alertStyle}>
              <strong style={{ color: '#ffb86b' }}>
                {displayValue(item.trigger)}
              </strong>

              <p>
                <strong>Required Action:</strong>{' '}
                {displayValue(item.action)}
              </p>
            </div>
          ))}
        </>
      )}

      {!result.message && !hasRegimen && (
        <p>
          Open Engine decision (JSON) to inspect
          the complete assessment.
        </p>
      )}

      <p
        style={{
          marginTop: 20,
          padding: 12,
          borderRadius: 10,
          background: 'rgba(255,184,107,0.08)',
          color: '#ffb86b',
          fontSize: 13
        }}
      >
        ⚠️ Research decision-support output only.
        Physician or pharmacist validation is required
        before prescribing or changing treatment.
      </p>
    </div>
  );
}

// ============================================================
// MAIN APPLICATION
// ============================================================

function App() {
  const [page, setPage] = useState('Dashboard');
  const [menu, setMenu] = useState(false);

  const [health, setHealth] = useState(null);
  const [cases, setCases] = useState([]);
  const [selected, setSelected] = useState(null);

  const [form, setForm] = useState(empty);
  const [assessment, setAssessment] = useState(null);

  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [search, setSearch] = useState('');

  const [messages, setMessages] = useState([]);
  const [chat, setChat] = useState('');

  const [apiKey, setApiKey] = useState('');
  const [model, setModel] = useState('openrouter/free');
  const [provider, setProvider] = useState('OpenRouter');

  // ==========================================================
  // LOAD DATA
  // ==========================================================

  const refresh = () => {
    api('/health')
      .then(setHealth)
      .catch(() => setHealth(null));

    api('/cases')
      .then(setCases)
      .catch(() => setCases([]));
  };

  useEffect(() => {
    refresh();
  }, []);

  // ==========================================================
  // FORM MANAGEMENT
  // ==========================================================

  const set = (name, value) => {
    setForm(previous => ({
      ...previous,
      [name]: value
    }));
  };

  const patient = () => {
    const dialysis = {
      status: form.dialysis === 'No' ? 'No' : 'Yes'
    };

    if (form.dialysis !== 'No') {
      dialysis.modality = form.dialysis;
    }

    if (
      form.dialysis === 'CRRT' &&
      Number(form.flow) > 0
    ) {
      dialysis.flow_rate_l_per_hour = Number(form.flow);
    }

    return {
      requested_drug: form.drug,
      age_years: Number(form.age),
      weight_kg: Number(form.weight),
      gender: form.sex,
      creatinine: Number(form.creatinine),

      dialysis,

      allergy_history: form.allergy.trim()
        ? [
            {
              substance: form.allergy.trim(),
              reaction: '',
              certainty: 'confirmed'
            }
          ]
        : [],

      concomitant_medications: form.medications
        .split(',')
        .map(x => x.trim())
        .filter(Boolean)
        .map(drug => ({ drug })),

      ...(form.drug === 'Meropenem'
        ? {
            indication_group: form.indication,
            infusion_strategy: form.infusion
          }
        : {
            infection_type: form.infection
          })
    };
  };

  // ==========================================================
  // CLINICAL ASSESSMENT
  // ==========================================================

  const assess = async event => {
    event.preventDefault();

    setBusy(true);
    setNotice('');

    try {
      const result = await api('/assess', {
        method: 'POST',
        body: JSON.stringify({
          patient: patient()
        })
      });

      setAssessment(result);

      setNotice(
        'Clinical engine assessment completed. Clinician review required.'
      );
    } catch (error) {
      setNotice(error.message);
    } finally {
      setBusy(false);
    }
  };

  // ==========================================================
  // SAVE CASE
  // ==========================================================

  const save = async () => {
    setBusy(true);

    try {
      const result = await api('/cases', {
        method: 'POST',
        body: JSON.stringify({
          patient: patient(),
          label: form.label
        })
      });

      setNotice('Case saved: ' + result.case_id);

      refresh();
    } catch (error) {
      setNotice(error.message);
    } finally {
      setBusy(false);
    }
  };

  // ==========================================================
  // OPEN CASE
  // ==========================================================

  const openCase = async id => {
    setBusy(true);

    try {
      const result = await api(
        '/cases/' + encodeURIComponent(id)
      );

      setSelected(result);
      setPage('Patient Records');
    } catch (error) {
      setNotice(error.message);
    } finally {
      setBusy(false);
    }
  };

  // ==========================================================
  // AI COPILOT
  // ==========================================================

  const send = async event => {
    event.preventDefault();

    if (!chat.trim()) return;

    const question = chat;

    setMessages(previous => [
      ...previous,
      {
        role: 'user',
        text: question
      }
    ]);

    setChat('');
    setBusy(true);

    try {
      const result = await api('/copilot', {
        method: 'POST',
        body: JSON.stringify({
          message: question,
          known: assessment?.patient || {},
          api_key: apiKey,
          model,
          provider
        })
      });

      setMessages(previous => [
        ...previous,
        {
          role: 'assistant',
          text: result.reply || 'Assessment completed.'
        }
      ]);

      setAssessment({
        result: result.result,
        evidence: result.evidence,
        patient: result.patient
      });
    } catch (error) {
      setMessages(previous => [
        ...previous,
        {
          role: 'assistant',
          text: 'Unable to complete: ' + error.message
        }
      ]);
    } finally {
      setBusy(false);
    }
  };

  // ==========================================================
  // FILTERS
  // ==========================================================

  const filtered = cases.filter(item =>
    (
      (item.case_id || '') +
      ' ' +
      (item.label || '') +
      ' ' +
      (item.drug || '')
    )
      .toLowerCase()
      .includes(search.toLowerCase())
  );

  const flags = cases.filter(
    item => statusClass(item.decision) !== 'good'
  ).length;

  const menuClick = name => {
    setPage(name);
    setMenu(false);
    setNotice('');
  };

  // ==========================================================
  // APPLICATION UI
  // ==========================================================

  return (
    <div className="shell">

      {/* SIDEBAR */}

      <aside className={'sidebar ' + (menu ? 'open' : '')}>

        <div className="brand">
          <div className="brand-symbol">✦</div>

          <div>
            <strong>
              HAC<span>·</span>Renal AI
            </strong>

            <small>CLINICAL INTELLIGENCE</small>
          </div>

          <button
            className="close-nav"
            onClick={() => setMenu(false)}
          >
            <X size={20} />
          </button>
        </div>

        <div className="nav-label">
          WORKSPACE
        </div>

        <nav>
          {nav.map(([name, Icon]) => (
            <button
              key={name}
              className={
                'nav-item ' +
                (page === name ? 'active' : '')
              }
              onClick={() => menuClick(name)}
            >
              <Icon size={19} />

              <span>{name}</span>

              {page === name && (
                <span className="nav-dot" />
              )}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="sidebar-organ">
            <span className="mini-kidney">🫘</span>
            <span className="orbital orbital-a" />
            <span className="orbital orbital-b" />
          </div>

          <div className="secure">
            <ShieldCheck size={17} />
            Clinical safety layer
          </div>

          <p>
            Research prototype · Not for autonomous prescribing.
          </p>

          <small>HAC-Renal AI · v2.0</small>
        </div>
      </aside>

      {/* MAIN CONTENT */}

      <div className="main">

        {/* HEADER */}

        <header className="topbar">

          <button
            className="mobile-menu"
            onClick={() => setMenu(!menu)}
          >
            <Menu />
          </button>

          <div className="breadcrumbs">
            WORKSPACE
            <span>/</span>
            <b>{page}</b>
          </div>

          <div className="header-right">

            <div className="search">
              <Search size={18} />

              <input
                aria-label="Search saved cases"
                value={search}
                onChange={event =>
                  setSearch(event.target.value)
                }
                placeholder="Search patient case, drug..."
                onKeyDown={event => {
                  if (event.key === 'Enter') {
                    setPage('Patient Records');
                  }
                }}
              />
            </div>

            <div className="live">
              <span
                className={
                  'live-dot ' +
                  (health ? '' : 'offline')
                }
              />

              {health ? 'ENGINE ONLINE' : 'API OFFLINE'}
            </div>

            <div className="avatar">
              DR
            </div>
          </div>
        </header>

        <main className="content">

          {/* NOTIFICATIONS */}

          {notice && (
            <div className="notice" role="status">
              {notice}

              <button onClick={() => setNotice('')}>
                <X size={16} />
              </button>
            </div>
          )}

          {/* ==================================================
              DASHBOARD
          ================================================== */}

          {page === 'Dashboard' && (
            <>

              <section className="hero">

                <div className="hero-copy">

                  <div className="eyebrow">
                    <span className="tiny-line" />
                    THE FUTURE OF RENAL CARE
                  </div>

                  <h1>
                    Intelligent &amp; safe
                    <br />

                    <em>antibiotic therapy</em>
                    <br />

                    for renal patients.
                  </h1>

                  <p>
                    Evidence-grounded medication review,
                    dialysis-aware safety checks and
                    intelligent clinical support —
                    beautifully connected.
                  </p>

                  <div className="hero-actions">

                    <button
                      className="btn primary"
                      onClick={() =>
                        menuClick('New Assessment')
                      }
                    >
                      <Plus size={18} />
                      New assessment
                    </button>

                    <button
                      className="btn secondary"
                      onClick={() =>
                        menuClick('AI Copilot')
                      }
                    >
                      <MessageCircle size={17} />
                      AI Copilot
                    </button>

                  </div>
                </div>

                <div className="hero-3d">

                  <div className="holo-label">
                    INTERACTIVE RENAL MODEL
                    <span>● 3D</span>
                  </div>

                  <KidneyScene />

                  <div className="holo-bottom">
                    DRAG TO ROTATE · LIVE 3D
                  </div>

                </div>

                <div className="hero-status">

                  <div className="status-heading">
                    System status
                    <span className="live-dot" />
                  </div>

                  {[
                    ['Clinical rules', !!health],
                    ['Drug registry', !!health],
                    ['Evidence retrieval', !!health],
                    ['AI copilot', 'key']
                  ].map(([name, ok]) => (

                    <div
                      className="status-row"
                      key={name}
                    >

                      <span>
                        <CheckCircle2 size={15} />
                        {name}
                      </span>

                      <b
                        className={
                          ok === true ? 'teal' : ''
                        }
                      >
                        {ok === 'key'
                          ? 'Optional'
                          : ok
                            ? 'Ready'
                            : 'Offline'}
                      </b>

                    </div>
                  ))}

                </div>

              </section>

              <section className="metrics">

                <Metric
                  icon={Users}
                  title="Tracked cases"
                  value={cases.length}
                  detail="Saved clinical records"
                  tone="cyan"
                />

                <Metric
                  icon={Pill}
                  title="Supported antibiotics"
                  value={
                    health?.supported_drugs?.length ?? '—'
                  }
                  detail="Rule engine connected"
                  tone="blue"
                />

                <Metric
                  icon={AlertTriangle}
                  title="Review flags"
                  value={flags}
                  detail="From saved assessments"
                  tone="pink"
                />

                <Metric
                  icon={ShieldCheck}
                  title="Clinical engine"
                  value={health ? 'ACTIVE' : 'OFFLINE'}
                  detail="Deterministic safety rules"
                  tone="green"
                />

              </section>

              <section className="two-col">

                <div className="glass">

                  <div className="card-heading">

                    <div>
                      <small>CASE MANAGEMENT</small>
                      <h2>Recent clinical cases</h2>
                    </div>

                    <button
                      className="text-button"
                      onClick={() =>
                        menuClick('Patient Records')
                      }
                    >
                      View all
                      <ArrowRight size={16} />
                    </button>

                  </div>

                  <div className="table-scroll">

                    <table>

                      <thead>
                        <tr>
                          <th>CASE ID</th>
                          <th>ANTIBIOTIC</th>
                          <th>UPDATED</th>
                          <th>STATUS</th>
                        </tr>
                      </thead>

                      <tbody>

                        {cases.slice(0, 5).map(item => (
                          <tr
                            key={item.case_id}
                            onClick={() =>
                              openCase(item.case_id)
                            }
                          >
                            <td>{item.case_id}</td>

                            <td>
                              {item.drug || '—'}
                            </td>

                            <td>
                              {(item.updated_at || '')
                                .slice(0, 10)}
                            </td>

                            <td>
                              <Badge
                                status={item.decision}
                              />
                            </td>
                          </tr>
                        ))}

                        {!cases.length && (
                          <tr>
                            <td
                              colSpan="4"
                              className="empty"
                            >
                              No cases yet. Run an
                              assessment to begin.
                            </td>
                          </tr>
                        )}

                      </tbody>
                    </table>

                  </div>
                </div>

                <div className="glass">

                  <div className="card-heading">

                    <div>
                      <small>CLINICAL OVERVIEW</small>
                      <h2>Care workflow</h2>
                    </div>

                    <Activity
                      size={20}
                      color="#3ddce9"
                    />

                  </div>

                  <div className="workflow">

                    <div>
                      <span>01</span>
                      <b>Capture patient context</b>
                      <small>
                        Structured clinical inputs
                      </small>
                    </div>

                    <div>
                      <span>02</span>
                      <b>Run safety rules</b>
                      <small>
                        Existing Python clinical engine
                      </small>
                    </div>

                    <div>
                      <span>03</span>
                      <b>Review evidence</b>
                      <small>
                        Clinician-verified decision
                      </small>
                    </div>

                  </div>
                </div>

              </section>

              <section className="quick-grid">

                <Quick
                  icon={FileScan}
                  title="Prescription scanner"
                  sub="Planned · requires backend"
                  disabled
                />

                <Quick
                  icon={ClipboardCheck}
                  title="Medication review"
                  sub="Run existing clinical rules"
                  onClick={() =>
                    menuClick('Medication Review')
                  }
                />

                <Quick
                  icon={ShieldCheck}
                  title="Safety center"
                  sub="Inspect clinical flags"
                  onClick={() =>
                    menuClick('Safety Center')
                  }
                />

                <Quick
                  icon={HeartPulse}
                  title="Case monitoring"
                  sub="Longitudinal follow-up"
                  onClick={() =>
                    menuClick('Patient Records')
                  }
                />

              </section>

            </>
          )}

          {/* ==================================================
              NEW ASSESSMENT / MEDICATION REVIEW
          ================================================== */}

          {(
            page === 'New Assessment' ||
            page === 'Medication Review'
          ) && (
            <>

              <PageTitle
                over="CLINICAL DECISION SUPPORT"
                title="Medication safety assessment"
                sub="All results are computed by your original Python rules engine, not by the interface."
              />

              <div className="assessment-grid">

                <form
                  className="glass form-card"
                  onSubmit={assess}
                >

                  <h2>
                    Patient &amp; medication details
                  </h2>

                  <div className="form-grid">

                    <Field label="Antibiotic">
                      <select
                        value={form.drug}
                        onChange={event =>
                          set('drug', event.target.value)
                        }
                      >
                        <option>Vancomycin</option>
                        <option>Meropenem</option>
                      </select>
                    </Field>

                    <Field label="Dialysis modality">
                      <select
                        value={form.dialysis}
                        onChange={event =>
                          set('dialysis', event.target.value)
                        }
                      >
                        {[
                          'No',
                          'IHD',
                          'CRRT',
                          'PD'
                        ].map(value => (
                          <option key={value}>
                            {value}
                          </option>
                        ))}
                      </select>
                    </Field>

                    <Field label="Age (years)">
                      <input
                        type="number"
                        min="1"
                        max="120"
                        required
                        value={form.age}
                        onChange={event =>
                          set('age', event.target.value)
                        }
                      />
                    </Field>

                    <Field label="Weight (kg)">
                      <input
                        type="number"
                        min="1"
                        max="350"
                        step="0.5"
                        required
                        value={form.weight}
                        onChange={event =>
                          set('weight', event.target.value)
                        }
                      />
                    </Field>

                    <Field label="Sex for renal calculation">
                      <select
                        value={form.sex}
                        onChange={event =>
                          set('sex', event.target.value)
                        }
                      >
                        <option>Male</option>
                        <option>Female</option>
                      </select>
                    </Field>

                    <Field label="Serum creatinine (mg/dL)">
                      <input
                        type="number"
                        min="0.1"
                        max="25"
                        step="0.1"
                        required
                        value={form.creatinine}
                        onChange={event =>
                          set(
                            'creatinine',
                            event.target.value
                          )
                        }
                      />
                    </Field>

                    {form.dialysis === 'CRRT' && (
                      <Field label="CRRT flow (L/hour)">
                        <input
                          type="number"
                          min="0"
                          max="10"
                          step="0.5"
                          value={form.flow}
                          onChange={event =>
                            set(
                              'flow',
                              event.target.value
                            )
                          }
                        />
                      </Field>
                    )}

                    {form.drug === 'Vancomycin' ? (

                      <Field label="Infection type">
                        <select
                          value={form.infection}
                          onChange={event =>
                            set(
                              'infection',
                              event.target.value
                            )
                          }
                        >
                          <option value="complicated">
                            Complicated
                          </option>

                          <option value="uncomplicated">
                            Uncomplicated
                          </option>
                        </select>
                      </Field>

                    ) : (
                      <>

                        <Field label="Indication">
                          <select
                            value={form.indication}
                            onChange={event =>
                              set(
                                'indication',
                                event.target.value
                              )
                            }
                          >
                            <option>Standard</option>
                            <option>Meningitis_CF</option>
                          </select>
                        </Field>

                        <Field label="Infusion strategy">
                          <select
                            value={form.infusion}
                            onChange={event =>
                              set(
                                'infusion',
                                event.target.value
                              )
                            }
                          >
                            <option>Short_Infusion</option>
                            <option>Extended_Infusion</option>
                          </select>
                        </Field>

                      </>
                    )}

                  </div>

                  <Field label="Documented drug allergy">
                    <input
                      value={form.allergy}
                      onChange={event =>
                        set(
                          'allergy',
                          event.target.value
                        )
                      }
                      placeholder="Leave blank if none documented"
                    />
                  </Field>

                  <Field label="Concomitant medications">
                    <input
                      value={form.medications}
                      onChange={event =>
                        set(
                          'medications',
                          event.target.value
                        )
                      }
                      placeholder="Comma-separated drug names"
                    />
                  </Field>

                  <button
                    disabled={busy || !health}
                    className="btn primary full"
                    type="submit"
                  >

                    {busy ? (
                      <Loader2
                        className="spin"
                        size={18}
                      />
                    ) : (
                      <ClipboardCheck size={18} />
                    )}

                    Run clinical assessment

                    <ArrowRight size={17} />

                  </button>

                </form>

                {/* ASSESSMENT RESULTS */}

                <div className="result-stack">

                  <div className="glass result-card">

                    <h2>
                      <ShieldCheck size={20} />
                      Clinical assessment output
                    </h2>

                    {assessment ? (
                      <>

                        <Badge
                          status={
                            assessment.result?.decision
                          }
                        />

                        {/* FIXED CLINICAL RESULT DISPLAY */}

                        <ClinicalResult
                          result={assessment.result}
                        />

                        {assessment.result
                          ?.missing_fields?.length > 0 && (

                          <p className="warning-text">
                            Missing:{' '}
                            {assessment.result
                              .missing_fields.join(', ')}
                          </p>

                        )}

                        {assessment.result
                          ?.required_action && (

                          <p>
                            <b>Required action:</b>{' '}
                            {String(
                              assessment.result.required_action
                            )}
                          </p>

                        )}

                        <details>
                          <summary>
                            Engine decision (JSON)
                          </summary>

                          <pre>
                            {JSON.stringify(
                              assessment.result,
                              null,
                              2
                            )}
                          </pre>
                        </details>

                        <details>
                          <summary>
                            Evidence &amp; traceability
                          </summary>

                          <pre>
                            {JSON.stringify(
                              assessment.evidence,
                              null,
                              2
                            )}
                          </pre>
                        </details>

                      </>
                    ) : (

                      <div className="placeholder">
                        <Stethoscope size={35} />

                        <p>
                          Enter patient information
                          and run the assessment to
                          see rule-engine results here.
                        </p>
                      </div>

                    )}

                  </div>

                  {/* SAVE CASE */}

                  <div className="glass save-card">

                    <h2>
                      <Save size={19} />
                      Save longitudinal case
                    </h2>

                    <p>
                      Save this reviewed assessment
                      as a case in your existing
                      follow-up system.
                    </p>

                    <Field label="Case label">
                      <input
                        value={form.label}
                        onChange={event =>
                          set(
                            'label',
                            event.target.value
                          )
                        }
                        placeholder="e.g. IHD review · visit 1"
                      />
                    </Field>

                    <button
                      className="btn secondary full"
                      disabled={!assessment || busy}
                      onClick={save}
                    >
                      Save tracked case
                    </button>

                  </div>

                </div>
              </div>
            </>
          )}

          {/* ==================================================
              PATIENT RECORDS
          ================================================== */}

          {page === 'Patient Records' && (
            <>

              <PageTitle
                over="LONGITUDINAL MONITORING"
                title="Patient case records"
                sub="These are existing case IDs, not a patient identity database."
              />

              <div className="two-col records">

                <div className="glass">

                  <div className="card-heading">

                    <h2>Saved cases</h2>

                    <button
                      className="text-button"
                      onClick={refresh}
                    >
                      <RefreshCw size={16} />
                      Refresh
                    </button>

                  </div>

                  {filtered.map(item => (

                    <button
                      className={
                        'record-item ' +
                        (
                          selected?.case_id === item.case_id
                            ? 'selected'
                            : ''
                        )
                      }
                      key={item.case_id}
                      onClick={() =>
                        openCase(item.case_id)
                      }
                    >

                      <span>
                        <b>
                          {item.label || item.case_id}
                        </b>

                        <small>
                          {item.case_id} ·{' '}
                          {item.drug || 'Unknown drug'}
                        </small>
                      </span>

                      <Badge
                        status={item.decision}
                      />

                    </button>

                  ))}

                  {!filtered.length && (
                    <div className="empty">
                      No matching cases found.
                    </div>
                  )}

                </div>

                <div className="glass">

                  <h2>Case detail</h2>

                  {selected ? (
                    <>

                      <h3>
                        {selected.label ||
                          selected.case_id}
                      </h3>

                      <p className="muted">
                        {selected.case_id}
                      </p>

                      <Badge
                        status={
                          selected.current_result?.decision
                        }
                      />

                      <p>
                        {selected.current_result?.message}
                      </p>

                      <h3>Timeline</h3>

                      {(selected.timeline || []).map(
                        (event, index) => (

                          <div
                            className="timeline-event"
                            key={index}
                          >

                            <span className="timeline-dot" />

                            <b>{event.event}</b>

                            <small>{event.at}</small>

                            <p>{event.note}</p>

                          </div>

                        )
                      )}

                      <details>
                        <summary>
                          Clinical record
                        </summary>

                        <pre>
                          {JSON.stringify(
                            selected,
                            null,
                            2
                          )}
                        </pre>
                      </details>

                    </>
                  ) : (

                    <div className="placeholder">
                      <Users size={38} />

                      <p>
                        Select a case to view
                        its clinical timeline.
                      </p>
                    </div>

                  )}

                </div>

              </div>
            </>
          )}

          {/* ==================================================
              AI COPILOT
          ================================================== */}

          {page === 'AI Copilot' && (
            <>

              <PageTitle
                over="EVIDENCE-GROUNDED AI"
                title="Clinical AI copilot"
                sub="Language model extracts clinical notes; the unchanged clinical engine performs rule checks."
              />

              <div className="glass copilot">

                <div className="chat-area">

                  {!messages.length && (
                    <div className="placeholder">

                      <MessageCircle size={45} />

                      <h2>
                        How can I help with this
                        clinical case?
                      </h2>

                      <p>
                        Enter an API key in Settings
                        first. Do not enter identifiable
                        patient data.
                      </p>

                    </div>
                  )}

                  {messages.map((message, index) => (

                    <div
                      className={
                        'chat-bubble ' + message.role
                      }
                      key={index}
                    >
                      {message.text}
                    </div>

                  ))}

                </div>

                <form
                  className="chat-input"
                  onSubmit={send}
                >

                  <input
                    aria-label="Clinical question"
                    value={chat}
                    onChange={event =>
                      setChat(event.target.value)
                    }
                    placeholder="Describe a synthetic clinical case..."
                  />

                  <button
                    disabled={
                      busy ||
                      !chat.trim() ||
                      !apiKey
                    }
                    className="btn primary"
                  >
                    Send
                    <ArrowRight size={16} />
                  </button>

                </form>

              </div>
            </>
          )}

          {/* ==================================================
              ANALYTICS
          ================================================== */}

          {page === 'Analytics' && (
            <>

              <PageTitle
                over="OPERATIONS INTELLIGENCE"
                title="Clinical analytics"
                sub="Statistics reflect saved case records only. No synthetic metrics are presented as real data."
              />

              <div className="metrics">

                <Metric
                  icon={Users}
                  title="Tracked cases"
                  value={cases.length}
                  tone="cyan"
                />

                <Metric
                  icon={AlertTriangle}
                  title="Review flags"
                  value={flags}
                  tone="pink"
                />

                <Metric
                  icon={Pill}
                  title="Antibiotics"
                  value={
                    health?.supported_drugs?.length ?? '—'
                  }
                  tone="blue"
                />

              </div>

              <div className="glass analytics">

                <h2>Case decisions</h2>

                {cases.length ? (

                  <ResponsiveContainer
                    width="100%"
                    height={280}
                  >

                    <PieChart>

                      <Pie
                        data={
                          Object.entries(
                            cases.reduce(
                              (accumulator, item) => {
                                const decision =
                                  item.decision || 'UNKNOWN';

                                accumulator[decision] =
                                  (
                                    accumulator[decision] || 0
                                  ) + 1;

                                return accumulator;
                              },
                              {}
                            )
                          ).map(([name, value]) => ({
                            name,
                            value
                          }))
                        }
                        dataKey="value"
                        nameKey="name"
                        cx="50%"
                        cy="50%"
                        outerRadius={95}
                        label
                      >

                        {Object.keys(
                          cases.reduce(
                            (accumulator, item) => {
                              accumulator[
                                item.decision || 'UNKNOWN'
                              ] = 1;

                              return accumulator;
                            },
                            {}
                          )
                        ).map((_, index) => (

                          <Cell
                            key={index}
                            fill={
                              [
                                '#28dfcd',
                                '#ee5c9d',
                                '#f4b85d',
                                '#4aafff'
                              ][index % 4]
                            }
                          />

                        ))}

                      </Pie>

                      <Tooltip />

                    </PieChart>

                  </ResponsiveContainer>

                ) : (

                  <div className="placeholder">
                    No case data available yet.
                  </div>

                )}

              </div>
            </>
          )}

          {/* ==================================================
              SAFETY CENTER
          ================================================== */}

          {page === 'Safety Center' && (
            <>

              <PageTitle
                over="PATIENT SAFETY"
                title="Clinical safety center"
                sub="Alerts originate from existing saved case decisions; they are not newly inferred by the UI."
              />

              <div className="glass">

                <h2>Cases requiring review</h2>

                {cases
                  .filter(
                    item =>
                      statusClass(item.decision) !== 'good'
                  )
                  .map(item => (

                    <button
                      className="record-item"
                      key={item.case_id}
                      onClick={() =>
                        openCase(item.case_id)
                      }
                    >

                      <span>
                        <b>
                          {item.label || item.case_id}
                        </b>

                        <small>{item.drug}</small>
                      </span>

                      <Badge
                        status={item.decision}
                      />

                    </button>

                  ))}

                {flags === 0 && (

                  <div className="placeholder">

                    <ShieldCheck size={36} />

                    <p>
                      No flagged decisions in saved
                      cases. This does not establish
                      clinical safety.
                    </p>

                  </div>

                )}

              </div>
            </>
          )}

          {/* ==================================================
              SETTINGS
          ================================================== */}

          {page === 'Settings' && (
            <>

              <PageTitle
                over="CONFIGURATION"
                title="AI connection settings"
                sub="API keys remain in this browser session and are sent only to your local Python adapter for the selected request."
              />

              <div className="glass settings-card">

                <Field label="LLM provider">

                  <select
                    value={provider}
                    onChange={event =>
                      setProvider(event.target.value)
                    }
                  >
                    <option>OpenRouter</option>
                    <option>Mistral</option>
                  </select>

                </Field>

                <Field label="Model ID">

                  <input
                    value={model}
                    onChange={event =>
                      setModel(event.target.value)
                    }
                  />

                </Field>

                <Field label="API key (session only)">

                  <input
                    type="password"
                    autoComplete="off"
                    value={apiKey}
                    onChange={event =>
                      setApiKey(event.target.value)
                    }
                    placeholder="Paste API key"
                  />

                </Field>

                <div className="secure-note">
                  <LockKeyhole size={17} />
                  No key is stored in case records
                  by this frontend. Use synthetic
                  cases only.
                </div>

                <button
                  className="btn primary"
                  onClick={() =>
                    menuClick('AI Copilot')
                  }
                >
                  Go to AI copilot
                  <ArrowRight size={17} />
                </button>

              </div>
            </>
          )}

          {/* FOOTER */}

          <footer>
            HAC-RENAL AI
            <span>·</span>
            RESEARCH PROTOTYPE
            <span>·</span>
            CLINICIAN VERIFICATION REQUIRED
          </footer>

        </main>
      </div>
    </div>
  );
}

// ============================================================
// REUSABLE COMPONENTS
// ============================================================

function Metric({
  icon: Icon,
  title,
  value,
  detail,
  tone = 'cyan'
}) {
  return (
    <div className={'metric ' + tone}>

      <div className="metric-icon">
        <Icon size={25} />
      </div>

      <div>
        <span>{title}</span>
        <strong>{value}</strong>
        <small>
          {detail || 'Live workspace data'}
        </small>
      </div>

    </div>
  );
}

function Badge({ status }) {
  return (
    <span
      className={
        'badge ' + statusClass(status)
      }
    >
      {status || 'PENDING'}
    </span>
  );
}

function Quick({
  icon: Icon,
  title,
  sub,
  onClick,
  disabled
}) {
  return (
    <button
      className="quick"
      disabled={disabled}
      onClick={onClick}
    >

      <span>
        <Icon size={29} />
      </span>

      <b>{title}</b>

      <small>{sub}</small>

      <ArrowRight
        className="quick-arrow"
        size={17}
      />

    </button>
  );
}

function PageTitle({
  over,
  title,
  sub
}) {
  return (
    <div className="page-title">

      <div className="eyebrow">
        {over}
      </div>

      <h1>{title}</h1>

      <p>{sub}</p>

    </div>
  );
}

function Field({
  label,
  children
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  );
}

// ============================================================
// EXPORT
// ============================================================

export default App;