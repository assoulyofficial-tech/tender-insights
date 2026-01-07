import { Link } from 'react-router-dom';
import { ExternalLink, FileText, ChevronRight } from 'lucide-react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { StatusBadge } from '@/components/dashboard/StatusBadge';
import { Button } from '@/components/ui/button';
import type { Tender } from '@/types/tender';

interface TenderTableProps {
  tenders: Tender[];
  isLoading?: boolean;
}

export function TenderTable({ tenders, isLoading }: TenderTableProps) {
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
            <TableHead className="w-[140px]">Reference</TableHead>
            <TableHead>Subject</TableHead>
            <TableHead className="w-[120px]">Institution</TableHead>
            <TableHead className="w-[100px]">Deadline</TableHead>
            <TableHead className="w-[90px]">Status</TableHead>
            <TableHead className="w-[80px]"></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {tenders.map((tender) => (
            <TableRow 
              key={tender.id} 
              className="border-border hover:bg-table-hover"
            >
              <TableCell className="font-mono text-sm">
                {tender.external_reference || tender.id.slice(0, 8)}
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
                  >
                    <ExternalLink className="w-4 h-4 text-muted-foreground" />
                  </a>
                  <Link
                    to={`/tender/${tender.id}`}
                    className="p-1.5 rounded hover:bg-muted transition-colors"
                    title="View details"
                  >
                    <ChevronRight className="w-4 h-4 text-muted-foreground" />
                  </Link>
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
