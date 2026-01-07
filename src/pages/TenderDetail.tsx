import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, ExternalLink, Bot, FileText, RefreshCw } from 'lucide-react';
import { AppLayout } from '@/components/layout/AppLayout';
import { StatusBadge } from '@/components/dashboard/StatusBadge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import type { Tender } from '@/types/tender';

// Mock data - will be replaced with API call
const mockTender: Tender = {
  id: '1',
  external_reference: 'AO-2024-001',
  source_url: 'https://www.marchespublics.gov.ma/pmmp/',
  status: 'LISTED',
  scraped_at: '2024-01-15T10:30:00Z',
  download_date: '2024-01-15',
  avis_metadata: {
    reference_tender: { value: 'AO-2024-001', source_document: 'AVIS', source_date: '2024-01-15' },
    tender_type: { value: 'AOON', source_document: 'AVIS', source_date: '2024-01-15' },
    issuing_institution: { value: 'Ministère de la Santé', source_document: 'AVIS', source_date: '2024-01-15' },
    submission_deadline: {
      date: { value: '25/01/2024', source_document: 'AVIS', source_date: '2024-01-15' },
      time: { value: '10:00', source_document: 'AVIS', source_date: '2024-01-15' },
    },
    folder_opening_location: { value: 'Rabat', source_document: 'AVIS', source_date: '2024-01-15' },
    subject: { value: 'Acquisition de fournitures médicales pour les hôpitaux régionaux', source_document: 'AVIS', source_date: '2024-01-15' },
    total_estimated_value: { value: '2,500,000 MAD', currency: 'MAD', source_document: 'AVIS', source_date: '2024-01-15' },
    lots: [
      { lot_number: '1', lot_subject: 'Équipements de diagnostic', lot_estimated_value: '1,200,000 MAD', caution_provisoire: '24,000 MAD' },
      { lot_number: '2', lot_subject: 'Consommables médicaux', lot_estimated_value: '800,000 MAD', caution_provisoire: '16,000 MAD' },
      { lot_number: '3', lot_subject: 'Mobilier médical', lot_estimated_value: '500,000 MAD', caution_provisoire: '10,000 MAD' },
    ],
    keywords: { 
      keywords_fr: ['médical', 'hôpital', 'fournitures', 'diagnostic', 'équipement'],
      keywords_eng: ['medical', 'hospital', 'supplies', 'diagnostic', 'equipment'],
      keywords_ar: ['طبي', 'مستشفى', 'مستلزمات']
    },
  },
  universal_metadata: null,
  created_at: '2024-01-15T10:30:00Z',
  updated_at: '2024-01-15T10:30:00Z',
};

function MetadataField({ label, value, source }: { label: string; value: string | null; source?: string }) {
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

export default function TenderDetail() {
  const { id } = useParams<{ id: string }>();
  const tender = mockTender; // Will be fetched via API

  const handleAnalyze = () => {
    console.log('Triggering deep analysis for:', id);
  };

  return (
    <AppLayout>
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
            </div>
            <p className="text-muted-foreground max-w-2xl">
              {tender.avis_metadata?.subject?.value}
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" asChild>
              <a href={tender.source_url} target="_blank" rel="noopener noreferrer">
                <ExternalLink className="w-4 h-4 mr-2" />
                Original
              </a>
            </Button>
            {tender.status === 'LISTED' && (
              <Button size="sm" onClick={handleAnalyze}>
                <RefreshCw className="w-4 h-4 mr-2" />
                Deep Analyze
              </Button>
            )}
          </div>
        </div>

        {/* Tabs */}
        <Tabs defaultValue="metadata" className="space-y-4">
          <TabsList>
            <TabsTrigger value="metadata">Metadata</TabsTrigger>
            <TabsTrigger value="lots">Lots ({tender.avis_metadata?.lots?.length || 0})</TabsTrigger>
            <TabsTrigger value="documents">Documents</TabsTrigger>
            <TabsTrigger value="ask">Ask AI</TabsTrigger>
            <TabsTrigger value="raw">Raw JSON</TabsTrigger>
          </TabsList>

          <TabsContent value="metadata" className="space-y-4">
            <div className="grid md:grid-cols-2 gap-6">
              {/* Left column */}
              <div className="data-card">
                <h3 className="font-medium mb-4">Basic Information</h3>
                <MetadataField 
                  label="Reference" 
                  value={tender.avis_metadata?.reference_tender?.value} 
                  source={tender.avis_metadata?.reference_tender?.source_document || undefined}
                />
                <MetadataField 
                  label="Type" 
                  value={tender.avis_metadata?.tender_type?.value} 
                />
                <MetadataField 
                  label="Issuing Institution" 
                  value={tender.avis_metadata?.issuing_institution?.value} 
                />
                <MetadataField 
                  label="Opening Location" 
                  value={tender.avis_metadata?.folder_opening_location?.value} 
                />
              </div>

              {/* Right column */}
              <div className="data-card">
                <h3 className="font-medium mb-4">Submission Details</h3>
                <MetadataField 
                  label="Deadline Date" 
                  value={tender.avis_metadata?.submission_deadline?.date?.value} 
                  source={tender.avis_metadata?.submission_deadline?.date?.source_document || undefined}
                />
                <MetadataField 
                  label="Deadline Time" 
                  value={tender.avis_metadata?.submission_deadline?.time?.value} 
                />
                <MetadataField 
                  label="Estimated Value" 
                  value={tender.avis_metadata?.total_estimated_value?.value} 
                />
              </div>
            </div>

            {/* Keywords */}
            {tender.avis_metadata?.keywords && (
              <div className="data-card">
                <h3 className="font-medium mb-4">Keywords</h3>
                <div className="space-y-3">
                  {tender.avis_metadata.keywords.keywords_fr?.length > 0 && (
                    <div>
                      <span className="text-xs text-muted-foreground">French:</span>
                      <div className="flex flex-wrap gap-2 mt-1">
                        {tender.avis_metadata.keywords.keywords_fr.map((kw, i) => (
                          <span key={i} className="px-2 py-0.5 bg-muted rounded text-sm">{kw}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  {tender.avis_metadata.keywords.keywords_eng?.length > 0 && (
                    <div>
                      <span className="text-xs text-muted-foreground">English:</span>
                      <div className="flex flex-wrap gap-2 mt-1">
                        {tender.avis_metadata.keywords.keywords_eng.map((kw, i) => (
                          <span key={i} className="px-2 py-0.5 bg-muted rounded text-sm">{kw}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  {tender.avis_metadata.keywords.keywords_ar?.length > 0 && (
                    <div>
                      <span className="text-xs text-muted-foreground">Arabic:</span>
                      <div className="flex flex-wrap gap-2 mt-1" dir="rtl">
                        {tender.avis_metadata.keywords.keywords_ar.map((kw, i) => (
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
            {tender.avis_metadata?.lots?.length ? (
              <div className="space-y-3">
                {tender.avis_metadata.lots.map((lot, index) => (
                  <div key={index} className="data-card">
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="text-sm text-muted-foreground">Lot {lot.lot_number}</div>
                        <div className="font-medium mt-1">{lot.lot_subject}</div>
                      </div>
                      <div className="text-right">
                        <div className="font-mono text-sm">{lot.lot_estimated_value}</div>
                        <div className="text-xs text-muted-foreground mt-1">
                          Caution: {lot.caution_provisoire}
                        </div>
                      </div>
                    </div>
                  </div>
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
            <div className="data-card text-center py-8">
              <FileText className="w-10 h-10 text-muted-foreground mx-auto mb-3" />
              <p className="text-muted-foreground">Documents will appear here after extraction</p>
              <p className="text-xs text-muted-foreground mt-2">AVIS, RC, CPS, Annexes</p>
            </div>
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
            <div className="terminal">
              <div className="terminal-header">
                <div className="terminal-dot bg-destructive" />
                <div className="terminal-dot bg-warning" />
                <div className="terminal-dot bg-success" />
                <span className="ml-2 text-xs text-muted-foreground">avis_metadata.json</span>
              </div>
              <pre className="p-4 text-xs overflow-auto max-h-[500px]">
                {JSON.stringify(tender.avis_metadata, null, 2)}
              </pre>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </AppLayout>
  );
}
