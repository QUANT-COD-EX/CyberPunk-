import React, { useState, useEffect } from 'react';
import {
  InvestigationAnalytics,
  CrossDocRelationshipGraph,
  RelationshipNode,
  RelationshipEdge,
  AnomalyCorrelationCluster,
  DocumentRecord,
  BBox,
} from '../types';
import {
  getInvestigationAnalytics,
  getInvestigationRelationships,
  getDocumentForensicsHeatmapUrl,
  getDocumentPageImageUrl,
} from '../api/client';

interface InvestigationAnalyticsViewProps {
  investigationId: string;
  documents: DocumentRecord[];
  onJumpToEvidence?: (docId: string, page: number, bbox: BBox) => void;
}

export const InvestigationAnalyticsView: React.FC<InvestigationAnalyticsViewProps> = ({
  investigationId,
  documents,
  onJumpToEvidence,
}) => {
  const [analytics, setAnalytics] = useState<InvestigationAnalytics | null>(null);
  const [graph, setGraph] = useState<CrossDocRelationshipGraph | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [activeTab, setActiveTab] = useState<'relationships' | 'forensics' | 'reasoning' | 'multilingual'>('relationships');

  // Forensics view state
  const [selectedDocId, setSelectedDocId] = useState<string>(documents[0]?.doc_id || '');
  const [forensicPage, setForensicPage] = useState<number>(1);
  const [forensicViewMode, setForensicViewMode] = useState<'side_by_side' | 'heatmap_only' | 'original_only'>('side_by_side');

  useEffect(() => {
    setLoading(true);
    Promise.all([
      getInvestigationAnalytics(investigationId).catch(() => null),
      getInvestigationRelationships(investigationId).catch(() => null),
    ]).then(([anaData, graphData]) => {
      setAnalytics(anaData);
      setGraph(graphData);
      setLoading(false);
    });
  }, [investigationId]);

  if (loading) {
    return (
      <div className="panel" style={{ padding: '30px', textAlign: 'center', color: 'var(--text-muted)' }}>
        Loading advanced analytics and evidence graph...
      </div>
    );
  }

  const selectedDoc = documents.find((d) => d.doc_id === selectedDocId) || documents[0];
  const selectedForensic = selectedDoc?.forensic_report;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* Top Banner: Key Investigation Metrics */}
      <div
        className="panel"
        style={{
          padding: '16px 20px',
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: '12px',
          backgroundColor: 'var(--bg-panel)',
        }}
      >
        <div style={{ borderLeft: '3px solid var(--accent-main)', paddingLeft: '10px' }}>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>CROSS-DOC CONSISTENCY</div>
          <div style={{ fontSize: '20px', fontWeight: '800', color: (analytics?.consistency_score || 1) < 0.8 ? '#ef4444' : '#10b981' }}>
            {analytics ? `${(analytics.consistency_score * 100).toFixed(1)}%` : '100%'}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{analytics?.contradictions_count || 0} contradiction(s) noted</div>
        </div>

        <div style={{ borderLeft: '3px solid #f59e0b', paddingLeft: '10px' }}>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>TAMPERING RISK INDEX</div>
          <div style={{ fontSize: '20px', fontWeight: '800', color: (analytics?.tampering_risk_score || 0) > 0.5 ? '#f59e0b' : '#3b82f6' }}>
            {analytics ? `${(analytics.tampering_risk_score * 100).toFixed(0)} / 100` : '0 / 100'}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Multi-method surface scan</div>
        </div>

        <div style={{ borderLeft: '3px solid #8b5cf6', paddingLeft: '10px' }}>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>DISCOVERED ENTITIES</div>
          <div style={{ fontSize: '20px', fontWeight: '800', color: 'var(--text-main)' }}>
            {analytics?.total_entities_discovered || graph?.total_entities || 0}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Persons, PAN, Accounts, Orgs</div>
        </div>

        <div style={{ borderLeft: '3px solid #ec4899', paddingLeft: '10px' }}>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>HANDWRITING RATIO</div>
          <div style={{ fontSize: '20px', fontWeight: '800', color: 'var(--text-main)' }}>
            {analytics ? `${(analytics.handwriting_stats.overall_handwriting_ratio * 100).toFixed(1)}%` : '0.0%'}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            {analytics?.handwriting_stats.total_handwritten_fields || 0} handwritten fields
          </div>
        </div>

        <div style={{ borderLeft: '3px solid #06b6d4', paddingLeft: '10px' }}>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>AI & SIGNATURE FORENSICS</div>
          <div style={{ fontSize: '20px', fontWeight: '800', color: documents.some((d) => d.is_ai_generated) ? '#ef4444' : '#10b981' }}>
            {documents.filter((d) => d.is_ai_generated).length > 0
              ? `${documents.filter((d) => d.is_ai_generated).length} AI-Gen Alert`
              : 'Authentic'}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Deepfake signature & AI scan</div>
        </div>
      </div>

      {/* Sub-navigation Controls */}
      <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
        <button
          onClick={() => setActiveTab('relationships')}
          className={`btn-action ${activeTab === 'relationships' ? 'btn-accent' : ''}`}
          style={{ fontSize: '12px', padding: '6px 14px' }}
        >
          Relationship Discovery Graph
        </button>
        <button
          onClick={() => setActiveTab('forensics')}
          className={`btn-action ${activeTab === 'forensics' ? 'btn-accent' : ''}`}
          style={{ fontSize: '12px', padding: '6px 14px' }}
        >
          Tampering Localization Heatmap
        </button>
        <button
          onClick={() => setActiveTab('reasoning')}
          className={`btn-action ${activeTab === 'reasoning' ? 'btn-accent' : ''}`}
          style={{ fontSize: '12px', padding: '6px 14px' }}
        >
          Contextual Reasoning Chains ({analytics?.correlation_clusters?.length || 0})
        </button>
        <button
          onClick={() => setActiveTab('multilingual')}
          className={`btn-action ${activeTab === 'multilingual' ? 'btn-accent' : ''}`}
          style={{ fontSize: '12px', padding: '6px 14px' }}
        >
          Multilingual & Handwriting
        </button>
      </div>

      {/* TAB 1: RELATIONSHIP DISCOVERY GRAPH */}
      {activeTab === 'relationships' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div className="panel" style={{ padding: '16px', backgroundColor: 'var(--bg-panel)' }}>
            <h3 style={{ margin: '0 0 6px 0', fontSize: '14px', fontWeight: '700', color: 'var(--text-main)' }}>
              Cross-Document Entity-Provenance Network
            </h3>
            <p style={{ margin: '0 0 14px 0', fontSize: '12px', color: 'var(--text-muted)' }}>
              Automatically correlates identities, account references, and issuing institutions across documents. Identifies cross-validation vs contradictory linkages.
            </p>

            {/* Entity Nodes Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '10px', marginBottom: '16px' }}>
              {graph?.nodes.map((node: RelationshipNode) => {
                const typeColors: Record<string, string> = {
                  document: '#0284c7',
                  person: '#10b981',
                  identifier: '#8b5cf6',
                  bank_account: '#f59e0b',
                  employer: '#ec4899',
                };
                const color = typeColors[node.type] || 'var(--text-muted)';

                return (
                  <div
                    key={node.id}
                    style={{
                      padding: '10px 12px',
                      borderRadius: '4px',
                      border: `1px solid var(--border-color)`,
                      borderLeft: `4px solid ${color}`,
                      backgroundColor: 'var(--bg-subtle)',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '4px',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '9.5px', fontWeight: '700', color, textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>
                        {node.type}
                      </span>
                      {node.doc_id && (
                        <span style={{ fontSize: '9.5px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                          {node.doc_id}
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: '12.5px', fontWeight: '600', color: 'var(--text-main)' }}>{node.label}</div>
                  </div>
                );
              })}
            </div>

            {/* Linkages / Edges Table */}
            <h4 style={{ margin: '14px 0 8px 0', fontSize: '12px', color: 'var(--text-muted)', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>
              Discovered Relationship Links ({graph?.edges.length || 0})
            </h4>
            <div style={{ overflowX: 'auto', border: '1px solid var(--border-color)', borderRadius: '4px' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '11.5px', textAlign: 'left' }}>
                <thead>
                  <tr style={{ backgroundColor: 'var(--bg-subtle)', borderBottom: '1px solid var(--border-color)', color: 'var(--text-muted)' }}>
                    <th style={{ padding: '8px 10px' }}>Source</th>
                    <th style={{ padding: '8px 10px' }}>Relationship</th>
                    <th style={{ padding: '8px 10px' }}>Target</th>
                    <th style={{ padding: '8px 10px' }}>Status</th>
                    <th style={{ padding: '8px 10px' }}>Details / Coherence</th>
                  </tr>
                </thead>
                <tbody>
                  {graph?.edges.map((edge: RelationshipEdge) => {
                    const isContradiction = edge.status === 'contradiction';
                    return (
                      <tr
                        key={edge.id}
                        style={{
                          borderBottom: '1px solid var(--border-color)',
                          backgroundColor: isContradiction ? 'rgba(239, 68, 68, 0.08)' : 'transparent',
                        }}
                      >
                        <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)', fontWeight: '600' }}>{edge.source}</td>
                        <td style={{ padding: '8px 10px', fontWeight: '700', color: isContradiction ? '#ef4444' : 'var(--text-main)' }}>
                          {edge.relation}
                        </td>
                        <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)' }}>{edge.target}</td>
                        <td style={{ padding: '8px 10px' }}>
                          <span
                            style={{
                              fontSize: '9.5px',
                              fontWeight: '700',
                              padding: '2px 6px',
                              borderRadius: '3px',
                              backgroundColor: isContradiction ? '#ef4444' : '#10b981',
                              color: '#ffffff',
                              textTransform: 'uppercase',
                            }}
                          >
                            {edge.status}
                          </span>
                        </td>
                        <td style={{ padding: '8px 10px', color: 'var(--text-muted)' }}>
                          {edge.details || `${(edge.confidence * 100).toFixed(0)}% confidence`}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: TAMPERING LOCALIZATION HEATMAP */}
      {activeTab === 'forensics' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div className="panel" style={{ padding: '16px', backgroundColor: 'var(--bg-panel)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px', marginBottom: '14px' }}>
              <div>
                <h3 style={{ margin: '0 0 4px 0', fontSize: '14px', fontWeight: '700', color: 'var(--text-main)' }}>
                  Advanced Multi-Signal Tampering Localization
                </h3>
                <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                  Error Level Analysis (ELA) &bull; 2D-FFT Spectral Frequency &bull; Noise Residuals &bull; Copy-Move Clones &bull; Deepfake Signatures &bull; AI Authenticity
                </span>
              </div>

              {/* Document Selector */}
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <select
                  value={selectedDocId}
                  onChange={(e) => {
                    setSelectedDocId(e.target.value);
                    setForensicPage(1);
                  }}
                  style={{
                    padding: '4px 8px',
                    fontSize: '12px',
                    borderRadius: '4px',
                    border: '1px solid var(--border-color)',
                    backgroundColor: 'var(--bg-subtle)',
                    color: 'var(--text-main)',
                  }}
                >
                  {documents.map((d) => (
                    <option key={d.doc_id} value={d.doc_id}>
                      {d.filename} ({d.doc_id})
                    </option>
                  ))}
                </select>

                {/* View Mode Toggle */}
                <div style={{ display: 'flex', border: '1px solid var(--border-color)', borderRadius: '4px', overflow: 'hidden' }}>
                  <button
                    onClick={() => setForensicViewMode('side_by_side')}
                    className={`btn-action ${forensicViewMode === 'side_by_side' ? 'btn-accent' : ''}`}
                    style={{ fontSize: '11px', padding: '4px 8px', borderRadius: 0 }}
                  >
                    Side-by-Side
                  </button>
                  <button
                    onClick={() => setForensicViewMode('heatmap_only')}
                    className={`btn-action ${forensicViewMode === 'heatmap_only' ? 'btn-accent' : ''}`}
                    style={{ fontSize: '11px', padding: '4px 8px', borderRadius: 0 }}
                  >
                    Heatmap Only
                  </button>
                  <button
                    onClick={() => setForensicViewMode('original_only')}
                    className={`btn-action ${forensicViewMode === 'original_only' ? 'btn-accent' : ''}`}
                    style={{ fontSize: '11px', padding: '4px 8px', borderRadius: 0 }}
                  >
                    Original Only
                  </button>
                </div>

                {selectedDoc && selectedDoc.pages > 1 && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <button
                      disabled={forensicPage <= 1}
                      onClick={() => setForensicPage((p) => Math.max(1, p - 1))}
                      className="btn-action"
                      style={{ fontSize: '11px', padding: '2px 6px' }}
                    >
                      &larr;
                    </button>
                    <span style={{ fontSize: '11px', fontFamily: 'var(--font-mono)' }}>
                      P.{forensicPage}/{selectedDoc.pages}
                    </span>
                    <button
                      disabled={forensicPage >= selectedDoc.pages}
                      onClick={() => setForensicPage((p) => Math.min(selectedDoc.pages, p + 1))}
                      className="btn-action"
                      style={{ fontSize: '11px', padding: '2px 6px' }}
                    >
                      &rarr;
                    </button>
                  </div>
                )}
              </div>
            </div>

            {/* Metric Cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '10px', marginBottom: '16px' }}>
              <div style={{ padding: '8px 12px', borderRadius: '4px', backgroundColor: 'var(--bg-subtle)', border: '1px solid var(--border-color)' }}>
                <div style={{ fontSize: '10px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>TAMPER PROBABILITY</div>
                <div style={{ fontSize: '18px', fontWeight: '800', color: (selectedForensic?.tamper_score || 0) > 0.6 ? '#ef4444' : '#10b981' }}>
                  {selectedForensic ? `${(selectedForensic.tamper_score * 100).toFixed(1)}%` : '5.0%'}
                </div>
              </div>
              <div style={{ padding: '8px 12px', borderRadius: '4px', backgroundColor: 'var(--bg-subtle)', border: '1px solid var(--border-color)' }}>
                <div style={{ fontSize: '10px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>ELA MEAN MSE</div>
                <div style={{ fontSize: '18px', fontWeight: '800', color: 'var(--text-main)' }}>
                  {selectedForensic?.ela_mean_mse || 0.0}
                </div>
              </div>
              <div style={{ padding: '8px 12px', borderRadius: '4px', backgroundColor: 'var(--bg-subtle)', border: '1px solid var(--border-color)' }}>
                <div style={{ fontSize: '10px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>2D-FFT SPECTRAL SPIKE</div>
                <div style={{ fontSize: '18px', fontWeight: '800', color: (selectedForensic?.fft_spectral_anomaly_score || 0) > 4.5 ? '#f59e0b' : 'var(--text-main)' }}>
                  {selectedForensic ? `${selectedForensic.fft_spectral_anomaly_score || 0.0}\u03c3` : '0.0\u03c3'}
                </div>
              </div>
              <div style={{ padding: '8px 12px', borderRadius: '4px', backgroundColor: 'var(--bg-subtle)', border: '1px solid var(--border-color)' }}>
                <div style={{ fontSize: '10px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>NOISE DISCREPANCY</div>
                <div style={{ fontSize: '18px', fontWeight: '800', color: 'var(--text-main)' }}>
                  {selectedForensic ? `${selectedForensic.noise_variance_delta}\u03c3` : '0.0\u03c3'}
                </div>
              </div>
              <div style={{ padding: '8px 12px', borderRadius: '4px', backgroundColor: 'var(--bg-subtle)', border: '1px solid var(--border-color)' }}>
                <div style={{ fontSize: '10px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>COPY-MOVE CLONES</div>
                <div style={{ fontSize: '18px', fontWeight: '800', color: 'var(--text-main)' }}>
                  {selectedForensic?.copy_move_matches || 0}
                </div>
              </div>
              <div style={{ padding: '8px 12px', borderRadius: '4px', backgroundColor: 'var(--bg-subtle)', border: '1px solid var(--border-color)' }}>
                <div style={{ fontSize: '10px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>AI GENERATION RISK</div>
                <div style={{ fontSize: '18px', fontWeight: '800', color: selectedDoc.is_ai_generated ? '#ef4444' : '#10b981' }}>
                  {selectedDoc.is_ai_generated ? `${((selectedDoc.ai_generation_risk || 0) * 100).toFixed(0)}%` : '0%'}
                </div>
              </div>
            </div>

            {/* Visual Heatmap and Original Rendering Canvas */}
            <div style={{ display: 'flex', gap: '16px', justifyContent: 'center', flexWrap: 'wrap', backgroundColor: 'var(--bg-subtle)', padding: '16px', borderRadius: '4px', border: '1px solid var(--border-color)' }}>
              {(forensicViewMode === 'side_by_side' || forensicViewMode === 'original_only') && (
                <div style={{ flex: '1 1 400px', maxWidth: '600px', textAlign: 'center' }}>
                  <div style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-muted)', marginBottom: '6px', fontFamily: 'var(--font-mono)' }}>
                    ORIGINAL RENDER (150 DPI)
                  </div>
                  <img
                    src={getDocumentPageImageUrl(selectedDoc.doc_id, forensicPage)}
                    alt="Original document"
                    style={{ width: '100%', height: 'auto', border: '1px solid var(--border-color)', borderRadius: '2px' }}
                  />
                </div>
              )}

              {(forensicViewMode === 'side_by_side' || forensicViewMode === 'heatmap_only') && (
                <div style={{ flex: '1 1 400px', maxWidth: '600px', textAlign: 'center' }}>
                  <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
                    <span style={{ fontSize: '11px', fontWeight: '700', color: '#f59e0b', fontFamily: 'var(--font-mono)' }}>
                      TAMPERING RESIDUAL HEATMAP (ELA + NOISE)
                    </span>
                  </div>
                  <img
                    src={getDocumentForensicsHeatmapUrl(selectedDoc.doc_id, forensicPage)}
                    alt="Tamper heatmap"
                    style={{ width: '100%', height: 'auto', border: '1px solid var(--border-color)', borderRadius: '2px' }}
                  />
                </div>
              )}
            </div>

            {/* Localized Tamper Regions List */}
            {selectedForensic?.regions && selectedForensic.regions.length > 0 && (
              <div style={{ marginTop: '14px' }}>
                <h4 style={{ margin: '0 0 8px 0', fontSize: '12px', color: 'var(--text-muted)', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>
                  Localized Anomalous Regions ({selectedForensic.regions.length})
                </h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  {selectedForensic.regions.map((reg, idx) => (
                    <div
                      key={idx}
                      style={{
                        padding: '8px 12px',
                        backgroundColor: 'var(--bg-subtle)',
                        border: '1px solid var(--border-color)',
                        borderRadius: '4px',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                      }}
                    >
                      <div>
                        <span style={{ fontSize: '10px', fontWeight: '700', padding: '2px 5px', borderRadius: '3px', backgroundColor: '#f59e0b', color: '#ffffff', marginRight: '8px', fontFamily: 'var(--font-mono)' }}>
                          {reg.technique.toUpperCase()}
                        </span>
                        <span style={{ fontSize: '12px', color: 'var(--text-main)' }}>{reg.description}</span>
                      </div>
                      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                          BBox: [{reg.bbox.join(', ')}]
                        </span>
                        {onJumpToEvidence && (
                          <button
                            onClick={() => onJumpToEvidence(selectedDoc.doc_id, forensicPage, reg.bbox)}
                            className="btn-action"
                            style={{ fontSize: '10.5px', padding: '2px 6px' }}
                          >
                            Inspect on Canvas &rarr;
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 3: CONTEXTUAL REASONING CHAINS */}
      {activeTab === 'reasoning' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {(!analytics?.correlation_clusters || analytics.correlation_clusters.length === 0) ? (
            <div className="panel" style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)' }}>
              No multi-hop anomaly clusters identified. All document signals remain within standard tolerances.
            </div>
          ) : (
            analytics.correlation_clusters.map((cluster: AnomalyCorrelationCluster) => {
              const isHigh = cluster.severity === 'potential_manipulation';
              const isMedium = cluster.severity === 'inconsistency';
              const badgeColor = isHigh ? '#ef4444' : isMedium ? '#f59e0b' : '#3b82f6';

              return (
                <div key={cluster.cluster_id} className="panel" style={{ padding: '16px', backgroundColor: 'var(--bg-panel)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span
                        style={{
                          fontSize: '10px',
                          fontWeight: '800',
                          padding: '3px 8px',
                          borderRadius: '3px',
                          backgroundColor: badgeColor,
                          color: '#ffffff',
                          fontFamily: 'var(--font-mono)',
                          textTransform: 'uppercase',
                        }}
                      >
                        {cluster.severity.replace('_', ' ')}
                      </span>
                      <h3 style={{ margin: 0, fontSize: '15px', fontWeight: '800', color: 'var(--text-main)' }}>
                        {cluster.theme} Vector
                      </h3>
                    </div>
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                      Cluster ID: {cluster.cluster_id}
                    </span>
                  </div>

                  {/* Synthesis Rationale */}
                  <div style={{ padding: '10px 12px', backgroundColor: 'var(--bg-subtle)', borderRadius: '4px', border: '1px solid var(--border-color)', marginBottom: '12px', fontSize: '12.5px', lineHeight: '1.5', color: 'var(--text-main)' }}>
                    <span style={{ fontWeight: '700' }}>Contextual Synthesis: </span>
                    {cluster.synthesis_rationale}
                  </div>

                  {/* Step-by-Step Reasoning Chain */}
                  <h4 style={{ margin: '10px 0 6px 0', fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>
                    Forensic Chain of Evidence ({cluster.chain.length} Step{cluster.chain.length > 1 ? 's' : ''})
                  </h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {cluster.chain.map((step) => (
                      <div
                        key={step.step_index}
                        style={{
                          padding: '10px 12px',
                          border: '1px solid var(--border-color)',
                          borderRadius: '4px',
                          borderLeft: '3px solid var(--accent-main)',
                          backgroundColor: 'var(--bg-panel)',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                          <span style={{ fontSize: '12px', fontWeight: '700', color: 'var(--text-main)' }}>
                            Step {step.step_index}: {step.title}
                          </span>
                          <span style={{ fontSize: '10.5px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                            {(step.confidence * 100).toFixed(0)}% Confidence
                          </span>
                        </div>
                        <div style={{ fontSize: '11.5px', color: 'var(--text-muted)', marginBottom: '4px' }}>
                          <span style={{ fontWeight: '600', color: 'var(--text-main)' }}>Premise: </span>
                          {step.premises.join('; ')}
                        </div>
                        <div style={{ fontSize: '12px', color: 'var(--text-main)', marginBottom: '4px' }}>
                          <span style={{ fontWeight: '600' }}>Observation: </span>
                          {step.observation}
                        </div>
                        <div style={{ fontSize: '12px', fontWeight: '600', color: isHigh ? '#ef4444' : 'var(--text-main)' }}>
                          <span>Conclusion: </span>
                          {step.conclusion}
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Recommended Human Review Action */}
                  <div style={{ marginTop: '12px', padding: '8px 12px', borderRadius: '4px', backgroundColor: 'rgba(59, 130, 246, 0.08)', border: '1px solid rgba(59, 130, 246, 0.3)', fontSize: '12px', color: 'var(--text-main)' }}>
                    <span style={{ fontWeight: '700', color: 'var(--accent-main)' }}>Recommended Human Reviewer Action: </span>
                    {cluster.recommended_inquiry}
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}

      {/* TAB 4: MULTILINGUAL & HANDWRITING */}
      {activeTab === 'multilingual' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div className="panel" style={{ padding: '16px', backgroundColor: 'var(--bg-panel)' }}>
            <h3 style={{ margin: '0 0 6px 0', fontSize: '14px', fontWeight: '700', color: 'var(--text-main)' }}>
              Multilingual Script & Handwriting Intelligence
            </h3>
            <p style={{ margin: '0 0 14px 0', fontSize: '12px', color: 'var(--text-muted)' }}>
              Identifies Indic and Latin scripts, detects handwritten cursive vs machine-printed text, and surfaces signature/annotation patches.
            </p>

            {/* Language and Script Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '12px', marginBottom: '16px' }}>
              <div style={{ padding: '12px', borderRadius: '4px', backgroundColor: 'var(--bg-subtle)', border: '1px solid var(--border-color)' }}>
                <div style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-muted)', marginBottom: '8px', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>
                  Detected Scripts
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  {analytics?.scripts && Object.entries(analytics.scripts).map(([script, count]) => (
                    <span
                      key={script}
                      style={{
                        padding: '4px 8px',
                        borderRadius: '3px',
                        backgroundColor: 'var(--accent-main)',
                        color: '#ffffff',
                        fontSize: '11px',
                        fontWeight: '700',
                        fontFamily: 'var(--font-mono)',
                      }}
                    >
                      {script} ({count} doc{count > 1 ? 's' : ''})
                    </span>
                  ))}
                </div>
              </div>

              <div style={{ padding: '12px', borderRadius: '4px', backgroundColor: 'var(--bg-subtle)', border: '1px solid var(--border-color)' }}>
                <div style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-muted)', marginBottom: '8px', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>
                  Language Distribution
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  {analytics?.languages && Object.entries(analytics.languages).map(([lang, count]) => (
                    <span
                      key={lang}
                      style={{
                        padding: '4px 8px',
                        borderRadius: '3px',
                        backgroundColor: '#10b981',
                        color: '#ffffff',
                        fontSize: '11px',
                        fontWeight: '700',
                        fontFamily: 'var(--font-mono)',
                      }}
                    >
                      {lang.toUpperCase()} ({count})
                    </span>
                  ))}
                </div>
              </div>
            </div>

            {/* Document-level Handwriting Breakdown Table */}
            <h4 style={{ margin: '10px 0 8px 0', fontSize: '12px', color: 'var(--text-muted)', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>
              Document Script & Handwriting Analysis
            </h4>
            <div style={{ overflowX: 'auto', border: '1px solid var(--border-color)', borderRadius: '4px' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '11.5px', textAlign: 'left' }}>
                <thead>
                  <tr style={{ backgroundColor: 'var(--bg-subtle)', borderBottom: '1px solid var(--border-color)', color: 'var(--text-muted)' }}>
                    <th style={{ padding: '8px 10px' }}>Document</th>
                    <th style={{ padding: '8px 10px' }}>Primary Script</th>
                    <th style={{ padding: '8px 10px' }}>Languages</th>
                    <th style={{ padding: '8px 10px' }}>Handwriting Status</th>
                    <th style={{ padding: '8px 10px' }}>Handwriting Ratio</th>
                  </tr>
                </thead>
                <tbody>
                  {documents.map((doc) => (
                    <tr key={doc.doc_id} style={{ borderBottom: '1px solid var(--border-color)' }}>
                      <td style={{ padding: '8px 10px', fontWeight: '600', color: 'var(--text-main)' }}>
                        {doc.filename} ({doc.doc_id})
                      </td>
                      <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)' }}>
                        {doc.scripts?.join(', ') || 'Latin'}
                      </td>
                      <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)' }}>
                        {doc.detected_languages?.join(', ').toUpperCase() || 'EN'}
                      </td>
                      <td style={{ padding: '8px 10px' }}>
                        <span
                          style={{
                            fontSize: '9.5px',
                            fontWeight: '700',
                            padding: '2px 6px',
                            borderRadius: '3px',
                            backgroundColor: doc.has_handwriting ? '#f59e0b' : '#3b82f6',
                            color: '#ffffff',
                            textTransform: 'uppercase',
                          }}
                        >
                          {doc.has_handwriting ? 'Contains Handwriting' : 'Machine Printed'}
                        </span>
                      </td>
                      <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)', fontWeight: '700' }}>
                        {((doc.handwriting_ratio || 0) * 100).toFixed(1)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
