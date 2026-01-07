import { useState } from 'react';
import { Search, RefreshCw, Filter } from 'lucide-react';
import { AppLayout } from '@/components/layout/AppLayout';
import { StatCard } from '@/components/dashboard/StatCard';
import { TenderTable } from '@/components/tenders/TenderTable';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import type { Tender, TenderStatus } from '@/types/tender';

// Mock data for skeleton - will be replaced with API calls
const mockTenders: Tender[] = [
  {
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
      total_estimated_value: { value: '2,500,000 MAD', source_document: 'AVIS', source_date: '2024-01-15' },
      lots: [],
      keywords: { keywords_fr: [], keywords_eng: [], keywords_ar: [] },
    },
    universal_metadata: null,
    created_at: '2024-01-15T10:30:00Z',
    updated_at: '2024-01-15T10:30:00Z',
  },
  {
    id: '2',
    external_reference: 'AO-2024-002',
    source_url: 'https://www.marchespublics.gov.ma/pmmp/',
    status: 'ANALYZED',
    scraped_at: '2024-01-15T10:35:00Z',
    download_date: '2024-01-15',
    avis_metadata: {
      reference_tender: { value: 'AO-2024-002', source_document: 'AVIS', source_date: '2024-01-15' },
      tender_type: { value: 'AOOI', source_document: 'AVIS', source_date: '2024-01-15' },
      issuing_institution: { value: 'Université Mohammed V', source_document: 'AVIS', source_date: '2024-01-15' },
      submission_deadline: {
        date: { value: '30/01/2024', source_document: 'WEBSITE', source_date: '2024-01-15' },
        time: { value: '14:00', source_document: 'WEBSITE', source_date: '2024-01-15' },
      },
      folder_opening_location: { value: 'Faculté des Sciences, Rabat', source_document: 'AVIS', source_date: '2024-01-15' },
      subject: { value: 'Acquisition d\'équipements informatiques et de laboratoire', source_document: 'AVIS', source_date: '2024-01-15' },
      total_estimated_value: { value: '1,800,000 MAD', source_document: 'AVIS', source_date: '2024-01-15' },
      lots: [
        { lot_number: '1', lot_subject: 'Ordinateurs', lot_estimated_value: '800,000 MAD', caution_provisoire: '16,000 MAD' },
        { lot_number: '2', lot_subject: 'Équipements de laboratoire', lot_estimated_value: '1,000,000 MAD', caution_provisoire: '20,000 MAD' },
      ],
      keywords: { keywords_fr: ['informatique', 'laboratoire'], keywords_eng: ['computer', 'laboratory'], keywords_ar: [] },
    },
    universal_metadata: null,
    created_at: '2024-01-15T10:35:00Z',
    updated_at: '2024-01-15T11:00:00Z',
  },
  {
    id: '3',
    external_reference: 'AO-2024-003',
    source_url: 'https://www.marchespublics.gov.ma/pmmp/',
    status: 'PENDING',
    scraped_at: '2024-01-15T10:40:00Z',
    download_date: '2024-01-15',
    avis_metadata: null,
    universal_metadata: null,
    created_at: '2024-01-15T10:40:00Z',
    updated_at: '2024-01-15T10:40:00Z',
  },
];

export default function Index() {
  const [searchQuery, setSearchQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  // Stats derived from mock data
  const stats = {
    total: mockTenders.length,
    listed: mockTenders.filter(t => t.status === 'LISTED').length,
    analyzed: mockTenders.filter(t => t.status === 'ANALYZED').length,
    pending: mockTenders.filter(t => t.status === 'PENDING').length,
  };

  const handleRefresh = () => {
    setIsLoading(true);
    // Simulate API call
    setTimeout(() => setIsLoading(false), 1000);
  };

  const filteredTenders = mockTenders.filter(tender => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      tender.external_reference?.toLowerCase().includes(query) ||
      tender.avis_metadata?.subject?.value?.toLowerCase().includes(query) ||
      tender.avis_metadata?.issuing_institution?.value?.toLowerCase().includes(query)
    );
  });

  return (
    <AppLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold">Tenders</h1>
            <p className="text-muted-foreground text-sm mt-1">
              Search and analyze government tenders from marchespublics.gov.ma
            </p>
          </div>
          <Button onClick={handleRefresh} variant="outline" size="sm">
            <RefreshCw className={`w-4 h-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard label="Total Tenders" value={stats.total} variant="default" />
          <StatCard label="Listed" value={stats.listed} variant="primary" />
          <StatCard label="Analyzed" value={stats.analyzed} variant="success" />
          <StatCard label="Pending" value={stats.pending} variant="warning" />
        </div>

        {/* Search */}
        <div className="flex gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              placeholder="Search by reference, subject, or institution..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10"
            />
          </div>
          <Button variant="outline" size="icon">
            <Filter className="w-4 h-4" />
          </Button>
        </div>

        {/* Table */}
        <TenderTable tenders={filteredTenders} isLoading={isLoading} />
      </div>
    </AppLayout>
  );
}
