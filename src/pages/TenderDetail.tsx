import { useParams, Link } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { ArrowLeft, ExternalLink, Bot, FileText, RefreshCw, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import { AppLayout } from '@/components/layout/AppLayout';
import { StatusBadge } from '@/components/dashboard/StatusBadge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Progress } from '@/components/ui/progress';
import { api } from '@/lib/api';
import type { Tender, TenderLot, TenderItem, UniversalMetadata, AvisMetadata } from '@/types/tender';

function MetadataField({ label, value, source }: { label: string; value: string | null | undefined; source?: string | null }) {
  return (
    <div className="py-3 border-b border-border last:border-0">
      <div className="text-xs text-muted-foreground mb-1">{label}</div>
      <div className="font-medium">
        {value || <span className="text-muted-foreground italic">Not extracted</span>}
      </div>
      {source && (
        <div className="text-xs text-muted-foreground mt-1">
          Source: <span className="font-mono">{source}</span>
        </div>
      )}
    </div>
  );
}

function LotCard({ lot, index, showDeepFields }: { lot: TenderLot; index: number; showDeepFields: boolean }) {
  return (
    <div className="data-card space-y-4">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="text-sm text-muted-foreground">Lot {lot.lot_number || index + 1}</div>
          <div className="font-medium mt-1">{lot.lot_subject || <span className="text-muted-foreground italic">No subject</span>}</div>
        </div>
        <div className="text-right">
          <div className="font-mono text-sm">{lot.lot_estimated_value || '-'}</div>
          <div className="text-xs text-muted-foreground mt-1">
            Caution Provisoire: {lot.caution_provisoire || '-'}
          </div>
        </div>
      </div>
      
      {showDeepFields && (
        <div className="border-t border-border pt-4 space-y-3">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-muted-foreground">Caution Définitive %:</span>
              <span className="ml-2 font-medium">{lot.caution_definitive_percentage || '-'}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Caution Définitive Estimée:</span>
              <span className="ml-2 font-medium">{lot.estimated_caution_definitive_value || '-'}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Délai d'exécution:</span>
              <span className="ml-2 font-medium">{lot.execution_date || '-'}</span>
            </div>
          </div>
          
          {lot.items && lot.items.length > 0 && (
            <div className="mt-4">
              <div className="text-sm font-medium mb-2">Items ({lot.items.length})</div>
              <div className="space-y-2">
                {lot.items.map((item, itemIndex) => (
                  <ItemCard key={itemIndex} item={item} index={itemIndex} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ItemCard({ item, index }: { item: TenderItem; index: number }) {
  return (
    <div className="bg-muted/50 rounded-lg p-3 text-sm">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          <div className="font-medium">{item.item_name || `Item ${index + 1}`}</div>
          {item.technical_description_full && (
            <div className="text-muted-foreground mt-1 text-xs whitespace-pre-wrap">
              {item.technical_description_full}
            </div>
          )}
        </div>
        <div className="text-right shrink-0">
          <span className="font-mono">{item.quantity || '-'}</span>
        </div>
      </div>
    </div>
  );
}

function LoadingOverlay({ progress, message }: { progress: number; message: string }) {
  return (
    <div className="fixed inset-0 bg-background/80 backdrop-blur-sm z-50 flex items-center justify-center">
      <div className="bg-card border border-border rounded-lg p-8 max-w-md w-full mx-4 space-y-4 shadow-lg">
        <div className="flex items-center gap-3">
          <Loader2 className="w-6 h-6 animate-spin text-primary" />
          <div className="text-lg font-medium">Deep Analysis in Progress</div>
        </div>
        <Progress value={progress} className="h-2" />
        <p className="text-sm text-muted-foreground">{message}</p>
        <p className="text-xs text-muted-foreground">
          Extracting data from all documents (Avis, RC, CPS, Annexes)...
        </p>
      </div>
    </div>
  );
}

export default function TenderDetail() {
  const { id } = useParams<{ id: string }>();
  const [tender, setTender] = useState<Tender | null>(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeProgress, setAnalyzeProgress] = useState(0);
  const [analyzeMessage, setAnalyzeMessage] = useState('Initializing...');
  const [error, setError] = useState<string | null>(null);

  // Fetch tender on mount
  useEffect(() => {
    if (!id) return;
    
    const fetchTender = async () => {
      setLoading(true);
      setError(null);
      
      const response = await api.getTender(id);
      
      if (response.success && response.data) {
        setTender(response.data);
        
        // Auto-trigger analysis if tender is LISTED (not yet analyzed)
        if (response.data.status === 'LISTED' && !response.data.universal_metadata) {
          triggerAnalysis(id);
        }
      } else {
        setError(response.error || 'Failed to load tender');
      }
      
      setLoading(false);
    };
    
    fetchTender();
  }, [id]);

  const triggerAnalysis = async (tenderId: string) => {
    setAnalyzing(true);
    setAnalyzeProgress(10);
    setAnalyzeMessage('Connecting to AI pipeline...');
    
    // Simulate progress updates
    const progressInterval = setInterval(() => {
      setAnalyzeProgress(prev => {
        if (prev >= 90) return prev;
        const increment = Math.random() * 15;
        return Math.min(prev + increment, 90);
      });
      
      // Update message based on progress
      setAnalyzeProgress(prev => {
        if (prev < 30) setAnalyzeMessage('Extracting document text...');
        else if (prev < 50) setAnalyzeMessage('Analyzing with AI...');
        else if (prev < 70) setAnalyzeMessage('Processing lots and items...');
        else setAnalyzeMessage('Finalizing extraction...');
        return prev;
      });
    }, 500);
    
    try {
      const response = await api.analyzeTender(tenderId);
      
      clearInterval(progressInterval);
      setAnalyzeProgress(100);
      setAnalyzeMessage('Complete!');
      
      if (response.success && response.data) {
        setTimeout(() => {
          setTender(response.data!);
          setAnalyzing(false);
        }, 500);
      } else {
        setError(response.error || 'Analysis failed');
        setAnalyzing(false);
      }
    } catch (err) {
      clearInterval(progressInterval);
      setError('Analysis failed');
      setAnalyzing(false);
    }
  };

  const handleManualAnalyze = () => {
    if (id) triggerAnalysis(id);
  };

  // Get the best available metadata (universal or avis)
  const metadata: UniversalMetadata | AvisMetadata | null = tender?.universal_metadata || tender?.avis_metadata || null;
  const hasUniversalData = !!tender?.universal_metadata;
  const lots = metadata?.lots || [];

  if (loading) {
    return (
      <AppLayout>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
        </div>
      </AppLayout>
    );
  }

  if (error || !tender) {
    return (
      <AppLayout>
        <div className="space-y-6">
          <Link 
            to="/" 
            className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to tenders
          </Link>
          <div className="data-card text-center py-12">
            <AlertCircle className="w-12 h-12 text-destructive mx-auto mb-4" />
            <h2 className="text-lg font-medium mb-2">Failed to Load Tender</h2>
            <p className="text-muted-foreground">{error || 'Tender not found'}</p>
          </div>
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      {analyzing && (
        <LoadingOverlay progress={analyzeProgress} message={analyzeMessage} />
      )}
      
      <div className="space-y-6">
        {/* Back link */}
        <Link 
          to="/" 
          className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to tenders
        </Link>

        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <h1 className="text-2xl font-semibold font-mono">
                {tender.external_reference}
              </h1>
              <StatusBadge status={tender.status} />
              {hasUniversalData && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-success/10 text-success rounded text-xs">
                  <CheckCircle2 className="w-3 h-3" />
                  Deep Analyzed
                </span>
              )}
            </div>
            <p className="text-muted-foreground max-w-2xl">
              {metadata?.subject?.value}
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" asChild>
              <a href={tender.source_url} target="_blank" rel="noopener noreferrer">
                <ExternalLink className="w-4 h-4 mr-2" />
                Original
              </a>
            </Button>
            {!hasUniversalData && (
              <Button size="sm" onClick={handleManualAnalyze} disabled={analyzing}>
                <RefreshCw className={`w-4 h-4 mr-2 ${analyzing ? 'animate-spin' : ''}`} />
                Deep Analyze
              </Button>
            )}
          </div>
        </div>

        {/* Tabs */}
        <Tabs defaultValue="metadata" className="space-y-4">
          <TabsList>
            <TabsTrigger value="metadata">Metadata</TabsTrigger>
            <TabsTrigger value="lots">Lots ({lots.length})</TabsTrigger>
            <TabsTrigger value="documents">Documents</TabsTrigger>
            <TabsTrigger value="ask">Ask AI</TabsTrigger>
            <TabsTrigger value="raw">Raw JSON</TabsTrigger>
          </TabsList>

          <TabsContent value="metadata" className="space-y-4">
            {/* Data source indicator */}
            <div className="flex items-center gap-2 text-sm">
              <span className="text-muted-foreground">Data source:</span>
              <span className={`px-2 py-0.5 rounded text-xs ${hasUniversalData ? 'bg-success/10 text-success' : 'bg-muted'}`}>
                {hasUniversalData ? 'Universal Metadata (Deep Analysis)' : 'Avis Metadata (Phase 1)'}
              </span>
            </div>

            <div className="grid md:grid-cols-2 gap-6">
              {/* Left column - Basic Info */}
              <div className="data-card">
                <h3 className="font-medium mb-4">Basic Information</h3>
                <MetadataField 
                  label="Reference" 
                  value={metadata?.reference_tender?.value} 
                  source={metadata?.reference_tender?.source_document}
                />
                <MetadataField 
                  label="Type" 
                  value={metadata?.tender_type?.value} 
                  source={metadata?.tender_type?.source_document}
                />
                <MetadataField 
                  label="Issuing Institution" 
                  value={metadata?.issuing_institution?.value} 
                  source={metadata?.issuing_institution?.source_document}
                />
                {hasUniversalData && (tender.universal_metadata as UniversalMetadata)?.institution_address && (
                  <MetadataField 
                    label="Institution Address" 
                    value={(tender.universal_metadata as UniversalMetadata).institution_address?.value} 
                    source={(tender.universal_metadata as UniversalMetadata).institution_address?.source_document}
                  />
                )}
                <MetadataField 
                  label="Opening Location" 
                  value={metadata?.folder_opening_location?.value} 
                  source={metadata?.folder_opening_location?.source_document}
                />
              </div>

              {/* Right column - Submission Details */}
              <div className="data-card">
                <h3 className="font-medium mb-4">Submission Details</h3>
                <MetadataField 
                  label="Deadline Date" 
                  value={metadata?.submission_deadline?.date?.value} 
                  source={metadata?.submission_deadline?.date?.source_document}
                />
                <MetadataField 
                  label="Deadline Time" 
                  value={metadata?.submission_deadline?.time?.value} 
                  source={metadata?.submission_deadline?.time?.source_document}
                />
                <MetadataField 
                  label="Estimated Value" 
                  value={metadata?.total_estimated_value?.value} 
                  source={metadata?.total_estimated_value?.source_document}
                />
                {metadata?.total_estimated_value?.currency && (
                  <MetadataField 
                    label="Currency" 
                    value={metadata.total_estimated_value.currency} 
                  />
                )}
              </div>
            </div>

            {/* Subject */}
            <div className="data-card">
              <h3 className="font-medium mb-4">Subject</h3>
              <p className="text-sm whitespace-pre-wrap">{metadata?.subject?.value || 'Not extracted'}</p>
              {metadata?.subject?.source_document && (
                <div className="text-xs text-muted-foreground mt-2">
                  Source: <span className="font-mono">{metadata.subject.source_document}</span>
                </div>
              )}
            </div>

            {/* Keywords */}
            {metadata?.keywords && (
              <div className="data-card">
                <h3 className="font-medium mb-4">Keywords</h3>
                <div className="space-y-3">
                  {metadata.keywords.keywords_fr?.length > 0 && (
                    <div>
                      <span className="text-xs text-muted-foreground">French:</span>
                      <div className="flex flex-wrap gap-2 mt-1">
                        {metadata.keywords.keywords_fr.map((kw, i) => (
                          <span key={i} className="px-2 py-0.5 bg-muted rounded text-sm">{kw}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  {metadata.keywords.keywords_eng?.length > 0 && (
                    <div>
                      <span className="text-xs text-muted-foreground">English:</span>
                      <div className="flex flex-wrap gap-2 mt-1">
                        {metadata.keywords.keywords_eng.map((kw, i) => (
                          <span key={i} className="px-2 py-0.5 bg-muted rounded text-sm">{kw}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  {metadata.keywords.keywords_ar?.length > 0 && (
                    <div>
                      <span className="text-xs text-muted-foreground">Arabic:</span>
                      <div className="flex flex-wrap gap-2 mt-1" dir="rtl">
                        {metadata.keywords.keywords_ar.map((kw, i) => (
                          <span key={i} className="px-2 py-0.5 bg-muted rounded text-sm">{kw}</span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </TabsContent>

          <TabsContent value="lots" className="space-y-4">
            {/* Lots summary */}
            <div className="flex items-center justify-between">
              <div className="text-sm text-muted-foreground">
                {lots.length} lot{lots.length !== 1 ? 's' : ''} extracted
              </div>
              {hasUniversalData && (
                <span className="text-xs text-success">Deep analysis data available</span>
              )}
            </div>

            {lots.length > 0 ? (
              <div className="space-y-3">
                {lots.map((lot, index) => (
                  <LotCard 
                    key={index} 
                    lot={lot} 
                    index={index} 
                    showDeepFields={hasUniversalData} 
                  />
                ))}
              </div>
            ) : (
              <div className="data-card text-center py-8">
                <FileText className="w-10 h-10 text-muted-foreground mx-auto mb-3" />
                <p className="text-muted-foreground">No lots extracted</p>
              </div>
            )}
          </TabsContent>

          <TabsContent value="documents" className="space-y-4">
            {tender.documents && tender.documents.length > 0 ? (
              <div className="space-y-3">
                {tender.documents.map((doc) => (
                  <div key={doc.id} className="data-card">
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="flex items-center gap-2">
                          <FileText className="w-4 h-4 text-muted-foreground" />
                          <span className="font-medium">{doc.filename}</span>
                          <span className="px-2 py-0.5 bg-muted rounded text-xs">{doc.document_type}</span>
                        </div>
                        <div className="text-sm text-muted-foreground mt-1">
                          {doc.page_count} pages • {doc.extraction_method}
                        </div>
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {new Date(doc.extracted_at).toLocaleDateString()}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="data-card text-center py-8">
                <FileText className="w-10 h-10 text-muted-foreground mx-auto mb-3" />
                <p className="text-muted-foreground">Documents will appear here after extraction</p>
                <p className="text-xs text-muted-foreground mt-2">AVIS, RC, CPS, Annexes</p>
              </div>
            )}
          </TabsContent>

          <TabsContent value="ask" className="space-y-4">
            <div className="data-card text-center py-8">
              <Bot className="w-10 h-10 text-muted-foreground mx-auto mb-3" />
              <p className="font-medium mb-2">Ask AI (Phase 3)</p>
              <p className="text-muted-foreground text-sm max-w-md mx-auto">
                Ask questions about this tender in French or Moroccan Darija. 
                AI will provide expert answers with document citations.
              </p>
            </div>
          </TabsContent>

          <TabsContent value="raw" className="space-y-4">
            {/* Show both metadata sources */}
            <div className="space-y-4">
              {tender.universal_metadata && (
                <div className="terminal">
                  <div className="terminal-header">
                    <div className="terminal-dot bg-success" />
                    <div className="terminal-dot bg-warning" />
                    <div className="terminal-dot bg-destructive" />
                    <span className="ml-2 text-xs text-muted-foreground">universal_metadata.json (Deep Analysis)</span>
                  </div>
                  <pre className="p-4 text-xs overflow-auto max-h-[400px]">
                    {JSON.stringify(tender.universal_metadata, null, 2)}
                  </pre>
                </div>
              )}
              
              {tender.avis_metadata && (
                <div className="terminal">
                  <div className="terminal-header">
                    <div className="terminal-dot bg-primary" />
                    <div className="terminal-dot bg-warning" />
                    <div className="terminal-dot bg-destructive" />
                    <span className="ml-2 text-xs text-muted-foreground">avis_metadata.json (Phase 1)</span>
                  </div>
                  <pre className="p-4 text-xs overflow-auto max-h-[400px]">
                    {JSON.stringify(tender.avis_metadata, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </AppLayout>
  );
}
