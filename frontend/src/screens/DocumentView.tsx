import React, { useState, useEffect } from 'react';
import { DocumentRecord, ExtractedField, BBox } from '../types';
import {
  getDocumentFields,
  getDocumentPageImageUrl,
  getDocumentForensicsHeatmapUrl,
  revealField,
} from '../api/client';

interface DocumentViewProps {
  documents: DocumentRecord[];
  activeDocId?: string;
  initialPage?: number;
  highlightBBox?: BBox | null;
  onSelectDoc?: (docId: string) => void;
}

export const DocumentView: React.FC<DocumentViewProps> = ({
  documents,
  activeDocId,
  initialPage = 1,
  highlightBBox,
  onSelectDoc,
}) => {
  const currentDocId = activeDocId || (documents[0]?.doc_id ?? '');
  const currentDoc = documents.find((d) => d.doc_id === currentDocId);

  const [currentPage, setCurrentPage] = useState<number>(initialPage);

  useEffect(() => {
    if (initialPage) {
      setCurrentPage(initialPage);
    }
  }, [initialPage, activeDocId]);
  const [fields, setFields] = useState<ExtractedField[]>([]);
  const [hoveredFieldId, setHoveredFieldId] = useState<string | null>(null);
  const [revealedValues, setRevealedValues] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState<boolean>(false);
  const [imgDimensions, setImgDimensions] = useState<{ width: number; height: number } | null>(null);
  const [fieldFilter, setFieldFilter] = useState<'all' | 'entities' | 'lines'>('all');
  const [showForensicsOverlay, setShowForensicsOverlay] = useState<boolean>(false);

  useEffect(() => {
    if (!currentDocId) return;
    setLoading(true);
    getDocumentFields(currentDocId)
      .then((data) => setFields(data))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, [currentDocId]);

  const handleReveal = async (fieldId: string) => {
    try {
      const res = await revealField(fieldId);
      setRevealedValues((prev) => ({ ...prev, [fieldId]: String(res.unmasked_value) }));
    } catch (err) {
      console.error(err);
    }
  };

  if (!currentDoc) {
    return (
      <div style={{ padding: '40px', textAlign: 'center', color: '#94a3b8' }}>
        No document selected. Please upload and process a document bundle.
      </div>
    );
  }

  const pageFields = fields.filter((f) => f.page === currentPage);
  const imageUrl = getDocumentPageImageUrl(currentDoc.doc_id, currentPage);

  return (
    <div style={{ display: 'flex', gap: '16px', height: 'calc(100vh - 140px)' }}>
      {/* Left: Document View with BBox Overlay */}
      <div
        className="panel"
        style={{
          flex: '1 1 65%',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          backgroundColor: 'var(--bg-panel)',
        }}
      >
        {/* Document Header Controls */}
        <div
          style={{
            padding: '8px 14px',
            backgroundColor: 'var(--bg-subtle)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            borderBottom: '1px solid var(--border-color)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <select
              value={currentDoc.doc_id}
              onChange={(e) => onSelectDoc && onSelectDoc(e.target.value)}
              style={{
                backgroundColor: 'var(--bg-panel)',
                color: 'var(--text-main)',
                border: '1px solid var(--border-color)',
                padding: '4px 10px',
                borderRadius: '4px',
                fontSize: '12px',
                fontFamily: 'var(--font-mono)',
              }}
            >
              {documents.map((d) => (
                <option key={d.doc_id} value={d.doc_id}>
                  {d.filename} ({d.type.toUpperCase()})
                </option>
              ))}
            </select>
            <span
              style={{
                fontSize: '10px',
                fontWeight: '700',
                padding: '2px 6px',
                borderRadius: '4px',
                textTransform: 'uppercase',
                fontFamily: 'var(--font-mono)',
                backgroundColor: currentDoc.status === 'processed' ? '#064e3b' : 'var(--tier-manip)',
                color: '#FFFFFF',
              }}
            >
              {currentDoc.status}
            </span>

            {/* Multilingual & Handwriting Badges */}
            <span
              style={{
                fontSize: '10px',
                fontWeight: '700',
                padding: '2px 6px',
                borderRadius: '3px',
                fontFamily: 'var(--font-mono)',
                backgroundColor: currentDoc.has_handwriting ? '#f59e0b' : '#3b82f6',
                color: '#FFFFFF',
              }}
            >
              {currentDoc.has_handwriting ? 'HANDWRITING' : 'PRINTED'}
            </span>

            {currentDoc.scripts && currentDoc.scripts.some((s) => s !== 'Latin') && (
              <span
                style={{
                  fontSize: '10px',
                  fontWeight: '700',
                  padding: '2px 6px',
                  borderRadius: '3px',
                  fontFamily: 'var(--font-mono)',
                  backgroundColor: '#8b5cf6',
                  color: '#FFFFFF',
                }}
              >
                {currentDoc.scripts.filter((s) => s !== 'Latin').join(', ')}
              </span>
            )}

            {/* AI Generated Document Badge */}
            {currentDoc.is_ai_generated && (
              <span
                title={currentDoc.ai_generation_reasoning || 'AI-generated / synthetic content detected'}
                style={{
                  fontSize: '10px',
                  fontWeight: '700',
                  padding: '2px 6px',
                  borderRadius: '3px',
                  fontFamily: 'var(--font-mono)',
                  backgroundColor: '#dc2626',
                  color: '#FFFFFF',
                  border: '1px solid #ef4444',
                }}
              >
                🤖 AI-GENERATED ({((currentDoc.ai_generation_risk || 0) * 100).toFixed(0)}%)
              </span>
            )}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {/* Tamper Heatmap Overlay Toggle */}
            <button
              type="button"
              onClick={() => setShowForensicsOverlay(!showForensicsOverlay)}
              className={`btn-action ${showForensicsOverlay ? 'btn-accent' : ''}`}
              style={{
                padding: '3px 8px',
                fontSize: '11px',
                backgroundColor: showForensicsOverlay ? '#f59e0b' : undefined,
                color: showForensicsOverlay ? '#ffffff' : undefined,
                borderColor: showForensicsOverlay ? '#d97706' : undefined,
                fontWeight: '600',
              }}
            >
              {showForensicsOverlay ? '🔥 Tamper Heatmap (Active)' : '🔍 Tamper Overlay'}
            </button>

            {currentDoc.pages > 1 && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <button
                  disabled={currentPage <= 1}
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  className="btn-action"
                  style={{ padding: '2px 8px', fontSize: '11px' }}
                >
                  &larr; Prev
                </button>
                <span style={{ fontSize: '12px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                  Page {currentPage} of {currentDoc.pages}
                </span>
                <button
                  disabled={currentPage >= currentDoc.pages}
                  onClick={() => setCurrentPage((p) => Math.min(currentDoc.pages, p + 1))}
                  className="btn-action"
                  style={{ padding: '2px 8px', fontSize: '11px' }}
                >
                  Next &rarr;
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Rendered Document Canvas with SVG BBox Overlays */}
        <div
          style={{
            flex: 1,
            overflow: 'auto',
            padding: '16px',
            display: 'flex',
            justifyContent: 'center',
            backgroundColor: 'var(--bg-main)',
          }}
        >
          <div style={{ position: 'relative', display: 'inline-block' }}>
            <img
              src={
                showForensicsOverlay
                  ? getDocumentForensicsHeatmapUrl(currentDoc.doc_id, currentPage)
                  : imageUrl
              }
              alt={`Page ${currentPage}`}
              onLoad={(e) => {
                const target = e.currentTarget;
                setImgDimensions({ width: target.naturalWidth, height: target.naturalHeight });
              }}
              style={{
                display: 'block',
                maxWidth: '100%',
                border: '1px solid var(--border-color)',
                borderRadius: '2px',
              }}
            />

            {/* Bounding Box Overlay SVG (2px border, 10% fill, hover flash) */}
            <svg
              viewBox={imgDimensions ? `0 0 ${imgDimensions.width} ${imgDimensions.height}` : undefined}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                height: '100%',
                pointerEvents: 'none',
              }}
            >
              {pageFields.map((f) => {
                const isHovered = hoveredFieldId === f.field_id;
                const [x0, y0, x1, y1] = f.bbox;
                const width = Math.max(2, x1 - x0);
                const height = Math.max(2, y1 - y0);

                return (
                  <g key={f.field_id}>
                    <rect
                      x={x0}
                      y={y0}
                      width={width}
                      height={height}
                      fill={isHovered ? 'var(--highlight-flash)' : 'var(--overlay-bg)'}
                      stroke={isHovered ? 'var(--accent-main)' : 'var(--overlay-border)'}
                      strokeWidth={2}
                    />
                    {isHovered && (
                      <text
                        x={x0}
                        y={Math.max(10, y0 - 3)}
                        fill="var(--overlay-border)"
                        fontSize="9px"
                        fontFamily="var(--font-mono)"
                        fontWeight="bold"
                      >
                        {f.name}
                      </text>
                    )}
                  </g>
                );
              })}

              {/* Dedicated finding highlight box if present */}
              {highlightBBox && (
                <rect
                  x={highlightBBox[0]}
                  y={highlightBBox[1]}
                  width={highlightBBox[2] - highlightBBox[0]}
                  height={highlightBBox[3] - highlightBBox[1]}
                  fill="var(--highlight-flash)"
                  stroke="var(--overlay-border)"
                  strokeWidth={2}
                  className="flash-target"
                />
              )}
            </svg>
          </div>
        </div>
      </div>

      {/* Right: Extracted Fields Sidebar */}
      <div
        className="panel"
        style={{
          flex: '1 1 35%',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          backgroundColor: 'var(--bg-panel)',
        }}
      >
        <div
          style={{
            padding: '8px 14px',
            backgroundColor: 'var(--bg-subtle)',
            borderBottom: '1px solid var(--border-color)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <h3 style={{ margin: 0, fontSize: '13px', color: 'var(--text-main)', fontWeight: '700' }}>
            Extracted Fields ({pageFields.length})
          </h3>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>DPI: 150</span>
        </div>

        {/* LLM Document Classification Card */}
        <div
          className="panel"
          style={{
            margin: '10px 10px 4px 10px',
            padding: '12px',
            backgroundColor: 'var(--bg-subtle)',
            border: '1px solid var(--border-color)',
            borderRadius: '4px',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>
              LLM Classification Analysis
            </span>
            <span
              style={{
                fontSize: '10px',
                fontWeight: '700',
                padding: '2px 6px',
                borderRadius: '3px',
                backgroundColor: '#0369a1',
                color: '#ffffff',
                fontFamily: 'var(--font-mono)',
              }}
            >
              {currentDoc.llm_provider || 'Local Semantic Engine'}
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', marginBottom: '6px' }}>
            <span style={{ fontSize: '14px', fontWeight: '800', color: 'var(--text-main)' }}>
              {currentDoc.llm_type ? currentDoc.llm_type.toUpperCase().replace('_', ' ') : currentDoc.type.toUpperCase().replace('_', ' ')}
            </span>
            <span style={{ fontSize: '12px', fontWeight: '700', color: '#10b981', fontFamily: 'var(--font-mono)' }}>
              {currentDoc.llm_accuracy ? `${(currentDoc.llm_accuracy * 100).toFixed(1)}% Accuracy` : `${(currentDoc.type_confidence * 100).toFixed(1)}% Confidence`}
            </span>
          </div>

          {currentDoc.llm_reasoning && (
            <div style={{ fontSize: '11.5px', color: 'var(--text-muted)', lineHeight: '1.45', backgroundColor: 'var(--bg-panel)', padding: '8px', borderRadius: '4px', border: '1px solid var(--border-color)' }}>
              <span style={{ fontWeight: '600', color: 'var(--text-main)' }}>LLM Rationale: </span>
              {currentDoc.llm_reasoning}
            </div>
          )}
        </div>

        {/* Filter Segmented Control */}
        <div style={{ display: 'flex', gap: '6px', margin: '8px 10px 4px 10px' }}>
          <button
            type="button"
            onClick={() => setFieldFilter('all')}
            style={{
              flex: 1,
              padding: '4px 6px',
              fontSize: '11px',
              fontFamily: 'var(--font-mono)',
              borderRadius: '4px',
              border: '1px solid var(--border-color)',
              backgroundColor: fieldFilter === 'all' ? 'var(--accent-main)' : 'var(--bg-subtle)',
              color: fieldFilter === 'all' ? '#ffffff' : 'var(--text-muted)',
              cursor: 'pointer',
              fontWeight: fieldFilter === 'all' ? '700' : '500',
            }}
          >
            All ({pageFields.length})
          </button>
          <button
            type="button"
            onClick={() => setFieldFilter('entities')}
            style={{
              flex: 1,
              padding: '4px 6px',
              fontSize: '11px',
              fontFamily: 'var(--font-mono)',
              borderRadius: '4px',
              border: '1px solid var(--border-color)',
              backgroundColor: fieldFilter === 'entities' ? 'var(--accent-main)' : 'var(--bg-subtle)',
              color: fieldFilter === 'entities' ? '#ffffff' : 'var(--text-muted)',
              cursor: 'pointer',
              fontWeight: fieldFilter === 'entities' ? '700' : '500',
            }}
          >
            Entities ({pageFields.filter((f) => !f.name.startsWith('line_') && !f.name.startsWith('text_line_')).length})
          </button>
          <button
            type="button"
            onClick={() => setFieldFilter('lines')}
            style={{
              flex: 1,
              padding: '4px 6px',
              fontSize: '11px',
              fontFamily: 'var(--font-mono)',
              borderRadius: '4px',
              border: '1px solid var(--border-color)',
              backgroundColor: fieldFilter === 'lines' ? 'var(--accent-main)' : 'var(--bg-subtle)',
              color: fieldFilter === 'lines' ? '#ffffff' : 'var(--text-muted)',
              cursor: 'pointer',
              fontWeight: fieldFilter === 'lines' ? '700' : '500',
            }}
          >
            OCR Lines ({pageFields.filter((f) => f.name.startsWith('line_') || f.name.startsWith('text_line_')).length})
          </button>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '10px' }}>
          {loading ? (
            <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-muted)' }}>Loading fields...</div>
          ) : pageFields.length === 0 ? (
            <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '12px' }}>
              No structured fields extracted on this page.
            </div>
          ) : (
            (() => {
              const isLineField = (name: string) => name.startsWith('line_') || name.startsWith('text_line_');
              const displayed =
                fieldFilter === 'entities'
                  ? pageFields.filter((f) => !isLineField(f.name))
                  : fieldFilter === 'lines'
                  ? pageFields.filter((f) => isLineField(f.name))
                  : pageFields;

              if (displayed.length === 0) {
                return (
                  <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '12px' }}>
                    No fields match the selected filter.
                  </div>
                );
              }

              return displayed.map((f) => {
                const displayVal = revealedValues[f.field_id] || (typeof f.value === 'object' ? JSON.stringify(f.value) : String(f.value));
                const isMasked = f.name.includes('aadhaar') || f.name.includes('pan');
                const isRevealed = Boolean(revealedValues[f.field_id]);
                const isHovered = hoveredFieldId === f.field_id;
                const isLine = isLineField(f.name);

                return (
                  <div
                    key={f.field_id}
                    onMouseEnter={() => setHoveredFieldId(f.field_id)}
                    onMouseLeave={() => setHoveredFieldId(null)}
                    className="panel"
                    style={{
                      backgroundColor: isHovered ? 'var(--bg-subtle)' : 'var(--bg-panel)',
                      borderColor: isHovered ? 'var(--accent-main)' : isLine ? 'var(--border-color)' : '#38bdf8',
                      borderLeftWidth: isLine ? '2px' : '4px',
                      padding: '8px 10px',
                      marginBottom: '6px',
                      transition: 'border-color 0.15s ease',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '3px' }}>
                      <span style={{ fontSize: '11px', fontWeight: '700', color: isLine ? 'var(--text-muted)' : 'var(--text-main)', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>
                        {isLine ? f.name.replace(/_/g, ' ').toUpperCase() : f.name.replace(/_/g, ' ')}
                      </span>
                      <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
                        {f.is_handwritten && (
                          <span
                            style={{
                              fontSize: '9px',
                              fontWeight: '700',
                              backgroundColor: '#f59e0b',
                              color: '#ffffff',
                              padding: '1px 5px',
                              borderRadius: '3px',
                              fontFamily: 'var(--font-mono)',
                            }}
                          >
                            HANDWRITTEN
                          </span>
                        )}
                        {f.script && f.script !== 'Latin' && (
                          <span
                            style={{
                              fontSize: '9px',
                              fontWeight: '700',
                              backgroundColor: '#0284c7',
                              color: '#ffffff',
                              padding: '1px 5px',
                              borderRadius: '3px',
                              fontFamily: 'var(--font-mono)',
                            }}
                          >
                            {f.script}
                          </span>
                        )}
                        <span
                          style={{
                            fontSize: '9.5px',
                            backgroundColor: 'var(--bg-subtle)',
                            color: 'var(--text-muted)',
                            padding: '1px 4px',
                            borderRadius: '3px',
                            border: '1px solid var(--border-color)',
                            fontFamily: 'var(--font-mono)',
                          }}
                        >
                          {f.source}
                        </span>
                        <span
                          style={{
                            fontSize: '9.5px',
                            fontWeight: '700',
                            backgroundColor: 'var(--bg-subtle)',
                            color: f.confidence >= 0.85 ? '#059669' : 'var(--tier-incons)',
                            border: '1px solid var(--border-color)',
                            padding: '1px 4px',
                            borderRadius: '3px',
                            fontFamily: 'var(--font-mono)',
                          }}
                        >
                          {(f.confidence * 100).toFixed(0)}%
                        </span>
                      </div>
                    </div>

                    <div style={{ fontSize: '12.5px', color: 'var(--text-main)', wordBreak: 'break-word', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>
                      {f.unable_to_assess ? (
                        <span style={{ color: 'var(--tier-manip)', fontStyle: 'italic', fontFamily: 'var(--font-sans)' }}>Unable to assess this field</span>
                      ) : (
                        displayVal
                      )}
                    </div>

                    {isMasked && !f.unable_to_assess && (
                      <div style={{ marginTop: '6px', display: 'flex', justifyContent: 'flex-end' }}>
                        <button
                          onClick={() => handleReveal(f.field_id)}
                          disabled={isRevealed}
                          className="btn-action"
                          style={{
                            fontSize: '10px',
                            padding: '2px 6px',
                          }}
                        >
                          {isRevealed ? 'Revealed (Audited)' : 'Reveal (Audit-Logged)'}
                        </button>
                      </div>
                    )}
                  </div>
                );
              });
            })()
          )}
        </div>
      </div>
    </div>
  );
};
