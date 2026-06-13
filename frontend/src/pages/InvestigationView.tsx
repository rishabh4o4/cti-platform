/* eslint-disable @typescript-eslint/no-explicit-any */
import { useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import { RiskBadge } from '@/components/shared/RiskBadge';
import { AlertTriangle, Clock, Hash, ShieldAlert, User, Send, Tag, X, Activity, Download, ChevronRight, FileText, RotateCcw } from 'lucide-react';
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { ErrorState } from '@/components/shared/ErrorState';
import { Skeleton } from '@/components/shared/Skeleton';
import { EmptyState } from '@/components/shared/EmptyState';
import { MitreAutocomplete } from '@/components/shared/MitreAutocomplete';
import { usePermission } from '@/lib/rbac';
import { Permission } from '@/types';
import { ReadOnlyBadge } from '@/components/shared/ReadOnlyBadge';

const fetchInvestigation = async (id: string) => {
  const [content, analysis, notes, auditLogs] = await Promise.all([
    api.get(`/content/${id}`),
    api.get(`/analysis/${id}`),
    api.get(`/content/${id}/notes`),
    api.get(`/audit_log?content_id=${id}`)
  ]);
  return { content: content.data, analysis: analysis.data, notes: notes.data, auditLogs: auditLogs.data };
};

function RelatedThreats({ authorHandle, currentId }: { authorHandle: string; currentId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['relatedThreats', authorHandle],
    queryFn: async () => {
      const { data } = await api.get(`/search`, { params: { q: authorHandle, limit: 6 } });
      return (data.results || []).filter((r: any) => r.id !== currentId).slice(0, 5);
    },
    enabled: !!authorHandle,
    staleTime: 60000,
  });

  if (isLoading || !data || data.length === 0) return null;

  return (
    <div className="bg-surface border border-border rounded-xl p-6 shadow-sm">
      <h2 className="text-lg font-semibold text-text-primary mb-4 flex items-center">
        <AlertTriangle className="h-5 w-5 mr-2 text-medium" /> Related by Author
      </h2>
      <div className="space-y-2">
        {data.map((item: any) => (
          <Link
            key={item.id}
            to={item.url}
            className="block p-3 rounded-lg border border-border hover:bg-border/50 transition-colors"
          >
            <p className="text-sm text-text-primary line-clamp-1 font-medium">{item.title}</p>
            <p className="text-xs text-text-secondary mt-1">{item.subtitle}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}

export default function InvestigationView() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [newNote, setNewNote] = useState('');
  const [newTactic, setNewTactic] = useState('');
  const [newTechnique, setNewTechnique] = useState('');
  const [showNoteConfirm, setShowNoteConfirm] = useState(false);
  const [pendingTemplate, setPendingTemplate] = useState('');
  const [reliabilityRating, setReliabilityRating] = useState('C / 2');
  const [isGeneratingPdf, setIsGeneratingPdf] = useState(false);

  const canAddNotes = usePermission(Permission.ADD_NOTES);
  const canInvestigate = usePermission(Permission.INVESTIGATE);
  const canExportPdf = usePermission(Permission.EXPORT_PDF);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['investigation', id],
    queryFn: () => fetchInvestigation(id!),
    enabled: !!id,
  });

  const { data: reports } = useQuery({
    queryKey: ['reports', id],
    queryFn: async () => (await api.get('/export/reports', { params: { content_id: id } })).data,
    enabled: !!id,
  });

  const updateStatusMutation = useMutation({
    mutationFn: (newStatus: string) => api.patch(`/content/${id}/status`, { status: newStatus }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['investigation', id] });
      toast.success('Investigation status updated');
    },
    onError: () => toast.error('Failed to update status'),
  });

  const addNoteMutation = useMutation({
    mutationFn: (note: string) => api.post(`/content/${id}/notes`, { note }),
    onSuccess: () => {
      setNewNote('');
      queryClient.invalidateQueries({ queryKey: ['investigation', id] });
      toast.success('Note added successfully');
    },
    onError: () => toast.error('Failed to add note'),
  });

  const updateAnalysisMutation = useMutation({
    mutationFn: (payload: { tactics?: string[], techniques?: string[] }) => api.patch(`/analysis/${id}`, payload),
    onSuccess: () => {
      setNewTactic('');
      setNewTechnique('');
      queryClient.invalidateQueries({ queryKey: ['investigation', id] });
      toast.success('Tags updated');
    },
    onError: () => toast.error('Failed to update tags'),
  });

  const navigate = useNavigate();

  const handleAddNote = (e: React.FormEvent) => {
    e.preventDefault();
    if (newNote.trim()) {
      addNoteMutation.mutate(newNote);
    }
  };

  const handleAddTag = (type: 'tactics' | 'techniques', value: string) => {
    if (!value.trim() || !data?.analysis) return;
    const current = data.analysis[type] || [];
    if (!current.includes(value.trim())) {
      updateAnalysisMutation.mutate({ [type]: [...current, value.trim()] });
    }
  };

  const handleRemoveTag = (type: 'tactics' | 'techniques', value: string) => {
    if (!data?.analysis) return;
    const current = data.analysis[type] || [];
    updateAnalysisMutation.mutate({ [type]: current.filter((t: string) => t !== value) });
  };

  const handleExport = () => {
    if (!data) return;
    
    const exportData = {
      caseId: id,
      exportedAt: new Date().toISOString(),
      content: data.content,
      analysis: {
        ...data.analysis,
        weightsSnapshot: data.analysis.score_breakdown, // full {raw, max, pct} breakdown
      },
      notes: data.notes,
      chainOfCustody: data.auditLogs,
    };

    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `investigation_export_${id}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleExportPdf = async () => {
    try {
      setIsGeneratingPdf(true);
      const res = await api.post(`/export/${id}/pdf`, null, {
        responseType: 'blob',
        params: { source_reliability_rating: reliabilityRating }
      });
      const blob = new Blob([res.data], { type: 'application/pdf' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `evidence_report_CASE-${id!.slice(0, 8).toUpperCase()}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast.success('Report downloaded');
      queryClient.invalidateQueries({ queryKey: ['reports', id] });
    } catch {
      toast.error('Failed to generate PDF report');
    } finally {
      setIsGeneratingPdf(false);
    }
  };

  if (isLoading) {
    return (
      <div className="max-w-6xl mx-auto space-y-6">
        <div className="flex items-center justify-between border-b border-border pb-4">
          <div className="space-y-2">
            <Skeleton className="h-4 w-64" />
            <Skeleton className="h-4 w-48" />
          </div>
          <div className="flex flex-col items-end gap-2">
            <Skeleton className="h-6 w-20" />
            <Skeleton className="h-6 w-24" />
          </div>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            <div className="bg-surface border border-border rounded-xl p-6 shadow-sm h-64">
              <Skeleton className="h-6 w-48 mb-4" />
              <div className="space-y-2">
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-3/4" />
              </div>
            </div>
          </div>
          <div className="space-y-6">
            <div className="bg-surface border border-border rounded-xl p-6 shadow-sm h-64">
              <Skeleton className="h-6 w-32 mb-4" />
              <Skeleton className="h-4 w-full mb-2" />
              <Skeleton className="h-4 w-full mb-2" />
              <Skeleton className="h-4 w-2/3" />
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="max-w-6xl mx-auto space-y-6">
        <ErrorState title="Failed to load investigation" message="An error occurred while fetching the case details." onRetry={refetch} />
      </div>
    );
  }

  if (!data || !data.content) {
    return (
      <div className="max-w-6xl mx-auto space-y-6">
        <EmptyState title="Investigation Not Found" message="The requested investigation could not be found or you do not have permission to view it." />
      </div>
    );
  }

  const { content, analysis, notes, auditLogs } = data;
  const sortedAuditLogs = auditLogs ? [...auditLogs] : [];

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex items-center text-sm text-text-secondary">
        <Link to="/" className="hover:text-primary transition-colors">Dashboard</Link>
        <ChevronRight className="h-4 w-4 mx-1" />
        <Link to="/alerts" className="hover:text-primary transition-colors">Alerts</Link>
        <ChevronRight className="h-4 w-4 mx-1" />
        <span className="text-text-primary">Investigation</span>
      </div>

      <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-border pb-4 gap-4">
        <div>
          <h1 className="text-2xl font-bold text-text-primary mb-1">{content.author_handle ? `@${content.author_handle}` : content.source_id}</h1>
          <div className="flex flex-wrap items-center gap-4 text-sm text-text-secondary">
            <span className="flex items-center"><Hash className="h-4 w-4 mr-1"/> {content.source}</span>
            <span className="flex items-center"><Clock className="h-4 w-4 mr-1"/> {new Date(content.collected_at).toLocaleString()}</span>
            <ReadOnlyBadge />
          </div>
        </div>
        <div className="flex flex-col sm:items-end gap-2">
          <div className="flex flex-wrap items-center gap-2">
            {content.status === 'closed' ? (
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium px-3 py-1.5 rounded-md border bg-low/10 text-low border-low/20">Closed</span>
                <button
                  onClick={() => updateStatusMutation.mutate('open')}
                  disabled={updateStatusMutation.isPending}
                  className="flex items-center text-xs font-medium px-3 py-1.5 rounded-md border bg-surface border-border text-text-primary hover:bg-background transition-colors focus:outline-none focus:ring-2 focus:ring-primary"
                >
                  <RotateCcw className="h-3.5 w-3.5 mr-1" /> Re-open Case
                </button>
              </div>
            ) : (
              <select
                value={content.status || 'open'}
                onChange={(e) => updateStatusMutation.mutate(e.target.value)}
                disabled={updateStatusMutation.isPending || !canInvestigate}
                className={`text-xs font-medium px-3 py-1.5 rounded-md border focus:outline-none focus:ring-2 focus:ring-primary transition-colors ${canInvestigate ? 'cursor-pointer' : 'cursor-not-allowed opacity-75'} ${
                  content.status === 'escalated' ? 'bg-critical/10 text-critical border-critical/20' :
                  content.status === 'under_review' ? 'bg-medium/10 text-medium border-medium/20' :
                  'bg-primary/10 text-primary border-primary/20'
                } disabled:opacity-50`}
                aria-label="Investigation status"
              >
                <option value="open">Open</option>
                <option value="under_review">Under Review</option>
                <option value="escalated">Escalated</option>
                <option value="closed">Closed</option>
              </select>
            )}
            <button 
              onClick={handleExport}
              className="flex items-center text-xs font-medium bg-surface border border-border text-text-secondary px-3 py-1 rounded hover:bg-background hover:text-text-primary transition-colors"
            >
              <Download className="h-4 w-4 mr-1.5" />
              Export JSON
            </button>
            <div className="flex items-center bg-surface border border-border rounded overflow-hidden">
              <select
                value={reliabilityRating}
                onChange={(e) => setReliabilityRating(e.target.value)}
                disabled={!canExportPdf}
                className="text-xs font-medium bg-transparent text-text-secondary px-2 py-1 focus:outline-none focus:ring-0 cursor-pointer border-r border-border disabled:opacity-50 disabled:cursor-not-allowed"
                aria-label="Source reliability rating"
              >
                <option value="A / 1">A / 1</option>
                <option value="B / 2">B / 2</option>
                <option value="C / 2">C / 2</option>
                <option value="C / 3">C / 3</option>
                <option value="F / 6">F / 6</option>
              </select>
              {canExportPdf && (
                <button 
                  onClick={handleExportPdf}
                  disabled={isGeneratingPdf}
                  className="flex items-center text-xs font-medium bg-transparent text-text-secondary px-3 py-1 hover:bg-background hover:text-text-primary transition-colors disabled:opacity-50"
                >
                  <FileText className="h-4 w-4 mr-1.5" />
                  {isGeneratingPdf ? 'Generating...' : 'Export PDF'}
                </button>
              )}
            </div>
            <RiskBadge level={analysis?.risk_label || 'low'} className="text-sm px-3 py-1" />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-surface border border-border rounded-xl p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-text-primary mb-4">Original Content</h2>
            <div className="bg-background border border-border rounded-lg p-4 text-text-primary whitespace-pre-wrap font-mono text-sm overflow-x-auto mb-4">
              {content.raw_text}
            </div>
            
            {analysis?.nlp_flags?.entities && Object.keys(analysis.nlp_flags.entities).length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-text-primary mb-2">Extracted Entities</h3>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(analysis.nlp_flags.entities).map(([type, entities]: [string, any]) => (
                    Array.isArray(entities) && entities.map((e: string, i: number) => (
                      <button
                        key={`${type}-${i}`}
                        onClick={() => navigate(`/feed?entity=${encodeURIComponent(e)}`)}
                        className="px-2 py-1 bg-medium/10 border border-medium/20 text-medium text-xs rounded-md font-mono hover:bg-medium/20 hover:border-medium/40 transition-colors cursor-pointer"
                        title={`Search for all content mentioning ${e}`}
                        aria-label={`Pivot to threat feed for entity ${type}: ${e}`}
                      >
                        {type}: {e}
                      </button>
                    ))
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="bg-surface border border-border rounded-xl p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-text-primary mb-4 flex items-center">
              <User className="h-5 w-5 mr-2 text-primary" /> Analyst Notes
            </h2>
            
            {canAddNotes && (
              <form onSubmit={handleAddNote} className="mb-6 space-y-2">
                <div className="flex gap-2 mb-2">
                  <select
                    onChange={(e) => {
                      const template = e.target.value;
                      if (template) {
                        if (newNote.trim()) {
                          setPendingTemplate(template);
                          setShowNoteConfirm(true);
                        } else {
                          setNewNote(template);
                        }
                        e.target.value = '';
                      }
                    }}
                    className="bg-background border border-border rounded-md text-xs px-2 py-1 text-text-secondary focus:outline-none focus:ring-2 focus:ring-primary"
                    aria-label="Insert note template"
                    defaultValue=""
                  >
                    <option value="" disabled>Insert template…</option>
                    <option value={"## Initial Assessment\n\n**Risk Level:** \n**Summary:** \n**Immediate Actions Required:** \n**Assigned To:** "}>Initial Assessment</option>
                    <option value={"## Escalation Note\n\n**Reason for Escalation:** \n**Escalated To:** \n**Priority:** \n**Supporting Evidence:** "}>Escalation Note</option>
                    <option value={"## Closure Summary\n\n**Resolution:** \n**Findings:** \n**Recommendations:** \n**Case Linked:** "}>Closure Summary</option>
                    <option value={"## Evidence Chain\n\n**Source:** \n**Hash/Identifier:** \n**Chain of Custody:** \n**Forensic Notes:** "}>Evidence Chain</option>
                  </select>
                </div>
                
                {showNoteConfirm && (
                  <div className="bg-medium/10 border border-medium rounded-lg p-3 mb-2 flex items-center justify-between text-sm">
                    <span className="text-text-primary">This will replace your current draft. Continue?</span>
                    <div className="flex items-center gap-2">
                      <button type="button" onClick={() => setShowNoteConfirm(false)} className="px-3 py-1 rounded bg-surface border border-border text-text-secondary hover:text-text-primary">Cancel</button>
                      <button type="button" onClick={() => { setNewNote(pendingTemplate); setShowNoteConfirm(false); setPendingTemplate(''); }} className="px-3 py-1 rounded bg-medium text-white hover:bg-medium/90">Replace</button>
                    </div>
                  </div>
                )}
                
                <div className="flex gap-3">
                  <textarea
                    value={newNote}
                    onChange={(e) => setNewNote(e.target.value)}
                    placeholder="Add a new note... Use templates above for structured entries."
                    className="flex-1 bg-background border border-border rounded-lg px-4 py-2 text-text-primary focus:outline-none focus:ring-2 focus:ring-primary/50 min-h-[80px] resize-y text-sm"
                    disabled={addNoteMutation.isPending}
                    rows={3}
                  />
                  <button
                    type="submit"
                    disabled={!newNote.trim() || addNoteMutation.isPending}
                    className="bg-primary hover:bg-primary-hover text-white px-4 py-2 rounded-lg font-medium transition-colors flex items-center self-end disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <Send className="h-4 w-4 mr-2" /> Add Note
                  </button>
                </div>
              </form>
            )}

            <div className="space-y-4">
              {notes && notes.length > 0 ? (
                notes.map((note: any) => (
                  <div key={note.id} className="bg-background border border-border rounded-lg p-4">
                    <div className="flex justify-between items-start mb-2">
                      <span className="font-semibold text-text-primary text-sm">{note.author}</span>
                      <span className="text-xs text-text-secondary">
                        {new Date(note.created_at).toLocaleString()}
                      </span>
                    </div>
                    <p className="text-text-primary text-sm whitespace-pre-wrap">{note.note}</p>
                  </div>
                ))
              ) : (
                <div className="text-center py-6 text-text-secondary text-sm">
                  No analyst notes added yet.
                </div>
              )}
            </div>
          </div>
          
          <div className="bg-surface border border-border rounded-xl p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-text-primary mb-4 flex items-center">
              <Activity className="h-5 w-5 mr-2 text-primary" /> Chain of Custody
            </h2>
            <div className="space-y-4">
              {sortedAuditLogs && sortedAuditLogs.length > 0 ? (
                sortedAuditLogs.map((log: any) => (
                  <div key={log.id} className="border-l-2 border-border pl-4 py-1">
                    <div className="flex justify-between items-start mb-1">
                      <span className="font-semibold text-text-primary text-sm">{log.action}</span>
                      <span className="text-xs text-text-secondary">
                        {new Date(log.timestamp).toLocaleString()}
                      </span>
                    </div>
                    <div className="text-xs text-text-secondary">By: {log.analyst}</div>
                    {log.details && (
                      <p className="text-text-primary text-sm mt-1 whitespace-pre-wrap bg-background p-2 rounded">
                        {log.details}
                      </p>
                    )}
                  </div>
                ))
              ) : (
                <div className="text-center py-6 text-text-secondary text-sm">
                  No audit logs available.
                </div>
              )}
            </div>
          </div>

          {/* Related Threats by Same Author */}
          {content.author_handle && (
            <RelatedThreats authorHandle={content.author_handle} currentId={id!} />
          )}
        </div>

        <div className="space-y-6">
          <div className="bg-surface border border-border rounded-xl p-6 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-text-primary flex items-center">
                <ShieldAlert className="h-5 w-5 mr-2 text-primary" /> Risk Analysis
              </h2>
              <div className="flex items-center gap-2">
                <span className="text-2xl font-bold text-text-primary">{analysis?.risk_score || 0}</span>
              </div>
            </div>

            {analysis?.score_breakdown?.nlp_threat_confidence < 0.5 && (
              <div className="mb-6 bg-medium/10 border border-medium rounded-lg p-4 flex items-start" role="alert" aria-live="polite">
                <AlertTriangle className="h-5 w-5 text-medium mr-3 mt-0.5 shrink-0" />
                <div>
                  <h4 className="text-sm font-semibold text-medium mb-1">Low Data Confidence</h4>
                  <p className="text-xs text-text-secondary">
                    This score is based on limited data signals. Do not use as the sole basis for investigative action.
                  </p>
                </div>
              </div>
            )}

            <div className="mb-6">
              <p className="text-sm text-text-secondary italic border-l-2 border-border pl-3 py-1 mb-4">
                Driven by: {(analysis?.score_breakdown?.top_factors || []).join(', ')}
              </p>
              
              <h3 className="text-sm font-medium text-text-primary mb-3">Score Breakdown</h3>
              <div className="space-y-3 mb-6">
                {Object.entries(analysis?.score_breakdown || {}).filter(([k]) => k !== 'top_factors' && k !== 'nlp_threat_confidence').map(([key, value]: any) => {
                  const numVal = typeof value === 'number' ? value : 0;
                  const pct = Math.min(numVal * 100, 100);
                  const barColor = pct >= 70 ? 'bg-critical' : pct >= 40 ? 'bg-medium' : 'bg-low';
                  return (
                    <div key={key}>
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-text-secondary capitalize">{key.replace(/_/g, ' ')}</span>
                        <span className="text-text-primary font-medium">{typeof value === 'number' ? value.toFixed(2) : value}</span>
                      </div>
                      <div className="h-1.5 bg-background rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-500 ${barColor}`}
                          style={{ width: `${pct}%` }}
                          role="progressbar"
                          aria-valuenow={pct}
                          aria-valuemin={0}
                          aria-valuemax={100}
                          aria-label={`${key.replace(/_/g, ' ')} score`}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="border-t border-border pt-4">
                <h3 className="text-sm font-medium text-text-primary mb-3 flex items-center">
                  <Tag className="h-4 w-4 mr-2" /> MITRE ATT&CK
                </h3>
                
                <div className="space-y-4">
                  <div>
                    <span className="text-xs text-text-secondary block mb-2">Tactics</span>
                    <div className="flex flex-wrap gap-2 mb-2">
                      {(analysis?.tactics || []).map((t: string) => (
                        <span key={t} className="bg-primary/10 text-primary text-xs px-2 py-1 rounded flex items-center">
                          {t}
                          {canInvestigate && <button onClick={() => handleRemoveTag('tactics', t)} className="ml-1 hover:text-red-500" aria-label={`Remove tactic ${t}`}><X className="h-3 w-3" /></button>}
                        </span>
                      ))}
                    </div>
                    {canInvestigate && (
                      <div className="flex gap-2">
                        <MitreAutocomplete
                          type="tactics"
                          value={newTactic}
                          onChange={setNewTactic}
                          onSubmit={(v) => handleAddTag('tactics', v)}
                          placeholder="Search tactics (e.g. TA0001 or Initial Access)..."
                          className="flex-1"
                        />
                      </div>
                    )}
                  </div>

                  <div>
                    <span className="text-xs text-text-secondary block mb-2">Techniques</span>
                    <div className="flex flex-wrap gap-2 mb-2">
                      {(analysis?.techniques || []).map((t: string) => (
                        <span key={t} className="bg-primary/10 text-primary text-xs px-2 py-1 rounded flex items-center">
                          {t}
                          {canInvestigate && <button onClick={() => handleRemoveTag('techniques', t)} className="ml-1 hover:text-red-500" aria-label={`Remove technique ${t}`}><X className="h-3 w-3" /></button>}
                        </span>
                      ))}
                    </div>
                    {canInvestigate && (
                      <div className="flex gap-2">
                        <MitreAutocomplete
                          type="techniques"
                          value={newTechnique}
                          onChange={setNewTechnique}
                          onSubmit={(v) => handleAddTag('techniques', v)}
                          placeholder="Search techniques (e.g. T1566 or Phishing)..."
                          className="flex-1"
                        />
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="bg-surface border border-border rounded-xl p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-text-primary mb-4 flex items-center">
              <FileText className="h-5 w-5 mr-2 text-primary" /> Generated Reports
            </h2>
            <div className="space-y-3">
              {reports && reports.length > 0 ? (
                reports.map((report: any) => (
                  <div key={report.id} className="bg-background border border-border rounded-lg p-3">
                    <div className="flex justify-between items-start">
                      <div>
                        <p className="text-sm font-medium text-text-primary">{report.report_ref}</p>
                        <p className="text-xs text-text-secondary">By {report.generated_by}</p>
                        <p className="text-xs text-text-secondary mt-1">{new Date(report.created_at).toLocaleString()}</p>
                      </div>
                      {canExportPdf && (
                        <button 
                          onClick={() => {
                            setReliabilityRating(report.source_reliability_rating);
                            handleExportPdf();
                          }}
                          className="text-text-secondary hover:text-primary transition-colors"
                          title="Re-download PDF"
                        >
                          <Download className="h-4 w-4" />
                        </button>
                      )}
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-center py-4 text-text-secondary text-sm">
                  No reports generated yet.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
