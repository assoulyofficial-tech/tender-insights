import { useState } from 'react';
import { Search, RefreshCw, Filter, WifiOff } from 'lucide-react';
import { AppLayout } from '@/components/layout/AppLayout';
import { StatCard } from '@/components/dashboard/StatCard';
import { TenderTable } from '@/components/tenders/TenderTable';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useTenders, useBackendHealth } from '@/hooks/useTenders';

export default function Index() {
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(1);

  const { data: isBackendOnline } = useBackendHealth();
  
  const { 
    data: tendersData, 
    isLoading, 
    isError,
    refetch 
  } = useTenders({
    query: searchQuery || undefined,
    page,
    per_page: 20,
  });

  const tenders = tendersData?.items || [];
  const total = tendersData?.total || 0;

  // Calculate stats from real data
  const stats = {
    total,
    listed: tenders.filter(t => t.status === 'LISTED').length,
    analyzed: tenders.filter(t => t.status === 'ANALYZED').length,
    pending: tenders.filter(t => t.status === 'PENDING').length,
  };

  return (
    <AppLayout>
      <div className="space-y-6">
        {/* Backend Status Alert */}
        {isBackendOnline === false && (
          <div className="flex items-start gap-3 p-4 rounded-lg bg-destructive/10 border border-destructive/20">
            <WifiOff className="w-5 h-5 text-destructive shrink-0 mt-0.5" />
            <div className="text-sm">
              <p className="font-medium text-destructive">Backend Offline</p>
              <p className="text-muted-foreground mt-1">
                Cannot connect to <code className="mx-1 px-1.5 py-0.5 bg-muted rounded font-mono text-xs">localhost:8000</code>. 
                Start the backend with <code className="mx-1 px-1.5 py-0.5 bg-muted rounded font-mono text-xs">cd backend && python main.py</code>
              </p>
            </div>
          </div>
        )}

        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold">Tenders</h1>
            <p className="text-muted-foreground text-sm mt-1">
              Search and analyze government tenders from marchespublics.gov.ma
            </p>
          </div>
          <Button onClick={() => refetch()} variant="outline" size="sm" disabled={isLoading}>
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
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setPage(1); // Reset to first page on search
              }}
              className="pl-10"
            />
          </div>
          <Button variant="outline" size="icon">
            <Filter className="w-4 h-4" />
          </Button>
        </div>

        {/* Error State */}
        {isError && (
          <div className="text-center py-8 text-muted-foreground">
            <p>Failed to load tenders. Is the backend running?</p>
            <Button onClick={() => refetch()} variant="link" className="mt-2">
              Try again
            </Button>
          </div>
        )}

        {/* Table */}
        <TenderTable tenders={tenders} isLoading={isLoading} />

        {/* Pagination */}
        {tendersData && tendersData.total_pages > 1 && (
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              Page {page} of {tendersData.total_pages} ({total} total)
            </p>
            <div className="flex gap-2">
              <Button 
                variant="outline" 
                size="sm" 
                disabled={page <= 1}
                onClick={() => setPage(p => p - 1)}
              >
                Previous
              </Button>
              <Button 
                variant="outline" 
                size="sm" 
                disabled={page >= tendersData.total_pages}
                onClick={() => setPage(p => p + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
}
