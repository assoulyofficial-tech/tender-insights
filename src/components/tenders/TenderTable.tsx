import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ExternalLink, FileText, ChevronRight, ChevronDown, ChevronUp } from 'lucide-react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { StatusBadge } from '@/components/dashboard/StatusBadge';
import { Badge } from '@/components/ui/badge';
import type { Tender, AvisMetadata } from '@/types/tender';

interface TenderTableProps {
  tenders: Tender[];
  isLoading?: boolean;
}

function MetadataField({ label, value, source }: { label: string; value: string | null | undefined; source?: string | null }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs text-muted-foreground uppercase tracking-wide">{label}</span>
      <div className="flex items-center gap-2">
        <span className={value ? "text-sm" : "text-sm text-muted-foreground italic"}>
          {value || 'null'}
        </span>
        {source && (
          <Badge variant="outline" className="text-[10px] px-1 py-0">
            {source}
          </Badge>
        )}
      </div>
    </div>
  );
}

function AvisMetadataDetails({ metadata }: { metadata: AvisMetadata | null }) {
  if (!metadata) {
    return (
      <div className="p-4 bg-muted/30 text-muted-foreground italic text-sm">
        No Avis metadata extracted
      </div>
    );
  }

  return (
    <div className="p-4 bg-muted/20 border-t border-border space-y-4">
      {/* Main Fields Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        <MetadataField 
          label="Reference" 
          value={metadata.reference_tender?.value} 
          source={metadata.reference_tender?.source_document}
        />
        <MetadataField 
          label="Tender Type" 
          value={metadata.tender_type?.value} 
          source={metadata.tender_type?.source_document}
        />
        <MetadataField 
          label="Institution" 
          value={metadata.issuing_institution?.value} 
          source={metadata.issuing_institution?.source_document}
        />
        <MetadataField 
          label="Opening Location" 
          value={metadata.folder_opening_location?.value} 
          source={metadata.folder_opening_location?.source_document}
        />
        <MetadataField 
          label="Deadline Date" 
          value={metadata.submission_deadline?.date?.value} 
          source={metadata.submission_deadline?.date?.source_document}
        />
        <MetadataField 
          label="Deadline Time" 
          value={metadata.submission_deadline?.time?.value} 
          source={metadata.submission_deadline?.time?.source_document}
        />
        <MetadataField 
          label="Estimated Value (TTC)" 
          value={metadata.total_estimated_value?.value} 
          source={metadata.total_estimated_value?.source_document}
        />
        <MetadataField 
          label="Currency" 
          value={metadata.total_estimated_value?.currency} 
        />
      </div>

      {/* Subject - Full Width */}
      <div className="border-t border-border pt-4">
        <MetadataField 
          label="Subject" 
          value={metadata.subject?.value} 
          source={metadata.subject?.source_document}
        />
      </div>

      {/* Lots */}
      {metadata.lots && metadata.lots.length > 0 && (
        <div className="border-t border-border pt-4">
          <span className="text-xs text-muted-foreground uppercase tracking-wide block mb-2">
            Lots ({metadata.lots.length})
          </span>
          <div className="space-y-2">
            {metadata.lots.map((lot, idx) => (
              <div key={idx} className="bg-background/50 rounded p-3 text-sm grid grid-cols-2 md:grid-cols-4 gap-2">
                <div>
                  <span className="text-muted-foreground text-xs">Lot #:</span>{' '}
                  <span className="font-mono">{lot.lot_number || 'null'}</span>
                </div>
                <div className="col-span-2">
                  <span className="text-muted-foreground text-xs">Subject:</span>{' '}
                  {lot.lot_subject || <span className="italic text-muted-foreground">null</span>}
                </div>
                <div>
                  <span className="text-muted-foreground text-xs">Value:</span>{' '}
                  {lot.lot_estimated_value || <span className="italic text-muted-foreground">null</span>}
                </div>
                <div>
                  <span className="text-muted-foreground text-xs">Caution:</span>{' '}
                  {lot.caution_provisoire || <span className="italic text-muted-foreground">null</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Keywords */}
      {metadata.keywords && (
        <div className="border-t border-border pt-4">
          <span className="text-xs text-muted-foreground uppercase tracking-wide block mb-2">
            Keywords
          </span>
          <div className="flex flex-wrap gap-2">
            {metadata.keywords.keywords_fr?.length > 0 && (
              <div className="flex flex-wrap gap-1">
                <Badge variant="secondary" className="text-xs">FR</Badge>
                {metadata.keywords.keywords_fr.map((kw, idx) => (
                  <Badge key={idx} variant="outline" className="text-xs">{kw}</Badge>
                ))}
              </div>
            )}
          </div>
          {metadata.keywords.keywords_eng?.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              <Badge variant="secondary" className="text-xs">EN</Badge>
              {metadata.keywords.keywords_eng.map((kw, idx) => (
                <Badge key={idx} variant="outline" className="text-xs">{kw}</Badge>
              ))}
            </div>
          )}
          {metadata.keywords.keywords_ar?.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              <Badge variant="secondary" className="text-xs">AR</Badge>
              {metadata.keywords.keywords_ar.map((kw, idx) => (
                <Badge key={idx} variant="outline" className="text-xs">{kw}</Badge>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function TenderTable({ tenders, isLoading }: TenderTableProps) {
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  const toggleRow = (id: string) => {
    setExpandedRows(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  if (isLoading) {
    return (
      <div className="data-card">
        <div className="animate-pulse space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-12 bg-muted rounded" />
          ))}
        </div>
      </div>
    );
  }

  if (tenders.length === 0) {
    return (
      <div className="data-card text-center py-12">
        <FileText className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
        <h3 className="text-lg font-medium mb-2">No tenders found</h3>
        <p className="text-muted-foreground text-sm">
          Run the scraper to collect tenders from marchespublics.gov.ma
        </p>
      </div>
    );
  }

  return (
    <div className="data-card p-0 overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent border-border">
            <TableHead className="w-[40px]"></TableHead>
            <TableHead className="w-[140px]">Reference</TableHead>
            <TableHead>Subject</TableHead>
            <TableHead className="w-[120px]">Institution</TableHead>
            <TableHead className="w-[100px]">Deadline</TableHead>
            <TableHead className="w-[90px]">Status</TableHead>
            <TableHead className="w-[80px]"></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {tenders.map((tender) => {
            const isExpanded = expandedRows.has(tender.id);
            return (
              <>
                <TableRow 
                  key={tender.id} 
                  className="border-border hover:bg-table-hover cursor-pointer"
                  onClick={() => toggleRow(tender.id)}
                >
                  <TableCell className="p-2">
                    <button 
                      className="p-1 rounded hover:bg-muted transition-colors"
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleRow(tender.id);
                      }}
                    >
                      {isExpanded ? (
                        <ChevronUp className="w-4 h-4 text-muted-foreground" />
                      ) : (
                        <ChevronDown className="w-4 h-4 text-muted-foreground" />
                      )}
                    </button>
                  </TableCell>
                  <TableCell className="font-mono text-sm">
                    {tender.avis_metadata?.reference_tender?.value || tender.external_reference || tender.id.slice(0, 8)}
                  </TableCell>
                  <TableCell className="max-w-[400px] truncate">
                    {tender.avis_metadata?.subject?.value || 
                      <span className="text-muted-foreground italic">No subject extracted</span>
                    }
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground truncate max-w-[150px]">
                    {tender.avis_metadata?.issuing_institution?.value || '—'}
                  </TableCell>
                  <TableCell className="font-mono text-sm">
                    {tender.avis_metadata?.submission_deadline?.date?.value || '—'}
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={tender.status} />
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1">
                      <a
                        href={tender.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="p-1.5 rounded hover:bg-muted transition-colors"
                        title="View original"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <ExternalLink className="w-4 h-4 text-muted-foreground" />
                      </a>
                      <Link
                        to={`/tender/${tender.id}`}
                        className="p-1.5 rounded hover:bg-muted transition-colors"
                        title="View details"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <ChevronRight className="w-4 h-4 text-muted-foreground" />
                      </Link>
                    </div>
                  </TableCell>
                </TableRow>
                {isExpanded && (
                  <TableRow key={`${tender.id}-details`} className="hover:bg-transparent">
                    <TableCell colSpan={7} className="p-0">
                      <AvisMetadataDetails metadata={tender.avis_metadata} />
                    </TableCell>
                  </TableRow>
                )}
              </>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}